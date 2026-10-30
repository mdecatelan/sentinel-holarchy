"""
Holon 1: Extended Kalman Filter (EKF) Soft-Sensor.
Fuses noisy low-cost electrochemical sensors (pH, ORP mV, Temperature) to estimate
internal VFA concentration (g/L) and Dissolved Oxygen (mg/L) between Raman scans.
"""

from typing import Dict, Tuple
import numpy as np
import math


class BioprocessEKFSoftSensor:
    """
    2-State Extended Kalman Filter:
      State vector x = [ VFA (g/L), DO (mg/L) ]^T
      Measurement vector z = [ pH, ORP (mV) ]^T
    """

    def __init__(self, initial_vfa: float = 2.0, initial_do: float = 6.5):
        # State estimate x_hat = [vfa, do]
        self.x = np.array([initial_vfa, initial_do], dtype=float)
        # Error covariance matrix P
        self.P = np.diag([1.5, 1.0])
        # Process noise covariance Q
        self.Q = np.diag([0.08, 0.12])
        # Measurement noise covariance R (pH variance ~ 0.02^2, ORP variance ~ 8mV^2)
        self.R = np.diag([0.0025, 64.0])

    def _measurement_model(self, x: np.ndarray, caco3_g_l: float = 8.0) -> np.ndarray:
        """Non-linear observation function h(x) mapping [VFA, DO] -> [pH, ORP_mV]."""
        vfa = max(0.05, float(x[0]))
        do = max(0.01, float(x[1]))

        # 1. Expected pH from Henderson-Hasselbalch + CaCO3 buffering
        ph_est = 4.76 - 0.45 * math.log10(vfa / 60.0) + min(caco3_g_l * 0.12, 1.8)
        ph_est = max(4.2, min(8.2, ph_est))

        # 2. Expected ORP (mV) from Nernst-like dependence on log(DO) and pH
        # E_h = E0 + 59.16 * log10(DO^0.25) - 59.16 * (pH - 7.0)
        orp_est = 120.0 + 65.0 * math.log10(do) - 59.16 * (ph_est - 7.0) - 8.5 * vfa
        return np.array([ph_est, orp_est], dtype=float)

    def _jacobian_h(self, x: np.ndarray, caco3_g_l: float = 8.0) -> np.ndarray:
        """Computes observation Jacobian H = dh/dx via analytical partial derivatives."""
        vfa = max(0.05, float(x[0]))
        do = max(0.01, float(x[1]))
        ln10 = math.log(10.0)

        # d(pH)/d(VFA) and d(pH)/d(DO)
        dph_dvfa = -0.45 / (vfa * ln10)
        dph_ddo = 0.0

        # d(ORP)/d(VFA) and d(ORP)/d(DO)
        dorp_dvfa = -59.16 * dph_dvfa - 8.5
        dorp_ddo = 65.0 / (do * ln10)

        return np.array([
            [dph_dvfa, dph_ddo],
            [dorp_dvfa, dorp_ddo]
        ], dtype=float)

    def step(
        self,
        measured_ph: float,
        measured_orp_mv: float,
        dt_h: float = 0.25,
        aerated: bool = False,
        caco3_g_l: float = 8.0
    ) -> Dict[str, float]:
        """Executes EKF Predict & Update cycle and returns filtered state estimates."""
        # --- 1. PREDICT STEP ---
        vfa_prev, do_prev = float(self.x[0]), float(self.x[1])
        if not aerated:
            # Acidogenesis drift: VFA slowly rises, DO decays
            vfa_pred = vfa_prev + 0.45 * dt_h
            do_pred = max(0.05, do_prev * math.exp(-1.2 * dt_h))
            F = np.array([[1.0, 0.0], [0.0, math.exp(-1.2 * dt_h)]])
        else:
            # Feast phase: VFA consumed, DO replenished toward saturation
            vfa_pred = max(0.05, vfa_prev * math.exp(-0.08 * dt_h))
            do_pred = do_prev + 4.0 * (7.8 - do_prev) * dt_h
            F = np.array([[math.exp(-0.08 * dt_h), 0.0], [0.0, max(0.1, 1.0 - 4.0 * dt_h)]])

        x_pred = np.array([vfa_pred, max(0.05, min(8.5, do_pred))], dtype=float)
        P_pred = F @ self.P @ F.T + self.Q

        # --- 2. UPDATE STEP ---
        z = np.array([measured_ph, measured_orp_mv], dtype=float)
        z_hat = self._measurement_model(x_pred, caco3_g_l=caco3_g_l)
        y_residual = z - z_hat

        H = self._jacobian_h(x_pred, caco3_g_l=caco3_g_l)
        S = H @ P_pred @ H.T + self.R
        K = P_pred @ H.T @ np.linalg.inv(S)

        self.x = x_pred + K @ y_residual
        self.x[0] = max(0.05, min(45.0, float(self.x[0])))
        self.x[1] = max(0.02, min(9.0, float(self.x[1])))
        self.P = (np.eye(2) - K @ H) @ P_pred

        return {
            "estimated_vfa_g_l": round(float(self.x[0]), 2),
            "estimated_do_mg_l": round(float(self.x[1]), 2),
            "vfa_uncertainty_std": round(math.sqrt(max(0.0, float(self.P[0, 0]))), 3),
            "do_uncertainty_std": round(math.sqrt(max(0.0, float(self.P[1, 1]))), 3)
        }
