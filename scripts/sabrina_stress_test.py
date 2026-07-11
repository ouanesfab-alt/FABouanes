#!/usr/bin/env python
"""
Sabrina Advanced Full-Field Stress Test & Validation Script.
Simulates natural language tasks by specifying ALL fields (notes, address, date, phone, categories, etc.)
multiple times to verify database integration, API serialization, and type checking.
"""

import os
import sys
import json
import time
import asyncio
import logging
import argparse
from typing import List, Dict, Any

# Setup UTF-8 streams for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Setup project root path
PROJECT_ROOT = r"c:\Users\massi\Downloads\FABouanes-main"
sys.path.insert(0, PROJECT_ROOT)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sabrina.stresstest_advanced")

from app.core.db_helpers import db_manager
from app.modules.assistant.service import (
    run_assistant_agent_generator,
    get_gemini_api_key,
)

# Advanced prompts testing ALL possible input fields
STRESS_PROMPTS = [
    {
        "category": "Clients",
        "task": "Créer un client complet",
        "prompt": "Crée un client avec les détails suivants : nom 'Client Test Compliqué', téléphone '0555001122', adresse '12 Rue d\\'Alger', notes 'Note client VIP', solde de départ 15000."
    },
    {
        "category": "Suppliers",
        "task": "Créer un fournisseur complet",
        "prompt": "Crée un fournisseur avec les détails : nom 'Fournisseur Test Compliqué', téléphone '0666001122', adresse '45 Route de Sétif', notes 'Note fournisseur principal'."
    },
    {
        "category": "Raw Materials",
        "task": "Créer une matière première complète",
        "prompt": "Ajoute une matière première nommée 'Orge Compliqué Test' avec l'unité 'kg', le stock de départ 2500, le coût d\\'achat moyen 42.50 et le seuil d\\'alerte de stock à 500."
    },
    {
        "category": "Finished Products",
        "task": "Créer un produit fini complet",
        "prompt": "Crée un produit fini nommé 'Aliment Volaille Compliqué' avec l'unité 'kg', le stock de départ 1200, le prix de vente par défaut 78.00 et le seuil d\\'alerte de stock à 100."
    },
    {
        "category": "Purchases",
        "task": "Enregistrer un achat complet",
        "prompt": "Enregistre un achat pour le fournisseur 'Fournisseur Test Compliqué' : 800 kg de la matière première 'Orge Compliqué Test' au prix unitaire de 42.50, avec le total 34000, la date d\\'achat '2026-07-11' et la note 'Achat de test complique'."
    },
    {
        "category": "Sales",
        "task": "Enregistrer une vente complète",
        "prompt": "Enregistre une vente pour le client 'Client Test Compliqué' : 400 kg du produit fini 'Aliment Volaille Compliqué' à 78.00, total 31200, avec un type de vente 'credit', un montant payé de 11200, la date de vente '2026-07-11' et les notes 'Livraison par camion'."
    },
    {
        "category": "Payments",
        "task": "Enregistrer un versement complet",
        "prompt": "Ajoute un versement de type 'versement' pour le client 'Client Test Compliqué' d'un montant de 20000 avec la date '2026-07-11' et la note 'Paiement solde facture'."
    },
    {
        "category": "Expenses",
        "task": "Enregistrer une dépense complète",
        "prompt": "Enregistre une dépense d'un montant de 15000 dans la catégorie 'loyer' payée par 'cheque' avec la description 'Loyer dépôt de test' et la date '2026-07-11'."
    },
    {
        "category": "Recipes",
        "task": "Créer une recette de production complète",
        "prompt": "Crée une recette nommée 'Recette Volaille Compliqué' pour le produit fini 'Aliment Volaille Compliqué' avec la note 'Formule hiver' contenant 100% de la matière première 'Orge Compliqué Test'."
    },
    {
        "category": "Production",
        "task": "Enregistrer un lot de production complet",
        "prompt": "Enregistre un lot de production pour le produit fini 'Aliment Volaille Compliqué' d'une quantité de 600 kg à la date '2026-07-11' avec le coût de production de 18000 et la note 'Production de nuit'."
    },
    {
        "category": "Insights / Queries",
        "task": "Rechercher des transactions complexes",
        "prompt": "Affiche toutes les transactions associées au client 'Client Test Compliqué' triées par date décroissante."
    }
]

async def execute_task_with_retry(prompt_info: dict, api_key: str, iteration: int) -> bool:
    category = prompt_info["category"]
    task_name = prompt_info["task"]
    prompt = prompt_info["prompt"]
    
    logger.info(f"--- [{category.upper()} - Itér. {iteration}/5] Exécution : {task_name} ---")
    messages = [{"role": "user", "parts": [{"text": prompt}]}]
    
    backoff = 2.0
    max_retries = 5
    
    for attempt in range(max_retries):
        confirmed_query = None
        error_occurred = False
        rate_limit_hit = False
        
        async def process_generator(hist: list, conf: str = None):
            nonlocal confirmed_query, error_occurred, rate_limit_hit
            current_confirmation = None
            
            async for event in run_assistant_agent_generator(hist, api_key, conf, user_role="admin"):
                evt_type = event.get("type")
                if evt_type == "text_chunk":
                    pass 
                elif evt_type == "confirmation_required":
                    current_confirmation = event.get("query")
                elif evt_type == "error":
                    err_msg = str(event.get("error", ""))
                    if "429" in err_msg or "quota" in err_msg.lower():
                        rate_limit_hit = True
                    else:
                        logger.error(f"  [Erreur Sabrina] : {err_msg}")
                        error_occurred = True
            return current_confirmation

        try:
            confirmed_query = await process_generator(messages)
            
            if rate_limit_hit:
                logger.warning(f"  [429 Rate Limit] Détecté. Attente de {backoff}s before retry...")
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
                
            if confirmed_query:
                # Auto-confirm write actions
                confirmed_query = await process_generator(messages, confirmed_query)
                
            if error_occurred:
                return False
            return True
            
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                logger.warning(f"  [429 Rate Limit Exception] Attente de {backoff}s before retry...")
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            logger.error(f"  [CRASH] : Exception rencontrée : {e}")
            return False
            
    logger.error(f"  [ÉCHEC] : Nombre maximum d'essais atteint suite à un blocage de quota API.")
    return False

async def main():
    parser = argparse.ArgumentParser(description="Sabrina Advanced Stress Test")
    parser.add_argument("--iterations", type=int, default=5, help="Nombre de répétitions pour chaque tâche")
    args = parser.parse_args()

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Clé API Gemini non configurée. Impossible de lancer le stress test.")
        sys.exit(1)
        
    total_iterations = args.iterations
    logger.info(f"Lancement du test de stress ADVANCED de Sabrina : {len(STRESS_PROMPTS)} tâches x {total_iterations} itérations.")
    
    success_count = 0
    failure_count = 0
    
    for iteration in range(1, total_iterations + 1):
        for item in STRESS_PROMPTS:
            # Short sleep between prompts to protect quota limits
            await asyncio.sleep(1.2)
            
            ok = await execute_task_with_retry(item, api_key, iteration)
            if ok:
                success_count += 1
            else:
                failure_count += 1
                
    print("\n" + "=" * 80)
    logger.info("BILAN GLOBAL DU STRESS TEST ADVANCED :")
    logger.info(f"  - Scénarios exécutés avec succès : {success_count} / {len(STRESS_PROMPTS) * total_iterations}")
    logger.info(f"  - Scénarios échoués : {failure_count} / {len(STRESS_PROMPTS) * total_iterations}")
    print("=" * 80)
    
    # Complete cleanup of all newly generated test data
    logger.info("Nettoyage de la base de données...")
    with db_manager.db_transaction() as conn:
        conn.execute("DELETE FROM purchases WHERE notes LIKE '%complique%' OR total = 34000")
        conn.execute("DELETE FROM sales WHERE total = 31200")
        conn.execute("DELETE FROM payments WHERE amount = 20000")
        conn.execute("DELETE FROM expenses WHERE description = 'Loyer dépôt de test' OR amount = 15000")
        conn.execute("DELETE FROM production_batches WHERE notes = 'Production de nuit' OR production_cost = 18000")
        conn.execute("DELETE FROM saved_recipes WHERE name = 'Recette Volaille Compliqué'")
        conn.execute("DELETE FROM raw_materials WHERE name = 'Orge Compliqué Test'")
        conn.execute("DELETE FROM finished_products WHERE name = 'Aliment Volaille Compliqué'")
        conn.execute("DELETE FROM clients WHERE name = 'Client Test Compliqué'")
        conn.execute("DELETE FROM suppliers WHERE name = 'Fournisseur Test Compliqué'")
        conn.commit()
    logger.info("Base de données nettoyée avec succès.")

    # Delete local note files from disk (if any test note was written)
    try:
        from app.core.runtime_paths import paths
        notes_dir = paths.notes_dir
        if notes_dir.exists():
            for f in notes_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        data = json.load(file)
                        if "Compliqué" in str(data.get("title", "")) or "Stress" in str(data.get("title", "")):
                            f.unlink()
                            logger.info(f"Fichier note de test supprimé : {f}")
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des notes physiques : {e}")

if __name__ == "__main__":
    asyncio.run(main())
