"""
Local Web Server (http://localhost:8080) for the Sentinel Holarchy Bio-Drum Digital Twin.
Connects the browser UI directly to the Python Holons (Holon 0, Holon 1, Holon 2, Holon 3).
"""

import json
import math
from http.server import HTTPStatus, BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Any

from sentinel_holarchy.holon0_microbial.kinetics import Holon0Engine, MicrobialState
from sentinel_holarchy.holon0_microbial.metabolic_flux import PHBVCopolymerModel, VFAProfile
from sentinel_holarchy.holon1_hardware.auto_dosing import (
    DumpAndGoTelemetry,
    BlindFeedstockInferencer,
    PassiveBufferCartridge,
)
from sentinel_holarchy.holon1_hardware.pid_controller import HydrodynamicShearModel
from sentinel_holarchy.holon1_hardware.soft_sensor import BioprocessEKFSoftSensor


def run_python_simulation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the full 73h Python simulation from a 'Dump & Go' bucket throw
    or custom sensor signals.
    """
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
    fault = False

    for i in range(steps):
        t = round(i * dt_h, 1)

        if t < 2.0:
            fsm_state = "1_MACERATION_AUTO_DIAGNOSTIC"
            rpm = 45.0
            temp_c = 28.0
            aerated = False
            valve_vfa = False
            valve_drain = False
        elif t < 36.0:
            fsm_state = "2_ACIDOGENESE_ANAEROBIE"
            rpm = 8.0
            temp_c = 30.0
            aerated = False
            valve_vfa = False
            valve_drain = False
        elif t < 36.5:
            fsm_state = "3_ESSORAGE_CENTRIFUGE_650RPM"
            rpm = 650.0
            temp_c = 25.0
            aerated = False
            valve_vfa = True
            valve_drain = False
        elif t < 72.0:
            fsm_state = "4_GAVAGE_AEROBIE_PHA"
            rpm = 15.0
            temp_c = 26.0
            aerated = True
            valve_vfa = False
            valve_drain = False
        else:
            fsm_state = "5_LYSE_THERMIQUE_RECOLTE_70C"
            rpm = 800.0
            temp_c = 70.0
            aerated = False
            valve_vfa = False
            valve_drain = True

        if abs(t - 36.5) < 0.01:
            state.nitrogen_g_l = max(0.05, state.nitrogen_g_l * 0.15)
            state.biomass_pha_active_g_l = max(state.biomass_pha_active_g_l, 1.35)

        if state.caco3_g_l < 0.3 and state.vfa_g_l > 14.0:
            state.ph = max(3.9, state.ph - (state.vfa_g_l - 14.0) * 0.05)

        if state.ph < 4.25:
            fault = True
            fsm_state = "FAULT_ALARME_CHOC_ACIDE"
            rpm = 0.0
            aerated = False

        hvfa = engine.calculate_undissociated_vfa(state.vfa_g_l, state.ph)
        peak_vfa_g_l = max(peak_vfa_g_l, state.vfa_g_l)

        # Simulated ORP mV sensor signal
        orp_mv = 120.0 + 65.0 * math.log10(max(0.02, state.dissolved_oxygen_mg_l)) - 59.16 * (state.ph - 7.0) - 6.2 * state.vfa_g_l
        if not aerated and 2.0 <= t < 36.5:
            orp_mv = min(-165.0, orp_mv - 85.0)
        elif aerated:
            orp_mv = 148.0 + (7.0 - state.ph) * 22.0 + (state.dissolved_oxygen_mg_l - 6.0) * 12.0
        orp_mv = max(-340.0, min(240.0, orp_mv))

        ekf_res = ekf.step(
            measured_ph=state.ph,
            measured_orp_mv=orp_mv,
            dt_h=dt_h,
            aerated=aerated,
            caco3_g_l=state.caco3_g_l,
        )
        hydro = shear_model.evaluate_regime(rpm)

        trajectory.append({
            "t": t,
            "fsm_state": fsm_state,
            "carb": round(state.carbohydrates_g_l, 2),
            "vfa": round(state.vfa_g_l, 2),
            "hvfa": round(hvfa, 2),
            "caco3_g_l": round(state.caco3_g_l, 2),
            "pha_g_l": round(state.pha_stored_g_l, 2),
            "pha_pct": round(state.pha_fraction * 100.0, 1),
            "ph": round(state.ph, 2),
            "orp_mv": round(orp_mv, 0),
            "do_mg_l": round(state.dissolved_oxygen_mg_l, 2),
            "temp_c": round(temp_c, 1),
            "rpm": round(rpm, 0),
            "motor_ma": round(motor_ma if t < 2.0 else (310.0 + rpm * 1.45), 0),
            "ec_ms": round(ec_ms + state.vfa_g_l * 0.08, 2),
            "lambda_k_um": hydro["kolmogorov_scale_um"],
            "rcf_g": hydro["rcf_g_force"],
            "ekf_vfa": ekf_res["estimated_vfa_g_l"],
            "ekf_vfa_std": ekf_res["vfa_uncertainty_std"],
            "ekf_do": ekf_res["estimated_do_mg_l"],
            "aerated": aerated,
            "valve_vfa": valve_vfa,
            "valve_drain": valve_drain,
            "fault": fault,
        })

        if not fault:
            state = engine.step(state, dt_h=dt_h, aerated=aerated)

    cartridge = PassiveBufferCartridge(initial_mass_g=cartridge_init_g, capacity_g=250.0)
    cartridge_status = cartridge.consume_for_batch(peak_vfa_g_l * vol_l)

    peak_state = MicrobialState(vfa_g_l=peak_vfa_g_l, odd_vfa_ratio=inferred["inferred_odd_vfa_ratio"])
    copolymer = peak_state.predict_copolymer_properties()
    final_pt = trajectory[-1]

    return {
        "inferred_feedstock": inferred,
        "cartridge_status": cartridge_status,
        "copolymer": {
            "hv_mol_pct": copolymer.hv_molar_fraction_pct,
            "tm_c": copolymer.melting_temp_c,
            "tg_c": copolymer.glass_transition_temp_c,
            "crystallinity_pct": copolymer.crystallinity_pct,
            "d33_pc_n": copolymer.piezoelectric_d33_pc_n,
            "application": copolymer.recommended_application,
            "final_pha_g": round(final_pt["pha_g_l"] * vol_l, 1),
        },
        "trajectory": trajectory,
    }


class BioDrumHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            html_path = Path(__file__).parent / "ui_local.html"
            content = html_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/api/default":
            data = run_python_simulation({})
            body = json.dumps(data).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        if self.path == "/api/simulate":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            payload = json.loads(raw)
            data = run_python_simulation(payload)
            body = json.dumps(data).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")


def start_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), BioDrumHTTPHandler)
    print(f"Sentinel Holarchy Local Server running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    start_server()
