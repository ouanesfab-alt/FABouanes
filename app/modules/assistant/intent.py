"""
intent.py — Intent classification and model routing logic for Sabrina.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("fabouanes.assistant.intent")

COMPLEX_KEYWORDS = {
    "modifier",
    "importer",
    "audit",
    "backup",
    "sql",
    "excel",
    "analyse",
    "production",
    "sauvegarde",
    "restaurer",
    "supprimer",
    "update",
    "delete",
    "créer",
    "creer",
    "crée",
    "cree",
    "vente",
    "achat",
    "versement",
    "payer",
    "dette",
    "solde",
    "rapport",
    "bénéfice",
    "benefice",
    "recette",
    "stock",
    "alerte",
    "alert",
    "mouvement",
    "facture",
    "bon",
    "pdf",
    "client",
    "fournisseur",
    "produit",
    "matière",
    "matiere",
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
    words = set(re.findall(r"\w+", query_lower))

    # Check if any complex keyword matches a full word in the query
    if words & COMPLEX_KEYWORDS:
        return "full"

    # If the user query is very short (under 15 chars) and has no business keywords, it's likely a simple greeting
    if len(user_query.strip()) < 15:
        return "lite"

    # Default to lite for simple chat queries if no business keywords match
    return "lite"


def detect_multi_step_intents(user_query: str) -> list[str]:
    """Splits a multi-action user query into individual sequential sub-prompts if connected by conjunctions."""
    if not user_query:
        return []

    # Match conjunction splitters: "puis", "et ensuite", "apres ca", "après ça", or newlines
    pattern = r"\s+(?:puis|et\s+ensuite|après\s+ça|apres\s+ca|\n+)\s+"
    parts = [p.strip() for p in re.split(pattern, user_query, flags=re.IGNORECASE) if p.strip()]

    # Only return multi-step list if at least 2 distinct action phrases were found
    if len(parts) >= 2:
        return parts
    return [user_query.strip()]


DOMAIN_TABLE_MAPPING: dict[str, list[str]] = {
    "sales": [
        "sales",
        "raw_sales",
        "clients",
        "finished_products",
        "raw_materials",
        "sale_documents",
        "payments",
        "clients_with_stats",
    ],
    "purchases": [
        "purchases",
        "suppliers",
        "raw_materials",
        "finished_products",
        "purchase_documents",
        "supplier_payments",
    ],
    "stock": [
        "catalog_items",
        "raw_materials",
        "finished_products",
        "stock_movements",
        "stock_alerts",
    ],
    "clients": [
        "contacts",
        "clients",
        "clients_with_stats",
        "payments",
        "sales",
        "raw_sales",
    ],
    "suppliers": [
        "contacts",
        "suppliers",
        "purchases",
        "supplier_payments",
    ],
    "payments": [
        "payments",
        "supplier_payments",
        "clients",
        "suppliers",
        "clients_with_stats",
    ],
    "expenses": [
        "expenses",
    ],
    "production": [
        "production_batches",
        "production_batch_items",
        "saved_recipes",
        "saved_recipe_items",
        "raw_materials",
        "finished_products",
    ],
    "admin": [
        "app_settings",
        "backup_jobs",
        "audit_logs",
        "activity_logs",
    ],
}

DOMAIN_KEYWORD_MAPPING: dict[str, list[str]] = {
    "sales": [
        "vente", "ventes", "vendre", "sale", "sales", "ca", "chiffre d'affaire",
        "chiffre d'affaires", "bénéfice", "benefice", "marge", "facture", "bon de vente",
        "bl client", "client", "clients",
    ],
    "purchases": [
        "achat", "achats", "acheter", "purchase", "purchases", "fournisseur", "fournisseurs",
        "supplier", "suppliers", "bon d'achat", "bl fournisseur",
    ],
    "stock": [
        "stock", "stocks", "inventaire", "matière", "matiere", "matières", "matieres",
        "produit", "produits", "alerte", "alertes", "rupture", "seuil", "mouvement", "catalogue",
    ],
    "clients": [
        "client", "clients", "dette", "dettes", "créance", "creance", "crédit", "credit",
        "solde", "versement", "versements", "contact", "contacts",
    ],
    "suppliers": [
        "fournisseur", "fournisseurs", "supplier", "suppliers",
    ],
    "payments": [
        "versement", "versements", "avance", "avances", "paiement", "paiements",
        "reglement", "règlement", "solde", "payer", "dette",
    ],
    "expenses": [
        "dépense", "depense", "dépenses", "depenses", "charge", "charges", "frais",
        "loyer", "salaire", "salaires", "transport", "electricite", "carburant",
    ],
    "production": [
        "production", "produire", "fabriquer", "fabrication", "lot", "lots",
        "recette", "recettes", "formule", "formules", "batch",
    ],
    "admin": [
        "paramètre", "parametre", "paramètres", "parametres", "config", "configuration",
        "settings", "sauvegarde", "backup", "restaurer", "restore", "audit", "sécurité", "securite", "logs",
    ],
}


def detect_query_domains(user_query: str) -> list[str]:
    """Detects matching business domains from a user query."""
    if not user_query:
        return []
    q = user_query.lower()
    matched_domains = []
    for domain, kws in DOMAIN_KEYWORD_MAPPING.items():
        for kw in kws:
            if re.search(rf"\b{re.escape(kw)}\b", q):
                matched_domains.append(domain)
                break
    return matched_domains

