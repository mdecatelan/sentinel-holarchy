"""
Holon 2: Solvent-Free Downstream PHA Extraction & Polymer Chain Scission Model.
Models green NPCM (Non-PHA Cellular Mass) digestion using thermal-osmotic shock and
mild sodium carbonate, while tracking molecular weight (Mw) degradation.
"""

from dataclasses import dataclass
from typing import Dict, Any
import math


@dataclass
class ExtractionProtocolConfig:
    lysis_temp_c: float = 70.0
    lysis_duration_min: float = 25.0
    na2co3_molarity: float = 0.08       # Mild green carbonate buffer (no chlorinated solvents)
    washing_cycles: int = 3
    centrifuge_rpm: float = 800.0
    initial_mw_kda: float = 520.0       # Native intracellular PHA molecular weight (kDa)
    initial_pdi: float = 1.85           # Polydispersity index Mw/Mn


class GreenPHAExtractor:
    """
    Simulates solvent-free extraction of intracellular PHA granules and predicts
    recovery yield, final purity, and molecular weight retention.
    """

    def __init__(self, config: ExtractionProtocolConfig = None):
        self.config = config or ExtractionProtocolConfig()

    def simulate_extraction(
        self,
        total_biomass_g: float,
        intracellular_pha_fraction: float
    ) -> Dict[str, Any]:
        """
        Computes NPCM solubilization efficiency, centrifugal recovery, and random
        ester chain scission (Kuhn-Mark-Houwink degradation kinetics).
        """
        c = self.config
        initial_pha_g = max(0.0, total_biomass_g * intracellular_pha_fraction)
        initial_npcm_g = max(0.0, total_biomass_g * (1.0 - intracellular_pha_fraction))

        # 1. NPCM Solubilization kinetics (thermal + carbonate lysis)
        temp_factor = math.exp(0.042 * (c.lysis_temp_c - 60.0))
        alkali_factor = 1.0 + 4.5 * c.na2co3_molarity
        k_lysis = 0.065 * temp_factor * alkali_factor  # min^-1

        npcm_solubilized_fraction = 1.0 - math.exp(-k_lysis * c.lysis_duration_min)
        # Each centrifugal washing cycle removes 78% of remaining suspended NPCM debris
        wash_removal = 1.0 - (0.22 ** c.washing_cycles)
        residual_npcm_g = initial_npcm_g * (1.0 - npcm_solubilized_fraction * wash_removal)

        # 2. Mechanical loss of fine PHA granules (< 0.5 um) across centrifuge mesh
        g_factor = min(1.0, (c.centrifuge_rpm / 750.0) ** 2)
        recovery_yield_pct = min(96.5, (82.0 + 14.0 * g_factor) - (1.2 * c.washing_cycles))
        recovered_pha_g = initial_pha_g * (recovery_yield_pct / 100.0)

        # 3. Final gravimetric purity
        total_pellet_dry_g = max(1e-6, recovered_pha_g + residual_npcm_g)
        final_purity_pct = (recovered_pha_g / total_pellet_dry_g) * 100.0

        # 4. Random ester chain scission (molecular weight degradation)
        # 1/DP_t - 1/DP_0 = k_scission * t
        k_scission = 1.2e-6 * math.exp(0.065 * (c.lysis_temp_c - 60.0)) * (1.0 + 8.0 * c.na2co3_molarity)
        dp_0 = (c.initial_mw_kda * 1000.0) / 86.09  # 3HB monomer unit MW = 86.09 g/mol
        inv_dp_final = (1.0 / dp_0) + k_scission * c.lysis_duration_min
        dp_final = 1.0 / inv_dp_final
        final_mw_kda = (dp_final * 86.09) / 1000.0

        return {
            "recovered_pha_g": round(recovered_pha_g, 2),
            "residual_npcm_g": round(residual_npcm_g, 2),
            "recovery_yield_pct": round(recovery_yield_pct, 1),
            "final_purity_pct": round(final_purity_pct, 1),
            "final_mw_kda": round(final_mw_kda, 1),
            "mw_retention_pct": round((final_mw_kda / c.initial_mw_kda) * 100.0, 1),
            "extrusion_grade_viable": (final_mw_kda >= 250.0 and final_purity_pct >= 85.0),
            "halogenated_solvents_used_ml": 0.0
        }
