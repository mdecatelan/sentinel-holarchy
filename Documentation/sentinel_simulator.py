"""
================================================================================
  SENTINEL-ALGAE | SYSTEME DE MONDE MECANISTE ET APPRENANT V16
  Convertisseur Universel Bacterien & Bio-Fonderie Urbaine (White-Box Model)
================================================================================
Ce module implemente le modele de dynamique de systeme mecaniste V16 (boite de verre).
Chaque equation et constante reflete un phenomene biophysique reel, auditable.
Il integre :
- Un registre d'experience persistant (knowledge_ledger.json) pour l'apprentissage.
- Une tresorerie operationnelle active (C_cap) affectee par les couts et ventes.
- Une pollution locale accumulee (P_env) induisant un drag toxique sur les souches.
- Un cisaillement mecanique cellulaire (shear_drag) induit par l'agitation RPM.
- L'auditabilite totale de l'etat causale via l'endpoint /api/audit.

Auteur: Antigravity (Advanced Agentic Coding - Google DeepMind Team)
Date: Mai 2026
"""

import math
import os
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import urllib.parse

LEDGER_FILE = "knowledge_ledger.json"

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class SentinelSimulator:
    def __init__(self, intrant_type="algues"):
        """
        Initialise le simulateur mecaniste V16.
        intrant_type: "algues", "organique" ou "e_waste"
        """
        self.intrant_type = intrant_type.lower()
        self.set_default_parameters()
        self.reset_state()
        self.load_experience()

    def set_default_parameters(self):
        """Definit les parametres cinetiques, stoechiometriques et physiques de base."""
        # --- Parametres Physiques Communs ---
        self.C_heat = 4.184 * 100  # Capacite thermique (kJ/C pour 100L)
        self.h_loss = 0.05        # Perte thermique passive (kW/C)
        self.T_amb = 20.0          # Température ambiante (C)
        self.N_rpm = 15.0          # Vitesse de rotation (rpm)
        self.theta = 45.0          # Angle d'inclinaison (degres)
        
        # --- Prix du marche des Grades (Euros par gramme, Or en mg) ---
        if self.intrant_type == "e_waste":
            self.price_A = 0.065   # Grade A: Or pur solubilise (0.065 EUR/mg)
            self.price_B = 3.50    # Grade B: Oligo-elements purs (3.50 EUR/g)
            self.price_C = 0.80    # Grade C: Cuivre lixivie (0.80 EUR/g)
        elif self.intrant_type == "organique":
            self.price_A = 12.00   # Grade A: Solvants PHA (12.00 EUR/g)
            self.price_B = 2.50    # Grade B: Fertilisant azote (2.50 EUR/g)
            self.price_C = 0.50    # Grade C: Digestat solide (0.50 EUR/g)
        else: # algues
            self.price_A = 22.00   # Grade A: Fucoidanes nobles (22.00 EUR/g)
            self.price_B = 3.00    # Grade B: Biostimulant (3.00 EUR/g)
            self.price_C = 0.60    # Grade C: Amendement maraicher (0.60 EUR/g)

        # --- Constantes Biologiques Nominales ---
        self.mu_max_base = 0.0
        self.K_adapt = 0.05        # Vitesse d'adaptation
        
        if self.intrant_type == "algues":
            # Bacteries lytiques (Bacteroidetes uniformis L8)
            self.mu_max_base = 0.28
            self.K_s_alg = 15.0        # Constante d'affinite (g/L)
            self.K_d_bac = 0.015       # Taux de mortalite (1/h)
            self.q_enzyme = 0.05       # Ribosome rate enzyme (U/g.h)
            self.K_deg_enz = 0.02      # Denaturation de l'enzyme (1/h)
            self.Y_GradeA = 0.45       # Rendement Fucoidanes / lyse
            self.Y_GradeB = 0.65       # Rendement Biostimulant / croissance
            self.Y_GradeC = 0.90       # Rendement compost / residu
            self.Q_metab_spec = 0.15   # Chaleur metabolique (kJ/g.h)
            
        elif self.intrant_type == "organique":
            # Clostridium acetobutylicum & Cupriavidus necator
            self.mu_max_base = 0.35    # Taux croissance acidogenes
            self.K_s_org = 20.0        # Affinite substrat organique (g/L)
            self.K_d_acid = 0.02       # Mortalite acidogenes (1/h)
            self.K_i_vfa = 12.0        # Inhibition par les acides (g/L VFA)
            self.Y_vfa = 0.55          # Rendement en VFA (g/g)
            self.mu_max_solv = 0.18    # Taux solvantogenes
            self.K_s_vfa = 5.0         # Affinite VFA (g/L)
            self.K_d_solv = 0.01       # Mortalite solvantogenes (1/h)
            self.Y_GradeA = 0.38       # Rendement PHA / solvantogenes
            self.Y_GradeB = 0.45       # Rendement azote liquide / VFA
            self.Y_GradeC = 0.85       # Rendement digestat solide
            self.Q_metab_spec = 0.12   # Chaleur metabolique (kJ/g.h)
            
        elif self.intrant_type == "e_waste":
            # Acidithiobacillus ferrooxidans (base) & Chromobacterium violaceum (gold)
            self.mu_max_base = 0.15    # Taux acidophiles
            self.K_s_fe2 = 2.0         # Affinite Fe2+ (g/L)
            self.K_d_acidophile = 0.008# Mortalite acidophiles (1/h)
            self.q_fe3_spec = 0.8      # Oxydation specifique Fe2+ -> Fe3+ (g/g.h)
            self.R_leach_Cu = 0.12     # Vitesse lixiviation cuivre (L/g.h)
            
            self.mu_max_cyanogene = 0.22 # Taux cyanogenes
            self.K_s_gly = 4.0         # Affinite glycine (g/L)
            self.K_d_cyanogene = 0.012 # Mortalite cyanogenes (1/h)
            self.q_cn_spec = 0.08      # Synthese specifique CN- / glycine (g/g.h)
            self.R_leach_Au = 0.005    # Vitesse lixiviation Or (L/g.h)
            self.K_O2_gold = 2.0       # Affinite oxygene dissous pour l'or (mg/L)
            
            self.Y_GradeA = 0.95       # Rendement Or pur
            self.Y_GradeB = 0.80       # Rendement Oligo-elements
            self.Y_GradeC = 0.90       # Rendement Cuivre pur
            self.Q_metab_spec = 0.05   # Chaleur metabolique (kJ/g.h)

    def reset_state(self):
        """Reinitialise l'etat des variables d'etat physiques et biologiques."""
        self.t = 0.0
        self.history = []
        
        # Sondes physiques
        self.T = 22.0
        self.DO = 8.0
        self.H2 = 0.0
        
        # --- Dynamique du World Model (BSD V16) ---
        self.C_cap = 500.0         # Tresorerie initiale (500 Euros)
        self.P_env = 0.0           # Pollution accumulee initiale nulle
        self.S_feed = 100.0        # Stock d'intrants solides bruts (g/L)
        
        # Adaptation active
        self.raman_active = False
        self.adaptation_factor = 1.0
        self.learning_score = 1.0  # Confiance basee sur le registre
        
        # Inhibitions / Drags physiques (boite de verre)
        self.shear_drag = 1.0      # Aucun cisaillement
        self.toxic_drag = 1.0      # Aucune toxicite
        self.energy_drag = 1.0     # Aucun ralentissement thermique
        
        # Biologiques specifiques
        if self.intrant_type == "algues":
            self.X = 0.5
            self.S = 40.0
            self.E = 0.0
            self.GradeA = 0.0
            self.GradeB = 0.0
            self.GradeC = 40.0
            self.pH = 6.8
            self.Redox = 120.0
            
        elif self.intrant_type == "organique":
            self.X_acid = 0.2
            self.X_solv = 0.05
            self.S = 50.0
            self.VFA = 0.5
            self.GradeA = 0.0
            self.GradeB = 0.0
            self.GradeC = 35.0
            self.pH = 6.5
            self.Redox = 50.0
            
        elif self.intrant_type == "e_waste":
            self.S = 0.0               # Defini pour compatibilite
            self.X_acidophile = 0.1
            self.Fe2 = 10.0
            self.Fe3 = 0.1
            self.Solid_Cu = 15.0
            self.Cu_sol = 0.0
            
            self.X_cyanogene = 0.01
            self.Glycine = 10.0
            self.CN = 0.0
            self.Solid_Au = 0.004      # 4 mg/L (40 mg/kg at 100 g/L feedstock)
            self.Au_sol = 0.0
            
            self.GradeA = 0.0
            self.GradeB = 0.0
            self.GradeC = 0.0
            self.pH = 1.8
            self.Redox = 450.0

    # --- ARCHITECTURE D'APPRENTISSAGE PAR L'EXPERIENCE ---
    def load_experience(self):
        """Charge le savoir accumule depuis le registre d'experience local."""
        self.adaptation_factor = 1.0
        self.learning_score = 1.0
        self.mu_max = self.mu_max_base
        
        if not os.path.exists(LEDGER_FILE):
            return
            
        try:
            with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
                ledger = json.load(f)
                
            runs = [r for r in ledger if r.get("intrant_type") == self.intrant_type]
            if len(runs) >= 3:
                # Moyenne ponderee des facteurs d'adaptation reussis
                factors = [r.get("adaptation_factor", 1.0) for r in runs[-5:]]
                self.adaptation_factor = sum(factors) / len(factors)
                self.learning_score = round(min(2.5, 1.0 + 0.3 * len(runs)), 2)
            elif len(runs) > 0:
                self.adaptation_factor = runs[-1].get("adaptation_factor", 1.0)
                self.learning_score = 1.2
            else:
                self.adaptation_factor = 1.0
                self.learning_score = 1.0
                
            self.mu_max = self.mu_max_base * self.adaptation_factor
        except Exception:
            self.adaptation_factor = 1.0
            self.learning_score = 1.0
            self.mu_max = self.mu_max_base

    def archive_experience(self):
        """Enregistre le lot acheve dans le registre d'experience local."""
        record = {
            "intrant_type": self.intrant_type,
            "t_total": round(self.t, 2),
            "adaptation_factor": round(self.adaptation_factor, 3),
            "final_GradeA": round(self.GradeA, 3),
            "final_GradeB": round(self.GradeB, 3),
            "final_GradeC": round(self.GradeC, 3),
            "final_capital": round(self.C_cap, 2),
            "final_pollution": round(self.P_env, 2)
        }
        
        ledger = []
        if os.path.exists(LEDGER_FILE):
            try:
                with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
                    ledger = json.load(f)
            except Exception:
                ledger = []
                
        ledger.append(record)
        
        try:
            with open(LEDGER_FILE, 'w', encoding='utf-8') as f:
                json.dump(ledger, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Alerte] Erreur lors de l'ecriture du registre d'experience : {e}")

    # --- SIMULATION CAUSALE ET DYNAMIQUE ---
    def step(self, dt=0.1, control_pH=None, add_glycine=0.0, raman_data=None):
        """
        Execute un pas de temps de la simulation avec modelisation mecaniste
        des couts, de la tresorerie, de la pollution, du cisaillement et de la toxicite.
        """
        # --- 1. CONTROLE DU CAPITAL ET ALIMENTATION ---
        # Insolvabilite : coupure active des equipements
        is_insolvent = (self.C_cap <= 0.0)
        if is_insolvent:
            self.C_cap = 0.0
            self.N_rpm = 0.0
            self.DO = 0.0
            self.T = max(self.T_amb, self.T - 0.2 * dt) # Refroidissement passif
        
        # Couts d'exploitation stricts et auditables
        heat_cost = 0.05 * max(0.0, self.T - self.T_amb) * dt
        agitation_cost = 0.01 * (self.N_rpm ** 1.5) * dt
        aeration_cost = 0.005 * self.DO * dt
        starter_cost = 0.15 * add_glycine * dt
        
        total_op_cost = heat_cost + agitation_cost + aeration_cost + starter_cost
        
        # Achat automatique d'intrants si stock bas
        feed_cost = 0.0
        if self.S_feed < 15.0 and self.C_cap > 50.0:
            self.S_feed += 50.0
            feed_cost = 25.0
            
        self.C_cap -= (total_op_cost + feed_cost)
        
        # Transfert de matiere : le stock physique S_feed alimente le milieu
        if self.S_feed > 0.1:
            if self.intrant_type == "e_waste":
                if self.Solid_Cu < 15.0:
                    rate_feed = 0.8 * self.S_feed * dt
                    self.S_feed -= rate_feed
                    self.Solid_Cu += rate_feed * 0.15    # 15% cuivre
                    self.Solid_Au += rate_feed * 0.00004 # 40 mg/kg equivalent
            else:
                if self.S < 15.0:
                    rate_feed = 0.8 * self.S_feed * dt
                    self.S_feed -= rate_feed
                    self.S += rate_feed

        # --- 2. EXTRACTION RAMAN ET AUTO-CALIBRATION ---
        if raman_data:
            self.raman_active = True
            alpha = 0.4
            
            if self.intrant_type == "algues":
                if "raman_biomass" in raman_data:
                    error_X = raman_data["raman_biomass"] - self.X
                    self.X += alpha * error_X
                    self.adaptation_factor += self.K_adapt * error_X * dt
                    self.adaptation_factor = max(0.5, min(2.5, self.adaptation_factor))
                    self.mu_max = self.mu_max_base * self.adaptation_factor
                if "raman_substrate" in raman_data:
                    self.S += alpha * (raman_data["raman_substrate"] - self.S)
                if "raman_grade_a" in raman_data:
                    self.GradeA += alpha * (raman_data["raman_grade_a"] - self.GradeA)
                    
            elif self.intrant_type == "organique":
                if "raman_biomass" in raman_data:
                    error_X = raman_data["raman_biomass"] - self.X_acid
                    self.X_acid += alpha * error_X
                    self.adaptation_factor += self.K_adapt * error_X * dt
                    self.adaptation_factor = max(0.5, min(2.5, self.adaptation_factor))
                    self.mu_max = self.mu_max_base * self.adaptation_factor
                if "raman_substrate" in raman_data:
                    self.S += alpha * (raman_data["raman_substrate"] - self.S)
                if "raman_grade_a" in raman_data:
                    self.GradeA += alpha * (raman_data["raman_grade_a"] - self.GradeA)
                    
            elif self.intrant_type == "e_waste":
                if self.pH < 3.5:
                    if "raman_biomass" in raman_data:
                        error_X = raman_data["raman_biomass"] - self.X_acidophile
                        self.X_acidophile += alpha * error_X
                        self.adaptation_factor += self.K_adapt * error_X * dt
                        self.adaptation_factor = max(0.5, min(2.5, self.adaptation_factor))
                        self.mu_max = self.mu_max_base * self.adaptation_factor
                else:
                    if "raman_biomass" in raman_data:
                        error_X = raman_data["raman_biomass"] - self.X_cyanogene
                        self.X_cyanogene += alpha * error_X
                if "raman_grade_a" in raman_data:
                    self.Au_sol += alpha * (raman_data["raman_grade_a"] - self.Au_sol)
                if "raman_grade_c" in raman_data:
                    self.Cu_sol += alpha * (raman_data["raman_grade_c"] - self.Cu_sol)

        # --- 3. RETROACTIONS PHYSIQUES & DE BRUIT (AUDITABLES) ---
        # A. Stress de Cisaillement Mecanique (Shear stress)
        # Destruction des cellules si la vitesse de rotation RPM est superieure a 32 RPM
        self.shear_drag = max(0.01, 1.0 - (self.N_rpm / 32.0) ** 2.5) if self.N_rpm > 0.0 else 1.0
        
        # B. Drag de Toxicite (Metaux dissous Pb/Cd / Pollution)
        self.toxic_drag = 1.0 / (1.0 + (self.P_env / 40.0) ** 2.0)
        
        # C. Drag Thermique (Arrhenius biologique)
        def get_arrhenius(T, T_opt=35.0, T_max=45.0, T_min=10.0):
            if T <= T_min or T >= T_max:
                return 0.0
            return ((T - T_max) * (T - T_min)**2) / ((T_opt - T_min) * ((T_opt - T_min) * (T - T_opt) - (T_opt - T_max) * (T_opt + T_min - 2.0 * T)))
            
        self.energy_drag = get_arrhenius(self.T)

        # --- 4. INTEGRATION CINETIQUE ET GENERATION DE REVENUS ---
        revenue = 0.0
        biological_heat = 0.0
        
        if is_insolvent:
            # Arret total de la biologie par gel thermique ou manque d'agitation
            mu_active = 0.0
        else:
            mu_active = self.mu_max * self.energy_drag * self.shear_drag * self.toxic_drag

        if self.intrant_type == "algues":
            f_pH = math.exp(-0.5 * ((self.pH - 6.5) / 1.0)**2)
            
            # Croissance mecaniste
            mu = mu_active * (self.S / (self.K_s_alg + self.S)) * f_pH
            dX = mu * self.X - (self.K_d_bac + (1.0 - self.shear_drag) * 0.1) * self.X
            self.X += dt * dX
            
            biological_heat = mu * self.X * self.Q_metab_spec
            
            # CAZymes excretion
            dE = self.q_enzyme * self.X - self.K_deg_enz * self.E
            self.E += dt * dE
            
            # Lysis enzymatique mecaniste
            rate_lyse = 0.08 * (self.E / (10.0 + self.E)) * self.S * self.energy_drag
            self.S -= dt * rate_lyse
            if self.S < 0.0: self.S = 0.0
            
            # Accumulation et valorisation en direct
            dGradeA = dt * (self.Y_GradeA * rate_lyse)
            dGradeB = dt * (self.Y_GradeB * mu * self.X)
            
            self.GradeA += dGradeA
            self.GradeB += dGradeB
            self.GradeC = self.S + self.S_feed * 0.2
            
            # Vente immediate
            revenue = dGradeA * self.price_A + dGradeB * self.price_B + (rate_lyse * 0.1 * self.price_C)
            
            if control_pH is None:
                self.pH += dt * (-0.02 * rate_lyse + 0.01 * mu * self.X)
                self.pH += dt * 0.1 * (6.8 - self.pH)
            else:
                self.pH = control_pH
                
            target_redox = 150.0 - 400.0 * (1.0 - (self.DO / 8.0)) - 59.0 * (self.pH - 7.0)
            self.Redox += dt * 0.2 * (target_redox - self.Redox)
            
            # Accumulation de pollution par dechet non valorise
            self.P_env += dt * (rate_lyse * 0.08)
            
        elif self.intrant_type == "organique":
            f_pH_acid = math.exp(-0.5 * ((self.pH - 5.8) / 1.2)**2)
            inhibition = max(0.0, 1.0 - (self.VFA / self.K_i_vfa))
            
            # Clostridium acidogenes
            mu_acid = mu_active * (self.S / (self.K_s_org + self.S)) * inhibition * f_pH_acid
            dX_acid = mu_acid * self.X_acid - (self.K_d_acid + (1.0 - self.shear_drag) * 0.1) * self.X_acid
            self.X_acid += dt * dX_acid
            
            biological_heat = mu_acid * self.X_acid * self.Q_metab_spec
            
            rate_ferment = mu_acid * self.X_acid / 0.4
            self.S -= dt * rate_ferment
            if self.S < 0.0: self.S = 0.0
            
            self.VFA += dt * (self.Y_vfa * rate_ferment)
            
            # Switch solvantogene declenche par stress de pH bas et AGV
            # Clostridium synth solvant / PHA
            f_pH_solv = math.exp(-0.5 * ((self.pH - 6.4) / 0.8)**2)
            mu_solv = self.mu_max_solv * (self.VFA / (self.K_s_vfa + self.VFA)) * self.energy_drag * self.shear_drag * f_pH_solv
            dX_solv = mu_solv * self.X_solv - self.K_d_solv * self.X_solv
            self.X_solv += dt * dX_solv
            
            rate_vfa_cons = mu_solv * self.X_solv / 0.3
            self.VFA -= dt * rate_vfa_cons
            if self.VFA < 0.0: self.VFA = 0.0
            
            dGradeA = dt * (self.Y_GradeA * mu_solv * self.X_solv)
            dGradeB = dt * (self.Y_GradeB * rate_ferment * 0.12)
            
            self.GradeA += dGradeA
            self.GradeB += dGradeB
            self.GradeC = self.S + self.VFA * 0.5
            
            revenue = dGradeA * self.price_A + dGradeB * self.price_B
            
            if control_pH is None:
                self.pH += dt * (-0.15 * (self.Y_vfa * rate_ferment) + 0.08 * rate_vfa_cons)
                if self.pH < 4.0: self.pH = 4.0
            else:
                self.pH = control_pH
                
            self.H2 += dt * (0.05 * rate_ferment - 0.1 * self.H2)
            target_redox = 50.0 - 500.0 * (self.H2 / (2.0 + self.H2)) - 59.0 * (self.pH - 7.0)
            self.Redox += dt * 0.3 * (target_redox - self.Redox)
            
            self.P_env += dt * (rate_ferment * 0.05)
            
        elif self.intrant_type == "e_waste":
            self.Glycine += dt * add_glycine
            
            if self.pH < 3.5:
                # --- PHASE 1 (ACIDE - OXYDATION FER) ---
                f_pH = math.exp(-0.5 * ((self.pH - 1.8) / 0.5)**2)
                mu_leach = mu_active * (self.Fe2 / (self.K_s_fe2 + self.Fe2)) * f_pH
                dX_acid = mu_leach * self.X_acidophile - (self.K_d_acidophile + (1.0 - self.shear_drag) * 0.1) * self.X_acidophile
                self.X_acidophile += dt * dX_acid
                
                biological_heat = mu_leach * self.X_acidophile * self.Q_metab_spec
                
                rate_fe_ox = self.q_fe3_spec * self.X_acidophile * (self.Fe2 / (self.K_s_fe2 + self.Fe2))
                self.Fe2 -= dt * rate_fe_ox
                if self.Fe2 < 0.0: self.Fe2 = 0.0
                self.Fe3 += dt * rate_fe_ox
                
                # Attaque redoxolyse directe du Fe3+ sur le cuivre
                rate_leach_cu = self.R_leach_Cu * self.Fe3 * self.Solid_Cu * (self.N_rpm / 15.0)
                self.Solid_Cu -= dt * rate_leach_cu
                if self.Solid_Cu < 0.0: self.Solid_Cu = 0.0
                
                self.Cu_sol += dt * rate_leach_cu
                self.Fe3 -= dt * rate_leach_cu * 0.5
                if self.Fe3 < 0.0: self.Fe3 = 0.0
                self.Fe2 += dt * rate_leach_cu * 0.5
                
                # Pas de production d'or en phase acide
                dGradeA = 0.0
                dGradeC = dt * rate_leach_cu * self.Y_GradeC
                self.GradeC += dGradeC
                
                # Vente immediate du Cuivre
                revenue = dGradeC * self.price_C
                
                # Pollution moderee par fuites acides
                self.P_env += dt * (rate_leach_cu * 0.15)
                
            else:
                # --- PHASE 2 (ALCALINE - CYANOGENESE DE L'OR) ---
                self.X_acidophile += dt * (-0.1 * self.X_acidophile)
                
                f_pH = math.exp(-0.5 * ((self.pH - 9.5) / 0.8)**2)
                mu_cyan = self.mu_max_cyanogene * (self.Glycine / (self.K_s_gly + self.Glycine)) * self.energy_drag * self.shear_drag * f_pH
                dX_cyan = mu_cyan * self.X_cyanogene - self.K_d_cyanogene * self.X_cyanogene
                self.X_cyanogene += dt * dX_cyan
                
                biological_heat = mu_cyan * self.X_cyanogene * self.Q_metab_spec
                
                # Decarboxylation de la glycine -> CN-
                rate_cn_synth = self.q_cn_spec * self.X_cyanogene * (self.Glycine / (self.K_s_gly + self.Glycine))
                self.Glycine -= dt * rate_cn_synth
                if self.Glycine < 0.0: self.Glycine = 0.0
                self.CN += dt * rate_cn_synth
                
                # Lixiviation de l'or selon l'equation d'Elsner (mecaniste, dependance DO)
                f_DO_gold = self.DO / (self.K_O2_gold + self.DO)
                rate_leach_au = self.R_leach_Au * self.CN * self.Solid_Au * f_DO_gold * (self.N_rpm / 15.0)
                self.Solid_Au -= dt * rate_leach_au
                if self.Solid_Au < 0.0: self.Solid_Au = 0.0
                
                self.Au_sol += dt * (rate_leach_au * 1000.0) # mg/L
                
                dGradeA = dt * (rate_leach_au * 1000.0 * self.Y_GradeA)
                self.GradeA += dGradeA
                
                # Vente immediate de l'Or
                revenue = dGradeA * self.price_A
                
                # Pollution par relachement de cyanure gazeux ou residuel
                self.P_env += dt * (rate_cn_synth * 0.25)
                
            self.GradeB = (self.Fe3 + self.Fe2) * 0.12 * self.Y_GradeB
            
            if control_pH is None:
                target_ph = 1.8 if self.pH < 5.0 else 9.5
                self.pH += dt * 0.05 * (target_ph - self.pH)
            else:
                self.pH = control_pH
                
            if self.pH < 5.0:
                ratio = (self.Fe3 / (self.Fe2 + 0.001))
                target_redox = 450.0 + 59.0 * math.log10(ratio + 0.001)
            else:
                target_redox = 100.0 - 59.0 * (self.pH - 7.0) + 10.0 * (self.DO / 8.0)
            self.Redox += dt * 0.2 * (target_redox - self.Redox)
            
        # Re-investir une fraction de capital dans la depollution automatique
        if self.C_cap > 100.0 and self.P_env > 5.0:
            remed_cost = 0.1 * self.P_env * dt
            self.C_cap -= remed_cost
            self.P_env = max(0.0, self.P_env - 0.2 * remed_cost)

        self.C_cap += revenue

        # --- 5. BILAN THERMIQUE COMMUMS ---
        Q_motor = 0.01 * self.N_rpm  
        Q_loss = self.h_loss * (self.T - self.T_amb)
        dT_dt = (biological_heat * 10.0 + Q_motor - Q_loss) / self.C_heat
        self.T += dt * dT_dt
        self.T = max(5.0, min(60.0, self.T))
        
        # Consommation passives d'Oxygene par respiration
        kLa_O2 = 0.8 * self.N_rpm * (1.0 - math.cos(math.radians(self.theta))) if self.N_rpm > 0.0 else 0.0
        self.DO += dt * (kLa_O2 * (8.2 - self.DO) - 0.12 * self.DO)
        self.DO = max(0.0, self.DO)
        
        self.t += dt
        self.save_to_history()

    def save_to_history(self):
        """Enregistre l'etat courant et les indicateurs causaux."""
        state = {
            "t": round(self.t, 2),
            "T": round(self.T, 2),
            "pH": round(self.pH, 2),
            "Redox": round(self.Redox, 1),
            "DO": round(self.DO, 2),
            "H2": round(self.H2, 2),
            "N_rpm": round(self.N_rpm, 1),
            "theta": round(self.theta, 1),
            "GradeA": round(self.GradeA, 3),
            "GradeB": round(self.GradeB, 3),
            "GradeC": round(self.GradeC, 3),
            "adaptation_factor": round(self.adaptation_factor, 3),
            "raman_active": self.raman_active,
            # Dimensions World Model V16
            "C_cap": round(self.C_cap, 2),
            "P_env": round(self.P_env, 2),
            "S_feed": round(self.S_feed, 2),
            "shear_drag": round(self.shear_drag, 2),
            "toxic_drag": round(self.toxic_drag, 2),
            "energy_drag": round(self.energy_drag, 2),
            "learning_score": round(self.learning_score, 2),
            "unfc_class": self.get_sara4unfc_classification()["unfc_code"]
        }
        
        if self.intrant_type == "algues":
            state["X"] = round(self.X, 3)
            state["S"] = round(self.S, 3)
            state["E"] = round(self.E, 3)
        elif self.intrant_type == "organique":
            state["X_acid"] = round(self.X_acid, 3)
            state["X_solv"] = round(self.X_solv, 3)
            state["S"] = round(self.S, 3)
            state["VFA"] = round(self.VFA, 3)
        elif self.intrant_type == "e_waste":
            state["X_acidophile"] = round(self.X_acidophile, 3)
            state["X_cyanogene"] = round(self.X_cyanogene, 3)
            state["Solid_Cu"] = round(self.Solid_Cu, 3)
            state["Solid_Au"] = round(self.Solid_Au * 1000.0, 1)
            state["CN"] = round(self.CN, 3)
            state["Glycine"] = round(self.Glycine, 3)
            
        self.history.append(state)

    def run_simulation(self, total_hours=72.0, dt=0.2):
        """Execute la simulation complète hors ligne."""
        self.reset_state()
        steps = int(total_hours / dt)
        for i in range(steps):
            current_hour = i * dt
            ph_val = None
            add_gly = 0.0
            
            if self.intrant_type == "e_waste":
                if current_hour < 36.0:
                    ph_val = 1.8
                else:
                    ph_val = 9.5
                    if abs(current_hour - 36.0) < 0.01:
                        self.X_cyanogene = 0.5
                        add_gly = 10.0
            elif self.intrant_type == "organique":
                if self.pH < 5.2:
                    ph_val = 5.8
                    
            self.step(dt=dt, control_pH=ph_val, add_glycine=add_gly)
        self.archive_experience()
        return self.history

    def get_future_prediction(self, horizon_hours=24.0, dt=0.5):
        """Genere une projection predictive a horizon glissant."""
        # Sauvegarde profonde de l'etat
        backup_t = self.t
        backup_T = self.T
        backup_pH = self.pH
        backup_Redox = self.Redox
        backup_DO = self.DO
        backup_H2 = self.H2
        backup_history = list(self.history)
        backup_adapt = self.adaptation_factor
        backup_C_cap = self.C_cap
        backup_P_env = self.P_env
        backup_S_feed = self.S_feed
        
        if self.intrant_type == "algues":
            state_vars = (self.X, self.S, self.E, self.GradeA, self.GradeB, self.GradeC)
        elif self.intrant_type == "organique":
            state_vars = (self.X_acid, self.X_solv, self.S, self.VFA, self.GradeA, self.GradeB, self.GradeC)
        elif self.intrant_type == "e_waste":
            state_vars = (self.X_acidophile, self.X_cyanogene, self.Fe2, self.Fe3, self.Solid_Cu, self.Cu_sol, self.Glycine, self.CN, self.Solid_Au, self.Au_sol, self.GradeA, self.GradeB, self.GradeC)
            
        prediction_history = []
        steps = int(horizon_hours / dt)
        
        prediction_history.append({
            "t": round(self.t, 2),
            "GradeA": round(self.GradeA, 3),
            "GradeB": round(self.GradeB, 3),
            "GradeC": round(self.GradeC, 3),
            "X": round((self.X if self.intrant_type == "algues" else (self.X_acid if self.intrant_type == "organique" else self.X_acidophile)), 3),
            "S": round(self.S, 3),
            "C_cap": round(self.C_cap, 2),
            "P_env": round(self.P_env, 2)
        })
        
        for _ in range(steps):
            ph_val = None
            if self.intrant_type == "e_waste":
                ph_val = 1.8 if self.t < 36.0 else 9.5
            elif self.intrant_type == "organique":
                if self.pH < 5.2: ph_val = 5.8
                
            self.step(dt=dt, control_pH=ph_val)
            prediction_history.append({
                "t": round(self.t, 2),
                "GradeA": round(self.GradeA, 3),
                "GradeB": round(self.GradeB, 3),
                "GradeC": round(self.GradeC, 3),
                "X": round((self.X if self.intrant_type == "algues" else (self.X_acid if self.intrant_type == "organique" else self.X_acidophile)), 3),
                "S": round(self.S, 3),
                "C_cap": round(self.C_cap, 2),
                "P_env": round(self.P_env, 2)
            })
            
        # Restauration
        self.t = backup_t
        self.T = backup_T
        self.pH = backup_pH
        self.Redox = backup_Redox
        self.DO = backup_DO
        self.H2 = backup_H2
        self.history = backup_history
        self.adaptation_factor = backup_adapt
        self.mu_max = self.mu_max_base * self.adaptation_factor
        self.C_cap = backup_C_cap
        self.P_env = backup_P_env
        self.S_feed = backup_S_feed
        
        if self.intrant_type == "algues":
            self.X, self.S, self.E, self.GradeA, self.GradeB, self.GradeC = state_vars
        elif self.intrant_type == "organique":
            self.X_acid, self.X_solv, self.S, self.VFA, self.GradeA, self.GradeB, self.GradeC = state_vars
        elif self.intrant_type == "e_waste":
            self.X_acidophile, self.X_cyanogene, self.Fe2, self.Fe3, self.Solid_Cu, self.Cu_sol, self.Glycine, self.CN, self.Solid_Au, self.Au_sol, self.GradeA, self.GradeB, self.GradeC = state_vars
            
        return prediction_history

    def get_sara4unfc_classification(self):
        """
        Calcule dynamiquement la classification UNFC (E-F-G) selon FutuRaM D7.5.
        Renvoie un dictionnaire contenant le triplet UNFC et le diagnostic des Controlling Factors (CFs).
        """
        e_class = "E3.2"
        e_desc = "Viabilite socio-economique non etablie (Capital critique)"
        cf_e = []
        
        if self.C_cap <= 0.0:
            e_class = "E3.2"
            e_desc = "Insolvabilite totale - Operation industrielle suspendue"
            cf_e.append("Capital nul (Insolvabilite)")
        elif self.C_cap < 300.0:
            e_class = "E3.2"
            e_desc = "Prospective - Risque de faillite operationnelle imminent"
            cf_e.append("Seuil critique de capital (<300 EUR)")
        elif self.P_env > 25.0:
            e_class = "E3.3"
            e_desc = "Non viable - Pollution environnementale severe (Toxic drag active)"
            cf_e.append("Pollution excessive (>25 ppm)")
        elif self.C_cap >= 2000.0 and self.P_env <= 5.0:
            e_class = "E1"
            e_desc = "Viable - Excellente rentabilite economique et impact environnemental minimal"
            cf_e.append("Capital optimal (>=2000 EUR)")
            cf_e.append("Pollution minimale (<=5 ppm)")
        else:
            e_class = "E2"
            e_desc = "Potentiellement viable - Rentabilite moderee, pollution controlee"
            cf_e.append("Capital suffisant (>=300 EUR)")
            cf_e.append("Pollution controlee (<=25 ppm)")

        f_class = "F3"
        f_desc = "Faisabilite non etablie - Arret ou conditions letales"
        cf_f = []
        
        if self.N_rpm <= 0.0:
            f_class = "F3"
            f_desc = "Inactif - Agitation a l'arret"
            cf_f.append("Agitation nulle (TRL 2)")
        elif self.N_rpm > 32.0:
            f_class = "F3"
            f_desc = "Critique - Cisaillement mecanique cellulaire extreme (Lyse membranaire active)"
            cf_f.append("Cisaillement membranaire actif (>32 RPM)")
        elif self.T <= 10.0 or self.T >= 45.0:
            f_class = "F3"
            f_desc = "Letal - Temperature extreme inhibant totalement la biologie"
            cf_f.append("Inhibition thermique extreme")
        elif 25.0 <= self.T <= 38.0 and self.N_rpm <= 25.0:
            f_class = "F1"
            f_desc = "Faisable - Conditions de bioprocede optimales"
            cf_f.append("Temperature optimale (Arrhenius OK)")
            cf_f.append("Integrite cellulaire preservee (<=25 RPM)")
        else:
            f_class = "F2"
            f_desc = "Potentiellement faisable - Bioprocede en condition sous-optimale"
            cf_f.append("Ecart thermique ou mecanique modere")

        g_class = "G3"
        g_desc = "Certitude faible - Estimations preliminaires theoriques"
        cf_g = []
        
        if self.raman_active and self.learning_score >= 1.50:
            g_class = "G1"
            g_desc = "Certitude elevee - Calibration Raman en continu et registre d'experience robuste"
            cf_g.append("Spectroscopie Raman active")
            cf_g.append("Savoir historique Ledger robuste (>=1.50x)")
        elif self.raman_active or self.learning_score >= 1.20:
            g_class = "G2"
            g_desc = "Certitude moderee - Estimation fiabilisee par Raman ou historique"
            if self.raman_active:
                cf_g.append("Spectroscopie Raman active")
            else:
                cf_g.append("Savoir historique Ledger modere (>=1.20x)")
        else:
            g_class = "G3"
            g_desc = "Certitude faible - Estimation theorique, absence de donnees physiques directes"
            cf_g.append("Aucun capteur Raman en ligne")
            cf_g.append("Absence d'historique de lot (Score 1.00x)")

        unfc_code = f"{e_class}-{f_class}-{g_class}"
        return {
            "unfc_code": unfc_code,
            "e_class": e_class,
            "e_desc": e_desc,
            "cf_e": cf_e,
            "f_class": f_class,
            "f_desc": f_desc,
            "cf_f": cf_f,
            "g_class": g_class,
            "g_desc": g_desc,
            "cf_g": cf_g
        }

    def get_audit_text(self):
        """
        Analyse de facon mecaniste les retroactions actives de l'etat
        et renvoie un diagnostic structure 100% explicable et auditable.
        """
        if not self.history:
            return "Aucune donnee d'audit disponible."
            
        final = self.history[-1]
        
        audit = f"=== RAPPORT D'AUDIT METHODOLOGIQUE (Lot V17) ===\n"
        audit += f"Type d'intrant : {self.intrant_type.upper()} | Temps de cycle : {final['t']} h\n"
        audit += f"--------------------------------------------------------------------------------\n"
        
        # 1. Analyse financiere et ressources
        audit += f"[CAPITAL & FLUX RESSOURCES]\n"
        audit += f"-> Capital Disponible : {final['C_cap']:.2f} EUR (Statut: "
        if final['C_cap'] <= 0.0:
            audit += "CRASH D'INSOLVABILITE - Chauffage, aeration et melange COUPEES)\n"
        elif final['C_cap'] < 100.0:
            audit += "CRITIQUE - Risque d'arret imminent de l'usine)\n"
        else:
            audit += "STABLE - Sante financière verifiee)\n"
            
        audit += f"-> Reserve solide en stock S_feed : {final['S_feed']:.2f} g/L\n"
        
        # 2. Diagnose des inhibitions cinetiques (White-Box Audit)
        audit += f"\n[DIAGNOSTIC DE TOXICITE & CONTRAINTES PHYSIQUES]\n"
        
        # Stress de cisaillement (Shear)
        audit += f"-> Drag de Cisaillement Mecanique : {final['shear_drag'] * 100:.1f}% "
        if final['shear_drag'] < 0.70:
            audit += f"[ALERTE: Agitation RPM ({final['N_rpm']} rpm) excessive. Eclatement cellulaire actif par cisaillement]\n"
        else:
            audit += f"[CONFORME: Agitation preserve l'integrite membranaire des souches]\n"
            
        # Drag de toxicite (Pollution)
        audit += f"-> Drag de Toxicite Metallique (P_env = {final['P_env']:.2f}) : {final['toxic_drag'] * 100:.1f}% "
        if final['toxic_drag'] < 0.80:
            audit += f"[ALERTE: Accumulation de metaux dissous ou acides. Empoisonnement enzymatique actif]\n"
        else:
            audit += f"[CONFORME: Taux d'impuretes tolerables]\n"
            
        # Drag energetique (Temperature)
        audit += f"-> Drag d'Energie (Temperature = {final['T']}C) : {final['energy_drag'] * 100:.1f}% "
        if final['energy_drag'] < 0.50:
            audit += f"[ALERTE: Temperature eloignee de l'optimum bacterien (35C)]\n"
        else:
            audit += f"[CONFORME: Regulateur thermique optimal]\n"
            
        # 3. Evolution des connaissances
        audit += f"\n[COMPORTEMENT APPRENANT & REGISTRE D'EXPERIENCE]\n"
        audit += f"-> Score de connaissance accumule : {final['learning_score']:.2f}x\n"
        audit += f"-> Coefficient adaptatif Raman mu_max : {final['adaptation_factor']:.2f}x "
        if self.raman_active:
            audit += "(Calibration active via mesures moleculaires Raman)\n"
        else:
            audit += "(Estimation theorique basee sur le savoir historique)\n"
            
        # 4. Classification SARA4UNFC V17
        unfc = self.get_sara4unfc_classification()
        audit += f"\n[EVALUATION DE LA MINE URBAINE - SARA4UNFC V17]\n"
        audit += f"-> Code UNFC Courant : {unfc['unfc_code']}\n"
        audit += f"   * Axe E ({unfc['e_class']}) : {unfc['e_desc']}\n"
        audit += f"     Facteurs : {', '.join(unfc['cf_e'])}\n"
        audit += f"   * Axe F ({unfc['f_class']}) : {unfc['f_desc']}\n"
        audit += f"     Facteurs : {', '.join(unfc['cf_f'])}\n"
        audit += f"   * Axe G ({unfc['g_class']}) : {unfc['g_desc']}\n"
        audit += f"     Facteurs : {', '.join(unfc['cf_g'])}\n"
            
        return audit

    def get_narrative(self):
        """Genere la narration d'ambiance du Maitre de Chai."""
        if not self.history:
            return "Aucune simulation."
        
        final = self.history[-1]
        n = f"=== MAITRE DE CHAI SENTINEL V16 (Lot #ORC-{id(self.history)%1000:03d}) ===\n"
        n += f"Intrant: {self.intrant_type.upper()} | t = {final['t']} h\n"
        n += f"Physico-chimie: T = {final['T']}C | pH = {final['pH']} | ORP = {final['Redox']} mV | O2 = {final['DO']} mg/L\n"
        n += f"Indicateurs de Monde : Capital = {final['C_cap']} EUR | Pollution = {final['P_env']} ppm\n"
        
        if self.raman_active:
            n += f"CAPTEURS SPECTROSCOPIQUES RAMAN: ACTIFS\n"
            n += f"-> Facteur d'adaptation biologique calibre: {final['adaptation_factor']:.2f}x\n"
        else:
            n += f"CAPTEURS RAMAN: INACTIFS (Inference par registre de connaissances : {final['learning_score']:.2f}x)\n"
            
        n += f"--------------------------------------------------------------------------------\n"
        
        if self.intrant_type == "algues":
            n += f"Lysis wall-attack (Bacteroides L8): Substrat restant: {final['S']} g/L | Bactéries: {final['X']} g/L\n"
            n += f"  - Grade A (Fucoïdanes nobles): {final['GradeA']} g/L [Clarins T.R.U.S.T.]\n"
            n += f"  - Grade B (Biostimulant): {final['GradeB']} g/L\n"
            n += f"  - Grade C (Amendement maraîcher): {final['GradeC']} g/L\n"
        elif self.intrant_type == "organique":
            n += f"Fermentation ABE/PHA (Clostridium): Substrat restant: {final['S']} g/L\n"
            n += f"  - Grade A (PHA / Solvants): {final['GradeA']} g/L\n"
            n += f"  - Grade B (Engrais liquide): {final['GradeB']} g/L\n"
            n += f"  - Grade C (Digestat stabilisé): {final['GradeC']} g/L\n"
        elif self.intrant_type == "e_waste":
            n += f"Biolixiviation E-Waste (Acidithiobacillus/Chromobacterium):\n"
            n += f"  - Grade A (Or soluble dicyanoaurate): {final['GradeA']} mg/L\n"
            n += f"  - Grade B (Oligo-éléments Fe/Zn): {final['GradeB']} g/L\n"
            n += f"  - Grade C (Cuivre lixivié): {final['GradeC']} g/L\n"
            
        return n

# --- SERVEUR API DE TELEMETRIE HTTP INDUSTRIEL V16 ---

_global_simulator = SentinelSimulator(intrant_type="algues")

class SentinelHTTPRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Connection', 'close')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        global _global_simulator
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/api/state':
            self._set_headers(200)
            state = _global_simulator.history[-1] if _global_simulator.history else {}
            response = {
                "intrant_type": _global_simulator.intrant_type,
                "current_state": state,
                "history": _global_simulator.history,
                "raman_calibrated_mu": round(_global_simulator.mu_max, 4),
                "adaptation_factor": round(_global_simulator.adaptation_factor, 3),
                "narrative": _global_simulator.get_narrative(),
                "sara4unfc": _global_simulator.get_sara4unfc_classification()
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        elif parsed_path.path == '/api/prediction':
            self._set_headers(200)
            prediction = _global_simulator.get_future_prediction(horizon_hours=24.0, dt=1.0)
            response = {
                "intrant_type": _global_simulator.intrant_type,
                "prediction_horizon": "24h",
                "adaptation_factor": round(_global_simulator.adaptation_factor, 3),
                "prediction_curve": prediction
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        elif parsed_path.path == '/api/audit':
            self._set_headers(200)
            response = {
                "intrant_type": _global_simulator.intrant_type,
                "audit_logs": _global_simulator.get_audit_text(),
                "history_length": len(_global_simulator.history),
                "knowledge_ledger_exists": os.path.exists(LEDGER_FILE),
                "sara4unfc": _global_simulator.get_sara4unfc_classification()
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode('utf-8'))

    def do_POST(self):
        global _global_simulator
        parsed_path = urllib.parse.urlparse(self.path)
        
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Invalid JSON", "details": str(e)}).encode('utf-8'))
            return

        if parsed_path.path == '/api/config':
            if "intrant_type" in data:
                intrant = data["intrant_type"]
                if intrant in ["algues", "organique", "e_waste"]:
                    _global_simulator = SentinelSimulator(intrant_type=intrant)
                    if "N_rpm" in data: _global_simulator.N_rpm = float(data["N_rpm"])
                    if "theta" in data: _global_simulator.theta = float(data["theta"])
                    if "T_amb" in data: _global_simulator.T_amb = float(data["T_amb"])
                    
                    self._set_headers(200)
                    self.wfile.write(json.dumps({
                        "status": "configured", 
                        "intrant_type": _global_simulator.intrant_type,
                        "N_rpm": _global_simulator.N_rpm,
                        "theta": _global_simulator.theta
                    }).encode('utf-8'))
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Unknown intrant type"}).encode('utf-8'))
            else:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing intrant_type"}).encode('utf-8'))

        elif parsed_path.path == '/api/telemetry':
            if "T" in data: _global_simulator.T = float(data["T"])
            if "pH" in data: _global_simulator.pH = float(data["pH"])
            if "Redox" in data: _global_simulator.Redox = float(data["Redox"])
            if "DO" in data: _global_simulator.DO = float(data["DO"])
            if "N_rpm" in data: _global_simulator.N_rpm = float(data["N_rpm"])
            if "theta" in data: _global_simulator.theta = float(data["theta"])
            
            dt = float(data.get("dt", 0.5))
            control_pH = data.get("control_pH", None)
            add_gly = float(data.get("add_glycine", 0.0))
            
            raman_info = data.get("raman", None)
            
            _global_simulator.step(dt=dt, control_pH=control_pH, add_glycine=add_gly, raman_data=raman_info)
            
            # Si fin de cycle verifiee, archiver l'experience
            if _global_simulator.t >= 71.9:
                _global_simulator.archive_experience()
                
            self._set_headers(200)
            response = {
                "status": "success",
                "time": round(_global_simulator.t, 2),
                "estimated_grades": {
                    "GradeA": round(_global_simulator.GradeA, 3),
                    "GradeB": round(_global_simulator.GradeB, 3),
                    "GradeC": round(_global_simulator.GradeC, 3)
                },
                "adaptation_factor": round(_global_simulator.adaptation_factor, 3),
                "raman_calibrated": _global_simulator.raman_active,
                "C_cap": round(_global_simulator.C_cap, 2),
                "P_env": round(_global_simulator.P_env, 2),
                "unfc_code": _global_simulator.get_sara4unfc_classification()["unfc_code"]
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode('utf-8'))


def start_server(port=5000):
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, SentinelHTTPRequestHandler)
    print(f"\n[API JUMEAU NUMERIQUE SENTINEL V17 ACTIVE]")
    print(f"-> Serveur mecaniste en ecoute sur le port {port}...")
    print(f"-> Endpoints disponibles :")
    print(f"   * POST http://localhost:{port}/api/config      (Parametrage de lot)")
    print(f"   * POST http://localhost:{port}/api/telemetry   (Ingestion IoT + Raman)")
    print(f"   * GET  http://localhost:{port}/api/state       (Lecture d'etat en direct)")
    print(f"   * GET  http://localhost:{port}/api/prediction  (Projection predictive a 24h)")
    print(f"   * GET  http://localhost:{port}/api/audit       (Rapport d'audit de cause)")
    print(f"--------------------------------------------------")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[API Interruption] Arret du serveur.")
        httpd.server_close()


# --- CLI STANDARD / SERVEUR V16 ---
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        port = 5000
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        start_server(port)
    else:
        print("======================================================================")
        print("   Lancement du test de l'Oracle Alpha - World Model Mecaniste V16     ")
        print("======================================================================\n")
        
        # 1. Simuler l'intrant Algues
        print(">>> SIMULATION 1: Intrant Algues (White-Box, 72 heures) <<<")
        sim_alg = SentinelSimulator(intrant_type="algues")
        sim_alg.run_simulation(total_hours=72.0, dt=0.5)
        print(sim_alg.get_narrative())
        print(sim_alg.get_audit_text())
        print("\n" + "="*80 + "\n")
        
        # 2. Simuler l'intrant E-Waste
        print(">>> SIMULATION 2: Intrant Dechets Electroniques (Bi-phasique, 72 heures) <<<")
        sim_ew = SentinelSimulator(intrant_type="e_waste")
        sim_ew.run_simulation(total_hours=72.0, dt=0.5)
        print(sim_ew.get_narrative())
        print(sim_ew.get_audit_text())
        print("\n" + "="*80 + "\n")
        
        print("\nConseil: Lancez le script avec '--serve' pour demarrer l'API HTTP locale !")
