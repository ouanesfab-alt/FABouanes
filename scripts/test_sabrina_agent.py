#!/usr/bin/env python
"""
Agent Robustness and Evaluation Script for Sabrina.
Tests business commands, configuration, administration actions, SQL validations, and off-topic requests.
"""

import os
import sys
import json
import asyncio
import logging
import traceback
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sabrina.evaluation")

# Setup project root path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.core.db_helpers import db_manager
from app.modules.assistant.service import (
    run_assistant_agent_generator,
    get_gemini_api_key,
)

# Test prompts to execute against Sabrina (formatted in the correct Gemini schema)
TEST_PROMPTS = [
    {
        "name": "1. Off-topic (Météo/Général)",
        "prompt": "Quel temps fait-il à Alger aujourd'hui ?"
    },
    {
        "name": "2. Off-topic (Loisir/Créatif)",
        "prompt": "Raconte-moi une courte blague de développeur."
    },
    {
        "name": "3. Consultation (Enums/Schémas)",
        "prompt": "Quels sont les modes de paiement valides pour les règlements clients ?"
    },
    {
        "name": "4. Business Insights (Débiteurs)",
        "prompt": "Donne-moi l'analyse de nos clients débiteurs et de la croissance."
    },
    {
        "name": "5. UI & Theme modification",
        "prompt": "Modifie le thème de l'application pour le mettre en sombre."
    },
    {
        "name": "6. SQL Write & Confirmation",
        "prompt": "Crée un client nommé 'Yacine Simulation' avec le numéro '0555999999'."
    }
]

async def run_prompt_evaluation(name: str, prompt: str, api_key: str):
    print("\n" + "=" * 60)
    print(f"ÉVALUATION : {name}")
    print(f"Prompt utilisateur : '{prompt}'")
    print("=" * 60)
    
    # Must use Gemini's standard schema: parts -> text
    messages = [{"role": "user", "parts": [{"text": prompt}]}]
    
    tokens = []
    tool_calls = []
    confirmation_required = None
    
    try:
        # Run the generator exactly like the web streaming endpoint
        async for event in run_assistant_agent_generator(messages, api_key):
            evt_type = event.get("type")
            if evt_type == "text_chunk":
                chunk = event.get("text", "")
                tokens.append(chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()
            elif evt_type == "status":
                logger.info(f" -> [Statut] : {event.get('message')}")
            elif evt_type == "function_call":
                logger.info(f" -> [Appel d'outil] : {event.get('functionCall')}")
                tool_calls.append(event.get("functionCall", {}))
            elif evt_type == "confirmation_required":
                logger.info(f" -> [Confirmation Requise] : {event.get('message')}")
                confirmation_required = event
            elif evt_type == "error":
                logger.error(f" -> [Erreur] : {event.get('error')}")
            elif evt_type == "final_response":
                final_text = event.get("text", "")
                if not tokens: # If we haven't printed tokens progressively
                    print(final_text)
                    tokens.append(final_text)
                
        print("")
        
        # Summary for the prompt
        logger.info(f"[Bilan {name}] :")
        logger.info(f"  - Outils appelés : {len(tool_calls)} ({[tc.get('name') for tc in tool_calls]})")
        if confirmation_required:
            logger.info(f"  - État : En attente de confirmation de l'utilisateur.")
        else:
            logger.info(f"  - État : Terminé avec succès.")
            
    except Exception as e:
        logger.error(f"Échec critique sur le prompt '{prompt}' : {e}")
        traceback.print_exc()

async def main():
    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Clé API Gemini non configurée dans l'environnement ou la base de données. Impossible de lancer l'évaluation.")
        sys.exit(1)
        
    logger.info("Début des tests d'évaluation de Sabrina...")
    
    for tp in TEST_PROMPTS:
        await run_prompt_evaluation(tp["name"], tp["prompt"], api_key)
        
    logger.info("Évaluation de Sabrina terminée.")

if __name__ == "__main__":
    asyncio.run(main())
