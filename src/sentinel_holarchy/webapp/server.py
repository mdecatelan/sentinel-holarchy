"""
Local Web Server (http://127.0.0.1:8080) for the Clamart Biorefinery Digital Twin v2.0.
Connects the interactive Cockpit UI & ESP32 hardware nodes to all Python Holons + SQLite.
"""

import json
import math
from http.server import HTTPStatus, BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Any, Optional

from sentinel_holarchy.holon0_microbial.kinetics import Holon0Engine, MicrobialState
from sentinel_holarchy.holon0_microbial.multi_molecules import (
    BiorefineryBatchInput,
    MultiMoleculeEngine,
    RefiningProgramId,
)
from sentinel_holarchy.holon1_hardware.auto_dosing import (
    DumpAndGoTelemetry,
    BlindFeedstockInferencer,
    PassiveBufferCartridge,
)
from sentinel_holarchy.holon1_hardware.pid_controller import HydrodynamicShearModel
from sentinel_holarchy.holon1_hardware.soft_sensor import BioprocessEKFSoftSensor
from sentinel_holarchy.holon3_intelligence.digital_twin import ClamartDigitalTwinService


# Singleton Digital Twin v2.0 service backed by local SQLite & SHA-256 Knowledge Ledger
DEFAULT_TWIN_SERVICE: Optional[ClamartDigitalTwinService] = None


def get_twin_service() -> ClamartDigitalTwinService:
    global DEFAULT_TWIN_SERVICE
    if DEFAULT_TWIN_SERVICE is None:
        DEFAULT_TWIN_SERVICE = ClamartDigitalTwinService()
    return DEFAULT_TWIN_SERVICE


def parse_batch_input(payload: Dict[str, Any]) -> BiorefineryBatchInput:
    return BiorefineryBatchInput(
        program_id=str(
            payload.get("program_id", RefiningProgramId.PROG_1_PHBV_COSMETIC_PIEZO.value)
        ),
        hx711_waste_kg=float(payload.get("hx711_waste_kg", 2.50)),
        brown_starch_ratio=float(payload.get("brown_starch_ratio", 0.33)),
        baseline_ec0_ms_cm=float(payload.get("baseline_ec0_ms_cm", 4.20)),
        cartridge_caco3_g=float(payload.get("cartridge_caco3_g", 250.0)),
        coffee_grounds_fraction=float(payload.get("coffee_grounds_fraction", 0.25)),
    )


def run_python_simulation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy v1 simulation wrapper preserved for backward compatibility."""
    gross_waste_kg = float(payload.get("gross_waste_kg", 1.15))
    motor_ma = float(payload.get("motor_current_ma", 580.0))
    ec_ms = float(payload.get("conductivity_ec_ms_cm", 4.2))
    orp_drop = float(payload.get("initial_orp_drop_mv_h", -115.0))
    cartridge_init_g = float(payload.get("cartridge_mass_g", 220.0))

    signals = DumpAndGoTelemetry(
        hx711_gross_waste_kg=gross_waste_kg,
        motor_current_ma_at_45rpm=motor_ma,
        conductivity_ec_ms_cm=ec_ms,
        initial_orp_drop_mv_per_h=orp_drop,
        initial_ph_drop_per_h=-0.35,
    )
    inferred = BlindFeedstockInferencer.infer_composition_from_maceration(signals)
    vol_l = inferred["effective_liquid_volume_l"]
    caco3_g_l = cartridge_init_g / vol_l

    engine = Holon0Engine()
    shear_model = HydrodynamicShearModel(liquid_volume_l=vol_l)
    ekf = BioprocessEKFSoftSensor(initial_vfa=1.0, initial_do=7.0)

    state = MicrobialState(
        time_h=0.0,
        carbohydrates_g_l=inferred["inferred_carbohydrates_g_l"],
        vfa_g_l=1.0,
        nitrogen_g_l=inferred["inferred_nitrogen_g_l"],
        caco3_g_l=caco3_g_l,
        biomass_acid_g_l=1.2,
        biomass_pha_active_g_l=0.5,
        pha_stored_g_l=0.02,
        ph=6.8,
        dissolved_oxygen_mg_l=7.2,
        odd_vfa_ratio=inferred["inferred_odd_vfa_ratio"],
    )

    trajectory = []
    dt_h = 0.5
    steps = int(73.0 / dt_h) + 1
    peak_vfa_g_l = 1.0

    for i in range(steps):
        t = round(i * dt_h, 1)
        aerated = 36.5 <= t < 72.0
        rpm = 45.0 if t < 2.0 else (8.0 if t < 36.0 else (650.0 if t < 36.5 else (15.0 if t < 72.0 else 800.0)))
        if abs(t - 36.5) < 0.01:
            state.nitrogen_g_l = max(0.05, state.nitrogen_g_l * 0.15)
            state.biomass_pha_active_g_l = max(state.biomass_pha_active_g_l, 1.35)

        peak_vfa_g_l = max(peak_vfa_g_l, state.vfa_g_l)
        orp_mv = 120.0 + 65.0 * math.log10(max(0.02, state.dissolved_oxygen_mg_l)) - 59.16 * (state.ph - 7.0) - 6.2 * state.vfa_g_l
        ekf_res = ekf.step(state.ph, orp_mv, dt_h, aerated=aerated, caco3_g_l=state.caco3_g_l)
        hydro = shear_model.evaluate_regime(rpm)

        trajectory.append(
            {
                "t": t,
                "carb": round(state.carbohydrates_g_l, 2),
                "vfa": round(state.vfa_g_l, 2),
                "pha_g_l": round(state.pha_stored_g_l, 2),
                "ph": round(state.ph, 2),
                "do_mg_l": round(state.dissolved_oxygen_mg_l, 2),
                "ekf_vfa": ekf_res["estimated_vfa_g_l"],
                "rcf_g": hydro["rcf_g_force"],
            }
        )
        state = engine.step(state, dt_h=dt_h, aerated=aerated)

    cartridge = PassiveBufferCartridge(initial_mass_g=cartridge_init_g, capacity_g=250.0)
    cartridge_status = cartridge.consume_for_batch(peak_vfa_g_l * vol_l)
    copolymer = MicrobialState(vfa_g_l=peak_vfa_g_l, odd_vfa_ratio=inferred["inferred_odd_vfa_ratio"]).predict_copolymer_properties()
    return {
        "inferred_feedstock": inferred,
        "cartridge_status": cartridge_status,
        "copolymer": {
            "hv_mol_pct": copolymer.hv_molar_fraction_pct,
            "final_pha_g": round(trajectory[-1]["pha_g_l"] * vol_l, 1),
        },
        "trajectory": trajectory,
    }


def dispatch_api_request(
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    service: Optional[ClamartDigitalTwinService] = None,
) -> tuple[HTTPStatus, Dict[str, Any]]:
    """Pure dispatcher function (testable without opening sockets)."""
    svc = service or get_twin_service()
    body = payload or {}

    if method == "GET":
        if path == "/api/twin/programs":
            params, meta = svc.db.get_latest_calibrated_parameters()
            return HTTPStatus.OK, {
                "programs": MultiMoleculeEngine.list_programs(),
                "active_parameters": {
                    "mu_max_acid": params.mu_max_acid,
                    "y_vfa_carb": params.y_vfa_carb,
                    "caco3_dissolution_rate": params.caco3_dissolution_rate,
                    "q_pha_max": params.q_pha_max,
                    "y_pha_vfa": params.y_pha_vfa,
                },
                "calibration_meta": meta,
                "recent_batches": svc.db.list_batches(limit=15),
                "ledger_integrity": svc.ledger.verify_chain_integrity(),
            }
        if path == "/api/batches":
            _, meta = svc.db.get_latest_calibrated_parameters()
            return HTTPStatus.OK, {
                "batches": svc.db.list_batches(limit=25),
                "calibration_meta": meta,
                "ledger_integrity": svc.ledger.verify_chain_integrity(),
            }
        if path == "/api/default":
            return HTTPStatus.OK, run_python_simulation({})
        return HTTPStatus.NOT_FOUND, {"error": f"Unknown GET endpoint: {path}"}

    if method == "POST":
        if path == "/api/twin/simulate":
            inp = parse_batch_input(body)
            use_cal = bool(body.get("use_calibrated", True))
            return HTTPStatus.OK, svc.run_simulation(inp, use_calibrated=use_cal)

        if path == "/api/telemetry/ingest":
            return HTTPStatus.OK, svc.ingest_esp32_packet(body)

        if path == "/api/twin/wetlab_stream":
            inp = parse_batch_input(body)
            seed = int(body.get("seed", 42))
            return HTTPStatus.OK, svc.simulate_wetlab_noisy_batch(inp, seed=seed)

        if path == "/api/twin/calibrate":
            batch_id = str(body.get("batch_id", ""))
            if not batch_id:
                return HTTPStatus.BAD_REQUEST, {"error": "batch_id requis"}
            return HTTPStatus.OK, svc.calibrate_on_batch(batch_id)

        if path == "/api/twin/reset_calibration":
            svc.db.reset_calibrations()
            return HTTPStatus.OK, {"status": "RESET_OK"}

        if path == "/api/twin/certify":
            batch_id = str(body.get("batch_id", "CLAMART-DEMO-01"))
            return HTTPStatus.OK, svc.issue_certificate_coa(batch_id)

        if path == "/api/simulate":
            return HTTPStatus.OK, run_python_simulation(body)

        return HTTPStatus.NOT_FOUND, {"error": f"Unknown POST endpoint: {path}"}

    return HTTPStatus.METHOD_NOT_ALLOWED, {"error": f"Method {method} not allowed"}


class BioDrumHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_json(self, status: HTTPStatus, data: Dict[str, Any]) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        clean_path = self.path.split("?")[0]
        if clean_path in ("/", "/index.html"):
            html_path = Path(__file__).parent / "ui_local.html"
            content = html_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        try:
            status, data = dispatch_api_request("GET", clean_path)
            self._send_json(status, data)
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_POST(self) -> None:
        clean_path = self.path.split("?")[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            payload = json.loads(raw) if raw.strip() else {}
            status, data = dispatch_api_request("POST", clean_path, payload)
            self._send_json(status, data)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})


def start_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), BioDrumHTTPHandler)
    print(f"Sentinel Holarchy Digital Twin v2.0 running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    start_server()
