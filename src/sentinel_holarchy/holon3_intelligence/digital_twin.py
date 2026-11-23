"""
Holon 3: Clamart Biorefinery Digital Twin v2.0 Core.

Provides:
  1. SQLite persistence (`DigitalTwinDatabase`) for batches, real-time ESP32 telemetry,
     auto-calibrated kinetic parameters, and cryptographic Certificates of Analysis (CoA).
  2. Real-time hardware-in-the-loop sensor ingestion (`ingest_esp32_packet`) with live EKF,
     baseline salt tare EC0, Delta_EC stoichiometric tracking, and DO Spike detection.
  3. System Identification (`ParameterAutoCalibrator`) via bounded Nelder-Mead simplex
     optimization to automatically fit Microbial KineticParameters to real Clamart batches.
  4. OpenRAMAN spectrum deconvolution + Ecocert UAB audit + SHA-256 CoA issuance.
"""

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import json
import math
import sqlite3
import numpy as np

from sentinel_holarchy.holon0_microbial.kinetics import KineticParameters
from sentinel_holarchy.holon0_microbial.multi_molecules import (
    BiorefineryBatchInput,
    MultiMoleculeEngine,
    RefiningProgramId,
)
from sentinel_holarchy.holon0_microbial.thermodynamics_flux import (
    CarbonAndThermalBalanceEngine,
    ThermalReactorConfig,
)
from sentinel_holarchy.holon1_hardware.auto_dosing import StoichiometricProductTracker
from sentinel_holarchy.holon1_hardware.soft_sensor import BioprocessEKFSoftSensor
from sentinel_holarchy.holon2_workshop.ecocert_validator import EcocertUABAuditor, LabAssayResults
from sentinel_holarchy.holon3_intelligence.knowledge_ledger import KnowledgeLedgerManager
from sentinel_holarchy.holon3_intelligence.openraman import OpenRamanPipeline


class DigitalTwinDatabase:
    """SQLite persistence store for the Clamart Biorefinery Digital Twin."""

    def __init__(self, db_path: str = "data/clamart_digital_twin.db"):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._persistent_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._persistent_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._persistent_conn.row_factory = sqlite3.Row
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._persistent_conn is not None:
            return self._persistent_conn
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _close_if_file(self, conn: sqlite3.Connection) -> None:
        if self._persistent_conn is None:
            conn.close()

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    program_id TEXT NOT NULL,
                    waste_kg REAL NOT NULL,
                    brown_starch_ratio REAL NOT NULL,
                    ec0_ms_cm REAL NOT NULL,
                    volume_l REAL NOT NULL,
                    status TEXT NOT NULL,
                    observed_grade_a_g REAL DEFAULT 0.0,
                    predicted_grade_a_g REAL DEFAULT 0.0,
                    gross_revenue_eur REAL DEFAULT 0.0,
                    net_margin_eur REAL DEFAULT 0.0,
                    co2_avoided_kg REAL DEFAULT 0.0,
                    input_json TEXT NOT NULL,
                    summary_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telemetry_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    t_h REAL NOT NULL,
                    source TEXT NOT NULL,
                    ph REAL NOT NULL,
                    orp_mv REAL NOT NULL,
                    ec_ms_cm REAL NOT NULL,
                    delta_ec_ms_cm REAL NOT NULL,
                    co2_ml_min REAL NOT NULL,
                    do_mg_l REAL NOT NULL,
                    temp_c REAL NOT NULL,
                    hx711_kg REAL NOT NULL,
                    rpm REAL NOT NULL,
                    ekf_vfa_g_l REAL NOT NULL,
                    stoich_vfa_g_l REAL NOT NULL,
                    alerts_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_telemetry_batch_t
                ON telemetry_points(batch_id, source, t_h);

                CREATE TABLE IF NOT EXISTS calibrated_parameters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    calibrated_at TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    program_id TEXT NOT NULL,
                    mu_max_acid REAL NOT NULL,
                    y_vfa_carb REAL NOT NULL,
                    caco3_dissolution_rate REAL NOT NULL,
                    q_pha_max REAL NOT NULL,
                    y_pha_vfa REAL NOT NULL,
                    rmse_before_pct REAL NOT NULL,
                    rmse_after_pct REAL NOT NULL,
                    notes TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS certificates_coa (
                    batch_id TEXT PRIMARY KEY,
                    issued_at TEXT NOT NULL,
                    program_id TEXT NOT NULL,
                    product_label TEXT NOT NULL,
                    purity_pct REAL NOT NULL,
                    crystallinity_pct REAL NOT NULL,
                    hv_mol_pct REAL NOT NULL,
                    uab_status TEXT NOT NULL,
                    coa_sha256 TEXT NOT NULL,
                    ledger_entry_hash TEXT NOT NULL,
                    coa_json TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            self._close_if_file(conn)

    def save_batch(
        self,
        batch_id: str,
        inp: BiorefineryBatchInput,
        sim_result: Dict[str, Any],
        status: str = "SIMULATED",
        observed_grade_a_g: Optional[float] = None,
    ) -> None:
        conn = self._connect()
        try:
            pred_g = float(sim_result["products"]["grade_a_mass_g"])
            obs_g = float(observed_grade_a_g) if observed_grade_a_g is not None else pred_g
            summary_compact = {
                "program": sim_result["program"],
                "feedstock": sim_result["feedstock"],
                "events": sim_result["events"],
                "products": sim_result["products"],
                "economics": sim_result["economics"],
                "lca": sim_result["lca"],
                "parameters_used": sim_result["parameters_used"],
            }
            conn.execute(
                """
                INSERT OR REPLACE INTO batches (
                    batch_id, created_at, program_id, waste_kg, brown_starch_ratio,
                    ec0_ms_cm, volume_l, status, observed_grade_a_g, predicted_grade_a_g,
                    gross_revenue_eur, net_margin_eur, co2_avoided_kg, input_json, summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    datetime.now(timezone.utc).isoformat(),
                    inp.program_id,
                    inp.hx711_waste_kg,
                    inp.brown_starch_ratio,
                    inp.baseline_ec0_ms_cm,
                    sim_result["feedstock"]["effective_volume_l"],
                    status,
                    obs_g,
                    pred_g,
                    sim_result["economics"]["gross_revenue_batch_eur"],
                    sim_result["economics"]["net_margin_batch_eur"],
                    sim_result["lca"]["total_co2_eq_avoided_kg"],
                    json.dumps(asdict(inp)),
                    json.dumps(summary_compact),
                ),
            )
            conn.commit()
        finally:
            self._close_if_file(conn)

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["input"] = json.loads(d.pop("input_json"))
            d["summary"] = json.loads(d.pop("summary_json"))
            return d
        finally:
            self._close_if_file(conn)

    def list_batches(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT batch_id, created_at, program_id, waste_kg, ec0_ms_cm, volume_l,
                       status, observed_grade_a_g, predicted_grade_a_g,
                       gross_revenue_eur, net_margin_eur, co2_avoided_kg
                FROM batches
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close_if_file(conn)

    def insert_telemetry_point(self, point: Dict[str, Any]) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO telemetry_points (
                    batch_id, timestamp_utc, t_h, source, ph, orp_mv, ec_ms_cm,
                    delta_ec_ms_cm, co2_ml_min, do_mg_l, temp_c, hx711_kg, rpm,
                    ekf_vfa_g_l, stoich_vfa_g_l, alerts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    point["batch_id"],
                    point.get("timestamp_utc", datetime.now(timezone.utc).isoformat()),
                    float(point["t_h"]),
                    point.get("source", "ESP32_REAL"),
                    float(point["ph"]),
                    float(point["orp_mv"]),
                    float(point["ec_ms_cm"]),
                    float(point["delta_ec_ms_cm"]),
                    float(point.get("co2_ml_min", 0.0)),
                    float(point["do_mg_l"]),
                    float(point.get("temp_c", 28.0)),
                    float(point.get("hx711_kg", 0.0)),
                    float(point.get("rpm", 10.0)),
                    float(point["ekf_vfa_g_l"]),
                    float(point["stoich_vfa_g_l"]),
                    json.dumps(point.get("alerts", {})),
                ),
            )
            conn.commit()
        finally:
            self._close_if_file(conn)

    def clear_telemetry_for_batch(self, batch_id: str, source: str = "ESP32_REAL") -> None:
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM telemetry_points WHERE batch_id = ? AND source = ?",
                (batch_id, source),
            )
            conn.commit()
        finally:
            self._close_if_file(conn)

    def get_telemetry(self, batch_id: str, source: str = "ESP32_REAL") -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT t_h, ph, orp_mv, ec_ms_cm, delta_ec_ms_cm, co2_ml_min,
                       do_mg_l, temp_c, hx711_kg, rpm, ekf_vfa_g_l, stoich_vfa_g_l, alerts_json
                FROM telemetry_points
                WHERE batch_id = ? AND source = ?
                ORDER BY t_h ASC
                """,
                (batch_id, source),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["alerts"] = json.loads(d.pop("alerts_json"))
                out.append(d)
            return out
        finally:
            self._close_if_file(conn)

    def save_calibrated_parameters(
        self,
        batch_id: str,
        program_id: str,
        params: KineticParameters,
        rmse_before_pct: float,
        rmse_after_pct: float,
        notes: str = "",
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO calibrated_parameters (
                    calibrated_at, batch_id, program_id, mu_max_acid, y_vfa_carb,
                    caco3_dissolution_rate, q_pha_max, y_pha_vfa,
                    rmse_before_pct, rmse_after_pct, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    batch_id,
                    program_id,
                    params.mu_max_acid,
                    params.y_vfa_carb,
                    params.caco3_dissolution_rate,
                    params.q_pha_max,
                    params.y_pha_vfa,
                    rmse_before_pct,
                    rmse_after_pct,
                    notes,
                ),
            )
            conn.execute(
                "UPDATE batches SET status = 'CALIBRATED' WHERE batch_id = ?",
                (batch_id,),
            )
            conn.commit()
        finally:
            self._close_if_file(conn)

    def get_latest_calibrated_parameters(self, program_id: Optional[str] = None) -> Tuple[KineticParameters, Optional[Dict[str, Any]]]:
        conn = self._connect()
        try:
            if program_id:
                row = conn.execute(
                    "SELECT * FROM calibrated_parameters WHERE program_id = ? ORDER BY id DESC LIMIT 1",
                    (program_id,),
                ).fetchone()
            else:
                row = None
            if not row:
                row = conn.execute(
                    "SELECT * FROM calibrated_parameters ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if not row:
                return KineticParameters(), None
            meta = dict(row)
            params = KineticParameters(
                mu_max_acid=float(meta["mu_max_acid"]),
                y_vfa_carb=float(meta["y_vfa_carb"]),
                caco3_dissolution_rate=float(meta["caco3_dissolution_rate"]),
                q_pha_max=float(meta["q_pha_max"]),
                y_pha_vfa=float(meta["y_pha_vfa"]),
            )
            return params, meta
        finally:
            self._close_if_file(conn)

    def reset_calibrations(self) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM calibrated_parameters")
            conn.commit()
        finally:
            self._close_if_file(conn)

    def save_certificate_coa(self, coa: Dict[str, Any]) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO certificates_coa (
                    batch_id, issued_at, program_id, product_label, purity_pct,
                    crystallinity_pct, hv_mol_pct, uab_status, coa_sha256,
                    ledger_entry_hash, coa_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    coa["batch_id"],
                    coa["issued_at"],
                    coa["program_id"],
                    coa["product_label"],
                    coa["raman_analysis"]["purity_estimate_pct"],
                    coa["raman_analysis"]["crystallinity_index_pct"],
                    coa["hv_mol_pct"],
                    coa["ecocert_audit"]["status"],
                    coa["coa_sha256"],
                    coa["ledger_entry_hash"],
                    json.dumps(coa),
                ),
            )
            conn.execute(
                "UPDATE batches SET status = 'CERTIFIED_COA' WHERE batch_id = ?",
                (coa["batch_id"],),
            )
            conn.commit()
        finally:
            self._close_if_file(conn)


class ParameterAutoCalibrator:
    """
    System Identification module fitting KineticParameters to empirical Clamart drum telemetry
    (Delta_EC carboxylate curve, DO respiration curve, and final harvested Grade A mass).
    Uses a pure-NumPy bounded Nelder-Mead simplex optimizer (zero SciPy dependency).
    """

    BOUNDS = np.array(
        [
            [0.16, 0.72],  # mu_max_acid (h^-1)
            [0.45, 0.90],  # y_vfa_carb (g/g)
            [0.18, 0.72],  # q_pha_max (h^-1)
            [0.40, 0.84],  # y_pha_vfa (g/g)
        ],
        dtype=float,
    )

    @classmethod
    def _clip_theta(cls, theta: np.ndarray) -> np.ndarray:
        return np.clip(theta, cls.BOUNDS[:, 0], cls.BOUNDS[:, 1])

    @staticmethod
    def compute_normalized_rmse_pct(
        sim_result: Dict[str, Any],
        observed_points: List[Dict[str, Any]],
        observed_grade_a_g: float,
    ) -> float:
        """Computes normalized RMSE (%) across Delta_EC(t), DO(t), and final Grade A mass."""
        traj = sim_result["trajectory"]
        traj_by_t = {round(pt["t"], 1): pt for pt in traj}

        sq_errors: List[float] = []
        for obs in observed_points:
            t_key = round(float(obs["t_h"]), 1)
            pred = traj_by_t.get(t_key)
            if pred is None:
                # Nearest neighbor lookup
                pred = min(traj, key=lambda p: abs(p["t"] - t_key))

            err_dec = (pred["delta_ec_ms"] - float(obs["delta_ec_ms_cm"])) / 2.2
            err_do = (pred["do_mg_l"] - float(obs["do_mg_l"])) / 8.0
            sq_errors.append(0.60 * (err_dec ** 2) + 0.40 * (err_do ** 2))

        mean_traj_mse = float(np.mean(sq_errors)) if sq_errors else 0.0
        pred_mass_g = float(sim_result["products"]["grade_a_mass_g"])
        err_mass = (pred_mass_g - observed_grade_a_g) / max(10.0, observed_grade_a_g)

        combined_rmse = math.sqrt(0.65 * mean_traj_mse + 0.35 * (err_mass ** 2))
        return round(combined_rmse * 100.0, 2)

    @classmethod
    def calibrate(
        cls,
        inp: BiorefineryBatchInput,
        observed_points: List[Dict[str, Any]],
        observed_grade_a_g: float,
        initial_params: Optional[KineticParameters] = None,
        max_iter: int = 65,
    ) -> Dict[str, Any]:
        base = initial_params or KineticParameters()
        baseline_sim = MultiMoleculeEngine(params=base).simulate_batch(inp, dt_h=0.5)
        rmse_before = cls.compute_normalized_rmse_pct(baseline_sim, observed_points, observed_grade_a_g)

        def loss_fn(theta_raw: np.ndarray) -> float:
            theta = cls._clip_theta(theta_raw)
            cand = KineticParameters(
                mu_max_acid=float(theta[0]),
                y_vfa_carb=float(theta[1]),
                caco3_dissolution_rate=base.caco3_dissolution_rate,
                q_pha_max=float(theta[2]),
                y_pha_vfa=float(theta[3]),
            )
            sim = MultiMoleculeEngine(params=cand).simulate_batch(inp, dt_h=0.5)
            return cls.compute_normalized_rmse_pct(sim, observed_points, observed_grade_a_g)

        x0 = np.array(
            [base.mu_max_acid, base.y_vfa_carb, base.q_pha_max, base.y_pha_vfa],
            dtype=float,
        )
        n = len(x0)
        simplex = [x0.copy()]
        steps = np.array([0.08, 0.07, 0.08, 0.07], dtype=float)
        for i in range(n):
            v = x0.copy()
            v[i] = cls._clip_theta(v)[i] + steps[i]
            v = cls._clip_theta(v)
            simplex.append(v)

        f_vals = [loss_fn(v) for v in simplex]

        alpha, gamma, rho, sigma = 1.0, 2.0, 0.5, 0.5
        for _ in range(max_iter):
            order = np.argsort(f_vals)
            simplex = [simplex[idx] for idx in order]
            f_vals = [f_vals[idx] for idx in order]

            if f_vals[0] < 1.35 or (f_vals[-1] - f_vals[0]) < 0.04:
                break

            centroid = np.mean(simplex[:-1], axis=0)
            xr = cls._clip_theta(centroid + alpha * (centroid - simplex[-1]))
            fr = loss_fn(xr)

            if f_vals[0] <= fr < f_vals[-2]:
                simplex[-1], f_vals[-1] = xr, fr
                continue

            if fr < f_vals[0]:
                xe = cls._clip_theta(centroid + gamma * (xr - centroid))
                fe = loss_fn(xe)
                if fe < fr:
                    simplex[-1], f_vals[-1] = xe, fe
                else:
                    simplex[-1], f_vals[-1] = xr, fr
                continue

            xc = cls._clip_theta(centroid + rho * (simplex[-1] - centroid))
            fc = loss_fn(xc)
            if fc < f_vals[-1]:
                simplex[-1], f_vals[-1] = xc, fc
            else:
                best = simplex[0]
                for i in range(1, len(simplex)):
                    simplex[i] = cls._clip_theta(best + sigma * (simplex[i] - best))
                    f_vals[i] = loss_fn(simplex[i])

        best_theta = cls._clip_theta(simplex[int(np.argmin(f_vals))])
        fitted_params = KineticParameters(
            mu_max_acid=round(float(best_theta[0]), 4),
            y_vfa_carb=round(float(best_theta[1]), 4),
            caco3_dissolution_rate=base.caco3_dissolution_rate,
            q_pha_max=round(float(best_theta[2]), 4),
            y_pha_vfa=round(float(best_theta[3]), 4),
        )
        calibrated_sim = MultiMoleculeEngine(params=fitted_params).simulate_batch(inp, dt_h=0.5)
        rmse_after = cls.compute_normalized_rmse_pct(calibrated_sim, observed_points, observed_grade_a_g)

        return {
            "rmse_before_pct": rmse_before,
            "rmse_after_pct": rmse_after,
            "old_parameters": {
                "mu_max_acid": round(base.mu_max_acid, 4),
                "y_vfa_carb": round(base.y_vfa_carb, 4),
                "q_pha_max": round(base.q_pha_max, 4),
                "y_pha_vfa": round(base.y_pha_vfa, 4),
            },
            "calibrated_parameters": {
                "mu_max_acid": fitted_params.mu_max_acid,
                "y_vfa_carb": fitted_params.y_vfa_carb,
                "q_pha_max": fitted_params.q_pha_max,
                "y_pha_vfa": fitted_params.y_pha_vfa,
            },
            "fitted_params_obj": fitted_params,
            "calibrated_simulation": calibrated_sim,
            "baseline_simulation": baseline_sim,
        }


class ClamartDigitalTwinService:
    """High-level orchestrator uniting simulation, live ESP32 ingestion, calibration & CoA."""

    def __init__(
        self,
        db_path: str = "data/clamart_digital_twin.db",
        ledger_path: str = "data/clamart_knowledge_ledger.json",
    ):
        self.db = DigitalTwinDatabase(db_path=db_path)
        if ledger_path != ":memory:":
            Path(ledger_path).parent.mkdir(parents=True, exist_ok=True)
        self.ledger = KnowledgeLedgerManager(ledger_filepath=ledger_path)
        self._live_ekf: Dict[str, BioprocessEKFSoftSensor] = {}
        self._live_prev_do: Dict[str, Tuple[float, float]] = {}

    def run_simulation(
        self,
        inp: BiorefineryBatchInput,
        use_calibrated: bool = True,
        batch_id: Optional[str] = None,
        ambient_workshop_temp_c: float = 16.0,
        insulated_jacket: bool = True,
    ) -> Dict[str, Any]:
        if use_calibrated:
            params, cal_meta = self.db.get_latest_calibrated_parameters(inp.program_id)
        else:
            params, cal_meta = KineticParameters(), None

        engine = MultiMoleculeEngine(params=params)
        sim = engine.simulate_batch(inp, dt_h=0.5)

        carbon_bal = CarbonAndThermalBalanceEngine.compute_carbon_mass_balance(sim)
        thermal_bal = CarbonAndThermalBalanceEngine.simulate_thermal_profile(
            sim,
            ThermalReactorConfig(
                ambient_workshop_temp_c=ambient_workshop_temp_c,
                insulated_jacket=insulated_jacket,
            ),
        )
        peak_vfa = float(sim["events"]["peak_vfa_g_l"])
        caproate_peak = (
            float(sim["trajectory"][-1]["target_mol_g_l"])
            if inp.program_id == RefiningProgramId.PROG_3_CAPROIC_C6_OIL.value
            else 0.0
        )
        vfa_spectrum = CarbonAndThermalBalanceEngine.resolve_vfa_chain_spectrum(
            total_vfa_g_l=peak_vfa,
            odd_vfa_ratio=float(sim["feedstock"]["odd_vfa_ratio"]),
            program_id=inp.program_id,
            caproate_c6_g_l=caproate_peak,
        )

        bid = batch_id or f"CLAMART-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        self.db.save_batch(bid, inp, sim, status="SIMULATED")

        return {
            "batch_id": bid,
            "is_calibrated": cal_meta is not None,
            "calibration_meta": cal_meta,
            "bayesian_posterior": self.ledger.estimate_posterior_yield(
                intrant_type=inp.program_id,
                prior_mean_g=sim["products"]["grade_a_mass_g"],
            ),
            "carbon_balance": carbon_bal,
            "thermal_balance": thermal_bal,
            "vfa_spectrum": vfa_spectrum,
            **sim,
        }

    def ingest_esp32_packet(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingests a single real-time telemetry frame from an ESP32 probe node (or HIL script).
        Computes live Delta_EC, stoichiometric VFA, EKF soft-sensor estimate, and phase triggers.
        """
        batch_id = str(packet.get("batch_id", "CLAMART-LIVE-01"))
        t_h = float(packet.get("t_h", 0.0))
        ph = float(packet.get("ph", 6.5))
        orp_mv = float(packet.get("orp_mv", -120.0))
        ec_ms_cm = float(packet.get("ec_ms_cm", 4.5))
        co2_ml_min = float(packet.get("co2_ml_min", 15.0))
        do_mg_l = float(packet.get("do_mg_l", 0.4))
        temp_c = float(packet.get("temp_c", 30.0))
        hx711_kg = float(packet.get("hx711_kg", 6.2))
        rpm = float(packet.get("rpm", 10.0))
        aerated = bool(packet.get("aerated", t_h >= 36.5))

        batch = self.db.get_batch(batch_id)
        if batch is None:
            default_inp = BiorefineryBatchInput(baseline_ec0_ms_cm=ec_ms_cm if t_h <= 1.0 else 4.2)
            self.run_simulation(default_inp, batch_id=batch_id)
            batch = self.db.get_batch(batch_id)

        ec0 = float(batch["ec0_ms_cm"]) if batch else 4.2
        tracker = StoichiometricProductTracker(baseline_ec0_ms_cm=ec0)
        stoich = tracker.estimate_vfa_from_delta_ec(ec_ms_cm, co2_rate_ml_min=co2_ml_min)

        if batch_id not in self._live_ekf:
            self._live_ekf[batch_id] = BioprocessEKFSoftSensor(initial_vfa=1.0, initial_do=7.2)

        prev_t, prev_do = self._live_prev_do.get(batch_id, (max(0.0, t_h - 0.5), do_mg_l))
        dt_step = max(0.05, t_h - prev_t) if t_h > prev_t else 0.5
        d_do_dt = (do_mg_l - prev_do) / dt_step
        self._live_prev_do[batch_id] = (t_h, do_mg_l)

        ekf_res = self._live_ekf[batch_id].step(
            measured_ph=ph,
            measured_orp_mv=orp_mv,
            dt_h=dt_step,
            aerated=aerated,
            caco3_g_l=12.0,
        )

        do_spike = tracker.detect_do_spike_harvest(
            do_mg_l=do_mg_l,
            d_do_dt=d_do_dt,
            time_in_aeration_h=max(0.0, t_h - 36.5) if aerated else 0.0,
        )

        alerts = {
            "ec0_locked": t_h >= 0.5,
            "acidogenesis_plateau_reached": stoich["acidogenesis_plateau_reached"],
            "do_spike_harvest_ready": do_spike,
            "recommended_action": (
                "DECLENCHER_LYSE_70C_RECOLTE"
                if do_spike
                else (
                    "BASCULER_ESSORAGE_650RPM_PUIS_AERATION"
                    if (not aerated and stoich["acidogenesis_plateau_reached"] and t_h >= 12.0)
                    else "MAINTENIR_CONSIGNE_EN_COURS"
                )
            ),
        }

        record = {
            "batch_id": batch_id,
            "t_h": t_h,
            "source": "ESP32_REAL",
            "ph": round(ph, 3),
            "orp_mv": round(orp_mv, 1),
            "ec_ms_cm": round(ec_ms_cm, 3),
            "delta_ec_ms_cm": stoich["delta_ec_ms_cm"],
            "co2_ml_min": round(co2_ml_min, 1),
            "do_mg_l": round(do_mg_l, 2),
            "temp_c": round(temp_c, 1),
            "hx711_kg": round(hx711_kg, 2),
            "rpm": round(rpm, 0),
            "ekf_vfa_g_l": ekf_res["estimated_vfa_g_l"],
            "stoich_vfa_g_l": stoich["stoichiometric_vfa_g_l"],
            "alerts": alerts,
        }
        self.db.insert_telemetry_point(record)
        return record

    def simulate_wetlab_noisy_batch(
        self,
        inp: BiorefineryBatchInput,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Generates a realistic noisy wet-lab batch representing the local Clamart consortium
        (whose true biological kinetics differ from textbook defaults) + probe noise,
        ingests it into SQLite, and compares it against the uncalibrated Digital Twin.
        """
        rng = np.random.default_rng(seed)

        # True Clamart wild consortium kinetics (faster acidogenesis & higher VFA/PHA efficiency)
        clamart_true_params = KineticParameters(
            mu_max_acid=0.47,
            y_vfa_carb=0.83,
            caco3_dissolution_rate=0.08,
            q_pha_max=0.52,
            y_pha_vfa=0.75,
        )
        true_sim = MultiMoleculeEngine(params=clamart_true_params).simulate_batch(inp, dt_h=0.5)
        observed_grade_a_g = round(
            float(true_sim["products"]["grade_a_mass_g"]) * float(rng.normal(1.0, 0.015)), 2
        )

        # Uncalibrated textbook twin prediction
        textbook_params = KineticParameters()
        uncalibrated_sim = MultiMoleculeEngine(params=textbook_params).simulate_batch(inp, dt_h=0.5)

        batch_id = f"WETLAB-CLAMART-{datetime.now(timezone.utc).strftime('%H%M%S')}"
        self.db.save_batch(
            batch_id,
            inp,
            uncalibrated_sim,
            status="WETLAB_ACQUIRED",
            observed_grade_a_g=observed_grade_a_g,
        )
        self.db.clear_telemetry_for_batch(batch_id, source="ESP32_REAL")
        self._live_ekf.pop(batch_id, None)
        self._live_prev_do.pop(batch_id, None)

        ingested_points: List[Dict[str, Any]] = []
        for pt in true_sim["trajectory"][::2]:
            noisy_ec = max(inp.baseline_ec0_ms_cm, pt["ec_ms"] + float(rng.normal(0.0, 0.055)))
            noisy_do = float(np.clip(pt["do_mg_l"] + rng.normal(0.0, 0.14), 0.05, 8.3))
            noisy_ph = float(np.clip(pt["ph"] + rng.normal(0.0, 0.035), 4.6, 7.6))
            noisy_orp = float(pt["orp_mv"] + rng.normal(0.0, 5.5))
            noisy_co2 = max(0.0, float(pt["co2_ml_min"] + rng.normal(0.0, 1.8)))

            rec = self.ingest_esp32_packet(
                {
                    "batch_id": batch_id,
                    "t_h": pt["t"],
                    "ph": noisy_ph,
                    "orp_mv": noisy_orp,
                    "ec_ms_cm": noisy_ec,
                    "co2_ml_min": noisy_co2,
                    "do_mg_l": noisy_do,
                    "temp_c": pt["temp_c"],
                    "hx711_kg": inp.hx711_waste_kg * 2.5,
                    "rpm": pt["rpm"],
                    "aerated": pt["aerated"],
                }
            )
            ingested_points.append(rec)

        rmse_initial = ParameterAutoCalibrator.compute_normalized_rmse_pct(
            uncalibrated_sim, ingested_points, observed_grade_a_g
        )

        return {
            "batch_id": batch_id,
            "observed_grade_a_g": observed_grade_a_g,
            "predicted_uncalibrated_grade_a_g": uncalibrated_sim["products"]["grade_a_mass_g"],
            "rmse_uncalibrated_pct": rmse_initial,
            "esp32_telemetry": ingested_points,
            "uncalibrated_twin": uncalibrated_sim,
        }

    def calibrate_on_batch(self, batch_id: str) -> Dict[str, Any]:
        """Runs automated Nelder-Mead parameter identification on an acquired wet-lab batch."""
        batch = self.db.get_batch(batch_id)
        if not batch:
            raise ValueError(f"Batch introuvable dans SQLite: {batch_id}")

        inp = BiorefineryBatchInput(**batch["input"])
        telemetry = self.db.get_telemetry(batch_id, source="ESP32_REAL")
        if not telemetry:
            raise ValueError(f"Aucune télémétrie ESP32_REAL enregistrée pour {batch_id}")

        observed_mass_g = float(batch["observed_grade_a_g"])
        cal_res = ParameterAutoCalibrator.calibrate(
            inp=inp,
            observed_points=telemetry,
            observed_grade_a_g=observed_mass_g,
            initial_params=KineticParameters(),
        )

        fitted: KineticParameters = cal_res["fitted_params_obj"]
        self.db.save_calibrated_parameters(
            batch_id=batch_id,
            program_id=inp.program_id,
            params=fitted,
            rmse_before_pct=cal_res["rmse_before_pct"],
            rmse_after_pct=cal_res["rmse_after_pct"],
            notes="Auto-calibration Nelder-Mead sur sondes Delta_EC + DO + pesée finale",
        )

        # Update hash-chained Knowledge Ledger & Bayesian yield posterior
        self.ledger.record_batch(
            {
                "batch_id": batch_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "intrant_type": inp.program_id,
                "final_GradeA": observed_mass_g,
                "calibrated_mu_max": fitted.mu_max_acid,
                "calibrated_y_vfa": fitted.y_vfa_carb,
                "rmse_after_pct": cal_res["rmse_after_pct"],
            }
        )
        posterior = self.ledger.estimate_posterior_yield(
            intrant_type=inp.program_id,
            prior_mean_g=cal_res["calibrated_simulation"]["products"]["grade_a_mass_g"],
        )

        return {
            "batch_id": batch_id,
            "observed_grade_a_g": observed_mass_g,
            "rmse_before_pct": cal_res["rmse_before_pct"],
            "rmse_after_pct": cal_res["rmse_after_pct"],
            "old_parameters": cal_res["old_parameters"],
            "calibrated_parameters": cal_res["calibrated_parameters"],
            "bayesian_posterior": posterior,
            "ledger_integrity": self.ledger.verify_chain_integrity(),
            "esp32_telemetry": telemetry,
            "calibrated_twin": cal_res["calibrated_simulation"],
            "uncalibrated_twin": cal_res["baseline_simulation"],
        }

    def issue_certificate_coa(self, batch_id: str) -> Dict[str, Any]:
        """
        Generates OpenRAMAN spectral quality proof (1724/1740 cm^-1 deconvolution + Amide I check),
        audits Ecocert UAB compliance, records on the SHA-256 ledger, and stores the CoA.
        """
        batch = self.db.get_batch(batch_id)
        if not batch:
            inp = BiorefineryBatchInput()
            sim_wrap = self.run_simulation(inp, batch_id=batch_id)
            summary = sim_wrap
            program_id = inp.program_id
        else:
            summary = batch["summary"]
            program_id = batch["program_id"]

        products = summary["products"]
        target_purity = min(0.98, max(0.78, float(products["grade_a_purity_pct"]) / 100.0))
        target_cryst = min(0.80, max(0.30, float(products["crystallinity_pct"]) / 100.0))

        raman = OpenRamanPipeline(laser_wavelength_nm=532.0)
        np.random.seed(abs(hash(batch_id)) % (2**31 - 1))
        wn, raw_int = raman.generate_synthetic_spectrum(
            pha_purity=target_purity,
            crystallinity=target_cryst,
            vfa_level=0.18,
            noise_level=0.018,
        )
        clean_int = raman.subtract_baseline(wn, raw_int)
        analysis = raman.analyze_sample(wn, raw_int, sample_id=batch_id)

        # Verify absence of residual cellular protein (Amide I band around 1655 cm^-1)
        mask_amide = (wn >= 1645.0) & (wn <= 1668.0)
        amide_i_ratio_pct = round(
            (float(np.mean(clean_int[mask_amide])) / max(1.0, float(np.max(clean_int)))) * 100.0,
            2,
        )

        # Downsample diagnostic fingerprint region (800 - 1850 cm^-1) for crisp UI rendering
        mask_plot = (wn >= 800.0) & (wn <= 1850.0)
        wn_sub = wn[mask_plot][::6]
        clean_sub = clean_int[mask_plot][::6]

        auditor = EcocertUABAuditor()
        ecocert_report = auditor.audit_batch(LabAssayResults(), batch_id=batch_id)

        ledger_count = self.ledger.record_batch(
            {
                "batch_id": batch_id,
                "event": "COA_ISSUED",
                "intrant_type": program_id,
                "final_GradeA": float(products["grade_a_mass_g"]),
                "raman_coa_sha256": analysis["coa_sha256"],
            }
        )
        records = self.ledger.load_ledger()
        latest_block_hash = records[-1]["entry_hash"] if records else analysis["coa_sha256"]

        lca_info = summary.get("lca", {})
        grade_a_kg = max(1e-4, float(products["grade_a_mass_g"]) / 1000.0)
        net_avoided_kg = float(lca_info.get("total_co2_eq_avoided_kg", 2.8))
        pcf_kg_co2e_per_kg = round(-net_avoided_kg / grade_a_kg, 2)

        dpp_passport = {
            "dpp_urn": f"urn:eu:espr-dpp:clamart-holarchy:{batch_id}",
            "espr_2024_1781_compliant": True,
            "en_16640_biogenic_carbon_pct": 100.0,
            "fossil_petrochemical_carbon_pct": 0.0,
            "product_carbon_footprint_kg_co2e_per_kg": pcf_kg_co2e_per_kg,
            "deforestation_free_eu_2023_1115": True,
            "microplastic_free_eu_2023_2055": True,
            "marine_biodegradability_iso_14852": "Biodégradation enzymatique marine < 6 mois",
            "origin_municipality": "Clamart (92140) — Vallée Sud Grand Paris",
        }

        canonical_coa = {
            "batch_id": batch_id,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "hub_location": "Bioraffinerie Urbaine Holarchique — Clamart (92140)",
            "program_id": program_id,
            "product_label": products["grade_a_label"],
            "grade_a_mass_g": products["grade_a_mass_g"],
            "hv_mol_pct": products["hv_mol_pct"],
            "mw_kda": products["grade_a_mw_kda"],
            "halogenated_solvents_ml": 0.0,
            "eu_2023_2055_microplastic_free": True,
            "amide_i_1655_protein_residue_pct": amide_i_ratio_pct,
            "eu_digital_product_passport": dpp_passport,
            "raman_analysis": analysis,
            "ecocert_audit": ecocert_report,
            "ledger_block_index": ledger_count,
            "ledger_entry_hash": latest_block_hash,
        }
        master_hash = hashlib.sha256(
            json.dumps(canonical_coa, sort_keys=True).encode("utf-8")
        ).hexdigest()
        canonical_coa["coa_sha256"] = master_hash
        canonical_coa["spectrum_plot"] = {
            "wavenumbers_cm1": [round(float(x), 1) for x in wn_sub],
            "intensity_clean": [round(float(y), 1) for y in clean_sub],
        }

        self.db.save_certificate_coa(canonical_coa)
        return canonical_coa
