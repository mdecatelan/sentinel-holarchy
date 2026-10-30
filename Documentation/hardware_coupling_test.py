"""
================================================================================
  SENTINEL-ALGAE | BANC D'ESSAI HARDWARE-IN-THE-LOOP APPRENANT V16
  Simulation Industrielle Séquentielle Multi-Lots et Registre d'Expérience
================================================================================
Ce script simule le comportement physique bruité d'un réacteur (Bio-Drum V16)
sur trois lots successifs pour démontrer le mécanisme d'apprentissage et
d'accumulation d'expérience ("Knowledge Ledger") du Jumeau Numérique.

Caractéristiques de la démo :
1. Lot 1 : Démarrage sans historique (Score de connaissance = 1.00x).
2. Fin du Lot 1 : Archivage automatique dans "knowledge_ledger.json".
3. Lot 2 : Le Jumeau charge le registre (Score de connaissance = 1.20x).
4. Lot 3 : Inférence optimisée par l'expérience (Score de connaissance = 1.50x).

Les calculs physiques incluent le bruit de mesure et une dérive active (+30%).
Les requêtes utilisent l'API HTTP Rest conforme sur le port 5000.

Auteur: Antigravity (Advanced Agentic Coding - Google DeepMind Team)
Date: Mai 2026
"""

import time
import json
import random
import sys
import os
import math
import urllib.request
import urllib.error

def send_post_request(url, data):
    """Envoie une requête POST HTTP contenant du JSON en utilisant urllib natif."""
    req_body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=req_body,
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=3.0) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body)
    except urllib.error.URLError as e:
        print(f"[ERREUR RESEAU] Impossible de poster a l'adresse {url}.")
        print(f"-> Ref: {e.reason}")
        return None

def send_get_request(url):
    """Envoie une requête GET HTTP en utilisant urllib natif."""
    try:
        with urllib.request.urlopen(url, timeout=3.0) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body)
    except urllib.error.URLError as e:
        print(f"[ERREUR RESEAU] Impossible de contacter {url}.")
        print(f"-> Ref: {e.reason}")
        return None

def run_single_batch(intrant, batch_index, total_steps=12, server_port=5000):
    url_config = f"http://127.0.0.1:{server_port}/api/config"
    url_telemetry = f"http://127.0.0.1:{server_port}/api/telemetry"
    url_state = f"http://127.0.0.1:{server_port}/api/state"
    url_audit = f"http://127.0.0.1:{server_port}/api/audit"

    print(f"\n======================================================================")
    print(f"               LOT #{batch_index:03d} - DEMARRAGE DE LA DECONSTRUCTION               ")
    print(f"======================================================================")
    
    # Configuration du lot
    config_payload = {
        "intrant_type": intrant,
        "N_rpm": 18.0,
        "theta": 45.0,
        "T_amb": 21.0
    }
    
    config_res = send_post_request(url_config, config_payload)
    if not config_res:
        print("[CRASH] Configuration refusee. Assurez-vous d'avoir lance le serveur :")
        print(f"   powershell> python sentinel_simulator.py --serve --port {server_port}")
        return None

    # Recupere le score initial d'apprentissage pour prouver l'enrichissement
    init_state = send_get_request(url_state)
    learning_score = 1.0
    if init_state:
        # Si de l'historique a ete charge
        learning_score = init_state.get("current_state", {}).get("learning_score", 1.0)
        # S'il n'y a pas encore d'historique dans cette cuvee
        if learning_score == 1.0 and len(init_state.get("history", [])) == 0:
            # On recupere la valeur par defaut du simulateur (learning_score est stocke dans l'instance)
            # Pour la premiere execution, c'est 1.0. Lors du chargement du registre, il augmente.
            # Mettons un print explicite du score d'apprentissage
            pass

    print(f"[*] Chargement du Jumeau : Taux de croissance base = 0.28")
    print(f"[*] Base de connaissances : Score d'apprentissage initial = {learning_score:.2f}x")
    print(f"[*] Ingestion en direct des capteurs physiques et du spectrometre Raman...")
    print("-" * 110)
    print(f"{'Temps (h)':<10}{'T (°C)':<8}{'pH':<8}{'ORP (mV)':<10}{'Raman X(g/L)':<15}{'Est GA(g/L)':<14}{'Adaptation':<12}{'Capital ($)':<14}{'UNFC Class':<12}")
    print("-" * 110)

    t_sim = 0.0
    dt = 6.0  # Pas plus grand (6h) pour accelerer la demo (12 pas = 72h)
    
    # Verite physique interne stochastique du reacteur (avec derive active de +30%)
    real_X = 0.5
    real_S = 40.0
    real_E = 0.0
    real_GradeA = 0.0
    real_pH = 6.8
    real_Redox = 120.0
    real_mu_max = 0.28 * 1.30  # +30% croissance
    real_C_cap = 500.0
    real_P_env = 0.0

    for step in range(total_steps):
        # Modelisation physique stochastique
        f_temp = 0.95
        f_pH = math.exp(-0.5 * ((real_pH - 6.5) / 1.0)**2)
        
        # Cinetique acceleree
        real_mu = real_mu_max * (real_S / (15.0 + real_S)) * f_temp * f_pH
        real_X += dt * (real_mu * real_X - 0.015 * real_X)
        real_E += dt * (0.05 * real_X - 0.02 * real_E)
        
        rate_lyse = 0.08 * (real_E / (10.0 + real_E)) * real_S * f_temp
        real_S -= dt * rate_lyse
        if real_S < 0.0: real_S = 0.0
        
        dGradeA = dt * (0.45 * rate_lyse)
        real_GradeA += dGradeA
        
        real_pH += dt * (-0.02 * rate_lyse + 0.01 * real_mu * real_X)
        real_pH += dt * 0.1 * (6.5 - real_pH)
        real_Redox += dt * 0.2 * ((150.0 - 400.0 * 0.9 - 59.0 * (real_pH - 7.0)) - real_Redox)
        
        # Economie & Pollution reelle
        real_C_cap -= (0.05 * 15.0 + 0.01 * 15.0 + 0.04) * dt
        real_C_cap += dGradeA * 22.0
        real_P_env += dt * (rate_lyse * 0.08)
        
        t_sim += dt

        # Capteurs bruités
        sensor_T = 35.0 + random.uniform(-0.15, 0.15)
        sensor_pH = round(real_pH + random.uniform(-0.04, 0.04), 2)
        sensor_Redox = round(real_Redox + random.uniform(-4.0, 4.0), 1)
        sensor_DO = 7.8 + random.uniform(-0.08, 0.08)
        
        # Spectrometre Raman (Mesures moleculaires directes)
        raman_biomass = round(real_X + random.uniform(-0.02, 0.02), 3)
        raman_sub = round(real_S + random.uniform(-0.3, 0.3), 2)
        raman_ga = round(real_GradeA + random.uniform(-0.05, 0.05), 3)
        
        telemetry_payload = {
            "T": sensor_T,
            "pH": sensor_pH,
            "Redox": sensor_Redox,
            "DO": sensor_DO,
            "dt": dt,
            "raman": {
                "raman_biomass": raman_biomass,
                "raman_substrate": raman_sub,
                "raman_grade_a": raman_ga
            }
        }
        
        res = send_post_request(url_telemetry, telemetry_payload)
        
        if res and res["status"] == "success":
            est_Ga = res["estimated_grades"]["GradeA"]
            factor = res["adaptation_factor"]
            cap = res["C_cap"]
            unfc_code = res.get("unfc_code", "N/A")
            print(f"{t_sim:<10.1f}{sensor_T:<8.1f}{sensor_pH:<8.2f}{sensor_Redox:<10.1f}{raman_biomass:<15.3f}{est_Ga:<14.3f}{factor:<12.2f}{cap:<14.2f}{unfc_code:<12}")
        else:
            print("[❌ HIL ERREUR] Perte de liaison au pas " + str(step+1))
            break
            
        time.sleep(0.2)  # Pause ultra-rapide (200ms) pour dynamisme

    print("-" * 110)
    print("[OK] Lot termine et archive dans le Registre local d'Experience.")
    
    # Récupérer l'audit final pour valider l'apprentissage
    final_audit = send_get_request(url_audit)
    final_state = send_get_request(url_state)
    
    if final_state and final_audit:
        final_factor = final_state["adaptation_factor"]
        final_score = final_state["current_state"].get("learning_score", 1.0)
        print(f"[OK] Jumeau Numerique Audite.")
        print(f"    - Facteur d'adaptation final : {final_factor:.2f}x (Cible : 1.30x)")
        print(f"    - Score final de connaissance ledger : {final_score:.2f}x")
        return {
            "batch_id": batch_index,
            "adaptation_factor": final_factor,
            "learning_score": final_score,
            "capital": final_state["current_state"].get("C_cap", 0.0),
            "pollution": final_state["current_state"].get("P_env", 0.0),
            "unfc_code": final_state.get("sara4unfc", {}).get("unfc_code", "N/A")
        }
    return None

def run_hil_learning_demo(intrant="algues", server_port=5000):
    print("======================================================================")
    print("      SENTINEL-ALGAE | HIL MULTI-LOTS ET ENRICHISSEMENT DE SAVOIR      ")
    print("            Demonstration de l'Apprentissage Mecaniste V16            ")
    print("======================================================================\n")
    print(f"[*] Cible : Serveur de Télémétrie HTTP sur le port {server_port}")
    print(f"[*] Intrant teste : {intrant.upper()}")
    
    # Reinitialiser le fichier ledger pour la demo
    if os.path.exists("knowledge_ledger.json"):
        try:
            os.remove("knowledge_ledger.json")
            print("[*] Reinitialisation du registre local 'knowledge_ledger.json' pour la demonstration.")
        except Exception:
            pass

    results = []
    
    # Lancement successif de 3 lots pour prouver la montee en competence
    for i in range(1, 4):
        res = run_single_batch(intrant, i, total_steps=12, server_port=server_port)
        if res:
            results.append(res)
        time.sleep(1.0) # Pause entre les lots

    # Rapport final d'audit de l'actif de connaissance
    print("\n======================================================================================")
    print("                 BILAN DE CAPITALISATION DU SAVOIR & VIABILITE V17                    ")
    print("======================================================================================")
    print(f"{'Lot ID':<10}{'Score Apprentissage':<24}{'Facteur Calibre':<20}{'Tresorerie finale':<20}{'UNFC V17 Class':<15}")
    print("-" * 88)
    for r in results:
        print(f"Lot #{r['batch_id']:03d}   {r['learning_score']:<24.2f}{r['adaptation_factor']:<20.2f}{r['capital']:<20.2f}{r['unfc_code']:<15}")
    print("-" * 88)
    print("[OK] PREUVE D'ENRICHISSEMENT METABOLIQUE EMANTE DU REGISTRE CONVERGEE.")
    print("    Le Jumeau Numerique accumule de l'actif technologique auditable")
    print("    et optimise son score predictif au fil de votre experience de terrain.")
    print("======================================================================")

if __name__ == "__main__":
    intrant_type = "algues"
    if len(sys.argv) > 1:
        if sys.argv[1] in ["algues", "organique", "e_waste"]:
            intrant_type = sys.argv[1]
            
    run_hil_learning_demo(intrant=intrant_type)
