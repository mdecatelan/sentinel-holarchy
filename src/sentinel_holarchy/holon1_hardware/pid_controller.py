"""
Holon 1: Anti-Windup PID Controller & Hydrodynamic Shear / Kolmogorov Microscale Analyzer.
Provides closed-loop actuator regulation and prevents mechanical cell lysis during mixing.
"""

from dataclasses import dataclass
from typing import Dict
import math


@dataclass
class PIDGains:
    kp: float = 2.5
    ki: float = 0.45
    kd: float = 0.15
    output_min: float = 0.0
    output_max: float = 100.0
    integral_limit: float = 50.0


class AntiWindupPID:
    """Discrete-time PID controller with clamping anti-windup and derivative filtering."""

    def __init__(self, gains: PIDGains = None, setpoint: float = 28.0):
        self.gains = gains or PIDGains()
        self.setpoint = setpoint
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_d_filtered = 0.0

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_d_filtered = 0.0

    def compute(self, measurement: float, dt: float) -> float:
        if dt <= 0.0:
            return 0.0

        g = self.gains
        error = self.setpoint - measurement

        # Proportional term
        p_term = g.kp * error

        # Derivative term with low-pass filter (alpha = 0.7)
        raw_d = (error - self._prev_error) / dt
        d_filtered = 0.7 * raw_d + 0.3 * self._prev_d_filtered
        d_term = g.kd * d_filtered

        # Provisional integral update with clamping anti-windup
        new_integral = self._integral + error * dt
        new_integral = max(-g.integral_limit, min(g.integral_limit, new_integral))
        i_term = g.ki * new_integral

        raw_out = p_term + i_term + d_term
        clamped_out = max(g.output_min, min(g.output_max, raw_out))

        # Back-calculation check: only integrate if not saturating in same direction
        if not ((raw_out >= g.output_max and error > 0) or (raw_out <= g.output_min and error < 0)):
            self._integral = new_integral

        self._prev_error = error
        self._prev_d_filtered = d_filtered
        return round(clamped_out, 2)


class HydrodynamicShearModel:
    """
    Computes Kolmogorov microscale of turbulence (lambda_K) and centrifugal G-force
    inside the 60L horizontal perforated inox drum.
    """

    def __init__(
        self,
        drum_diameter_m: float = 0.48,
        liquid_volume_l: float = 45.0,
        kinematic_viscosity_m2_s: float = 1.15e-6,
        power_number_np: float = 0.85
    ):
        self.drum_diameter_m = drum_diameter_m
        self.liquid_volume_m3 = max(0.001, liquid_volume_l / 1000.0)
        self.nu = kinematic_viscosity_m2_s
        self.np = power_number_np

    def evaluate_regime(self, rpm: float) -> Dict[str, float]:
        """
        Calculates Reynolds number, specific power dissipation epsilon (W/kg),
        Kolmogorov length scale (micrometers), and Relative Centrifugal Force (g).
        """
        n_rps = max(0.01, rpm / 60.0)
        d = self.drum_diameter_m
        radius_cm = (d / 2.0) * 100.0

        # Impeller/Drum Reynolds number: Re = N * D^2 / nu
        reynolds = (n_rps * (d ** 2)) / self.nu

        # Power dissipated per unit mass (W/kg = m^2 / s^3): epsilon = P / (rho * V)
        power_watts = self.np * 1015.0 * (n_rps ** 3) * (d ** 5)
        epsilon = max(1e-8, power_watts / (1015.0 * self.liquid_volume_m3))

        # Kolmogorov microscale: lambda_K = (nu^3 / epsilon)^(1/4)
        lambda_k_m = ((self.nu ** 3) / epsilon) ** 0.25
        lambda_k_um = lambda_k_m * 1e6

        # Relative Centrifugal Force (RCF in g): 1.118e-5 * r_cm * RPM^2
        rcf_g = 1.118e-5 * radius_cm * (rpm ** 2)

        # Typical MMC bacterial floc size is 80-150 um; eddy damage occurs if lambda_K < 65 um
        floc_safe = lambda_k_um >= 65.0

        return {
            "rpm": round(rpm, 1),
            "reynolds_number": round(reynolds, 0),
            "power_input_w": round(power_watts, 2),
            "kolmogorov_scale_um": round(lambda_k_um, 1),
            "rcf_g_force": round(rcf_g, 2),
            "floc_integrity_safe": floc_safe
        }
