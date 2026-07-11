"""
intent.py — Intent classification and model routing logic for Sabrina.
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger("fabouanes.assistant.intent")

COMPLEX_KEYWORDS = {
    "modifier", "importer", "audit", "backup", "sql", "excel", "analyse", 
    "production", "sauvegarde", "restaurer", "supprimer", "update", 
    "delete", "créer", "creer", "crée", "cree", "vente", "achat", "versement",
    "payer", "dette", "solde", "rapport", "bénéfice", "benefice", "recette", "stock",
    "alerte", "alert", "mouvement", "facture", "bon", "pdf", "client", "fournisseur",
    "produit", "matière", "matiere"
}

def classify_intent(user_query: str) -> str:
    """
    Classify the complexity of the user query to route it to the appropriate model.
    
    Returns:
        "lite": For simple chats, greetings, theme configurations, navigation requests.
        "full": For business operations, reports, sql generation or complex analyses.
    """
    if not user_query:
        return "lite"
    
    query_lower = user_query.lower()
    words = set(re.findall(r'\w+', query_lower))
    
    # Check if any complex keyword matches a full word in the query
    if words & COMPLEX_KEYWORDS:
        return "full"
        
    # If the user query is very short (under 15 chars) and has no business keywords, it's likely a simple greeting
    if len(user_query.strip()) < 15:
        return "lite"
        
    # Default to lite for simple chat queries if no business keywords match
    return "lite"
