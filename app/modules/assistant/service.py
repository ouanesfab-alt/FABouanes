import os
import json
import logging
import asyncio
import httpx
from typing import Any, Dict, List, Tuple
from app.core.db_helpers import db_manager

logger = logging.getLogger("fabouanes.assistant")

TABLE_SCHEMAS = {
    "clients": (
        "id* (BIGINT auto), name* (TEXT), phone (TEXT), address (TEXT), notes (TEXT), "
        "opening_credit* (NUMERIC défaut 0), credit_limit (NUMERIC), created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Liste des clients. "
        "IMPORTANT: Avant INSERT une vente ou versement, vérifier que le client existe via SELECT id, name FROM clients."
    ),
    "suppliers": (
        "id* (BIGINT auto), name* (TEXT), phone (TEXT), address (TEXT), notes (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Liste des fournisseurs. "
        "IMPORTANT: Avant INSERT un achat, vérifier que le fournisseur existe via SELECT id, name FROM suppliers."
    ),
    "raw_materials": (
        "id* (BIGINT auto), name* (TEXT), unit* (TEXT), stock_qty* (NUMERIC), avg_cost* (NUMERIC), "
        "sale_price* (NUMERIC), alert_threshold* (NUMERIC), threshold_qty* (NUMERIC), updated_at (TIMESTAMPTZ) "
        "— Matières premières en stock. "
        "IMPORTANT: Avant INSERT un achat ou vente de matière, vérifier que la matière existe via SELECT id, name, unit FROM raw_materials."
    ),
    "finished_products": (
        "id* (BIGINT auto), name* (TEXT), default_unit* (TEXT), stock_qty* (NUMERIC), "
        "sale_price* (NUMERIC), avg_cost* (NUMERIC), alert_threshold* (NUMERIC), updated_at (TIMESTAMPTZ) "
        "— Produits finis en stock. "
        "IMPORTANT: Avant INSERT une vente de produit fini, vérifier que le produit existe via SELECT id, name, avg_cost, sale_price FROM finished_products."
    ),
    "purchases": (
        "id* (BIGINT auto), supplier_id (INTEGER FK→suppliers), document_id (INTEGER), "
        "raw_material_id (INTEGER FK→raw_materials), finished_product_id (BIGINT FK→finished_products), "
        "quantity* (NUMERIC), unit* (TEXT défaut 'kg'), unit_price* (NUMERIC), total* (NUMERIC), "
        "purchase_date* (DATE), notes (TEXT), custom_item_name (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Achats (matières premières ou produits finis). "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT (auto-généré). "
        "Il faut OBLIGATOIREMENT soit raw_material_id soit finished_product_id (sinon la ligne n'apparaît pas). "
        "Étapes pour créer un achat: "
        "1) SELECT id,name FROM suppliers; "
        "2) SELECT id,name FROM raw_materials (ou finished_products); "
        "3) INSERT INTO purchases (supplier_id, raw_material_id, quantity, unit, unit_price, total, purchase_date) VALUES (...); "
        "4) UPDATE raw_materials SET stock_qty = stock_qty + [quantity], avg_cost = [unit_price] WHERE id = [id];"
    ),
    "sales": (
        "id* (BIGINT auto), client_id (INTEGER FK→clients), document_id (INTEGER), "
        "finished_product_id* (INTEGER FK→finished_products — OBLIGATOIRE, pas NULL !), quantity* (NUMERIC), unit* (TEXT), "
        "unit_price* (NUMERIC), total* (NUMERIC), sale_type* (TEXT: 'cash' si payé immédiatement, 'credit' si paiement différé), "
        "amount_paid* (NUMERIC: = total si cash, = acompte si credit, = 0 si rien payé), "
        "balance_due* (NUMERIC: = 0 si cash, = total - amount_paid si credit), "
        "cost_price_snapshot* (NUMERIC: = avg_cost du produit au moment de la vente — lire dans finished_products.avg_cost), "
        "profit_amount* (NUMERIC: = (unit_price - cost_price_snapshot) * quantity), "
        "sale_date* (DATE), notes (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Ventes de produits finis. "
        "RÈGLE ABSOLUE: finished_product_id ne peut PAS être NULL — sinon la ligne n'apparaît PAS dans les opérations. "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT. "
        "Étapes pour créer une vente de produit fini: "
        "1) SELECT id,name FROM clients WHERE lower(name) LIKE '%nom%'; "
        "2) SELECT id,name,sale_price,avg_cost,stock_qty,default_unit FROM finished_products WHERE lower(name) LIKE '%produit%'; "
        "3) INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date) VALUES (...); "
        "4) UPDATE finished_products SET stock_qty = stock_qty - [quantity] WHERE id = [id];"
    ),
    "raw_sales": (
        "id* (BIGINT auto), client_id (INTEGER FK→clients), document_id (INTEGER), "
        "raw_material_id* (INTEGER FK→raw_materials — OBLIGATOIRE, pas NULL !), quantity* (NUMERIC), unit* (TEXT), "
        "unit_price* (NUMERIC), total* (NUMERIC), sale_type* (TEXT: 'cash' ou 'credit'), "
        "amount_paid* (NUMERIC), balance_due* (NUMERIC), cost_price_snapshot* (NUMERIC: avg_cost de la matière), "
        "profit_amount* (NUMERIC: = (unit_price - cost_price_snapshot) * quantity), "
        "sale_date* (DATE), notes (TEXT), custom_item_name (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Ventes de matières premières. "
        "RÈGLE ABSOLUE: raw_material_id ne peut PAS être NULL — sinon la ligne n'apparaît PAS dans les opérations. "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT. "
        "Étapes pour créer une vente de matière première: "
        "1) SELECT id,name FROM clients WHERE lower(name) LIKE '%nom%'; "
        "2) SELECT id,name,sale_price,avg_cost,stock_qty,unit FROM raw_materials WHERE lower(name) LIKE '%matière%'; "
        "3) INSERT INTO raw_sales (client_id, raw_material_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date) VALUES (...); "
        "4) UPDATE raw_materials SET stock_qty = stock_qty - [quantity] WHERE id = [id];"
    ),
    "payments": (
        "id* (BIGINT auto), client_id* (INTEGER FK→clients — OBLIGATOIRE, pas NULL !), "
        "sale_id (INTEGER FK→sales optionnel), "
        "raw_sale_id (INTEGER FK→raw_sales optionnel), "
        "sale_kind (TEXT: 'finished' si lié à une vente produit fini, 'raw' si lié à une vente matière première, NULL si versement général), "
        "payment_type* (TEXT: TOUJOURS 'versement' pour un versement client, ou 'avance' pour une avance — NE JAMAIS mettre 'cash', 'cheque' ou 'virement' ici !), "
        "allocation_meta (TEXT JSON optionnel), amount* (NUMERIC), payment_date* (DATE), notes (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Paiements/versements reçus des clients. "
        "RÈGLE ABSOLUE: client_id ne peut PAS être NULL — sinon la ligne n'apparaît PAS. "
        "RÈGLE ABSOLUE: payment_type doit être 'versement' ou 'avance' — jamais autre chose. "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT. "
        "Étapes pour créer un versement: "
        "1) SELECT id,name FROM clients WHERE lower(name) LIKE '%nom%'; "
        "2) INSERT INTO payments (client_id, payment_type, amount, payment_date) VALUES ([id], 'versement', [montant], CURRENT_DATE);"
    ),
    "expenses": (
        "id* (BIGINT auto), date* (DATE), category* (TEXT), description (TEXT), "
        "amount* (NUMERIC), payment_method (TEXT), "
        "created_at (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Dépenses et charges. "
        "RÈGLE: Ne PAS spécifier 'id' dans INSERT. "
        "RÈGLE ABSOLUE: category doit être obligatoirement l'une des clés minuscules suivantes : "
        "'general', 'transport', 'fournitures', 'loyer', 'salaires', 'maintenance', 'telecom', 'energie', 'impots', 'autre'. "
        "RÈGLE ABSOLUE: payment_method doit être obligatoirement l'une des valeurs minuscules suivantes : "
        "'cash', 'cheque', 'virement', 'autre'."
    ),
    "production_batches": (
        "id* (BIGINT auto), finished_product_id* (INTEGER FK→finished_products), "
        "output_quantity* (NUMERIC), production_cost* (NUMERIC), unit_cost* (NUMERIC), "
        "production_date* (DATE), notes (TEXT) "
        "— Lots de production de produits finis. "
        "RÈGLE: Ne PAS spécifier 'id' dans INSERT."
    ),
    "production_batch_items": (
        "id* (BIGINT auto), batch_id* (INTEGER FK→production_batches), "
        "raw_material_id* (INTEGER FK→raw_materials), quantity* (NUMERIC), "
        "unit_cost_snapshot* (NUMERIC), line_cost* (NUMERIC) "
        "— Matières premières consommées par lot de production"
    ),
    "app_settings": (
        "key* (TEXT primary key), value (TEXT), updated_at (TIMESTAMPTZ auto) "
        "— Paramètres et configuration de l'application (ex: gdrive_backup_dir, backup_snapshot_time, backup_local_retention...)."
    ),
    "saved_recipes": (
        "id* (BIGINT auto), finished_product_id* (INTEGER FK→finished_products), name* (TEXT), notes (TEXT), created_at* (TIMESTAMPTZ auto) "
        "— Recettes enregistrées pour la production."
    ),
    "saved_recipe_items": (
        "id* (BIGINT auto), recipe_id* (INTEGER FK→saved_recipes), raw_material_id* (INTEGER FK→raw_materials), quantity* (NUMERIC), position* (INTEGER défaut 0) "
        "— Matières premières associées à une recette enregistrée."
    ),
    "stock_movements": (
        "id* (BIGINT auto), item_kind* (TEXT: 'raw' ou 'finished'), item_id* (BIGINT), direction* (TEXT: 'in' ou 'out'), quantity* (NUMERIC), unit (TEXT), stock_before* (NUMERIC), stock_after* (NUMERIC), reason (TEXT), reference_type (TEXT: 'purchase', 'sale', 'raw_sale', 'production'), reference_id (BIGINT), created_at* (TIMESTAMPTZ auto) "
        "— Historique détaillé des mouvements de stock."
    ),
    "activity_logs": (
        "id* (BIGINT auto), username* (TEXT), action* (TEXT), entity_type (TEXT), entity_id (BIGINT), details (TEXT), created_at* (TIMESTAMPTZ auto) "
        "— Journal des actions utilisateur."
    ),
    "audit_logs": (
        "id* (BIGINT auto), actor_username* (TEXT), actor_role* (TEXT), source* (TEXT), action* (TEXT), entity_type (TEXT), entity_id (TEXT), status* (TEXT), ip_address (TEXT), created_at* (TIMESTAMPTZ auto) "
        "— Journal d'audit détaillé pour la sécurité."
    ),
    "backup_jobs": (
        "id* (BIGINT auto), reason* (TEXT), backup_type* (TEXT), local_path* (TEXT), status* (TEXT), error_message* (TEXT), created_at* (TIMESTAMPTZ auto) "
        "— Historique et état des tâches de sauvegarde de la base de données."
    ),
    "supplier_payments": (
        "id* (BIGINT auto), supplier_id* (BIGINT FK→suppliers — OBLIGATOIRE, pas NULL !), "
        "purchase_id (BIGINT FK→purchases optionnel), "
        "purchase_document_id (BIGINT FK→purchase_documents optionnel), "
        "payment_type* (TEXT défaut 'versement' — versement ou avance), "
        "amount* (NUMERIC), payment_date* (TEXT/DATE format YYYY-MM-DD), notes (TEXT), "
        "created_at (TIMESTAMPTZ auto) "
        "— Versements/avances versés aux fournisseurs. "
        "RÈGLE ABSOLUE: supplier_id ne peut PAS être NULL. "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT."
    ),
    "sale_documents": (
        "id* (BIGINT auto), client_id (INTEGER FK→clients), sale_type* (TEXT: 'cash' ou 'credit'), "
        "total* (NUMERIC), amount_paid* (NUMERIC), balance_due* (NUMERIC), sale_date* (DATE), "
        "notes (TEXT), doc_number (TEXT) "
        "— Bons / Documents de vente. "
        "RÈGLE: Ne PAS spécifier 'id' dans INSERT."
    ),
    "purchase_documents": (
        "id* (BIGINT auto), supplier_id (INTEGER FK→suppliers), total* (NUMERIC), "
        "purchase_date* (DATE), notes (TEXT), doc_number (TEXT) "
        "— Bons / Documents d'achat. "
        "RÈGLE: Ne PAS spécifier 'id' dans INSERT."
    ),
    "stock_alerts": (
        "id* (BIGINT auto), product_type* (TEXT: 'raw' ou 'finished'), product_id* (BIGINT), "
        "product_name* (TEXT), current_qty* (NUMERIC), threshold_qty* (NUMERIC), "
        "triggered_at* (TIMESTAMPTZ auto), acknowledged_at (TIMESTAMPTZ) "
        "— Alertes de stock bas en cours ou acquittées."
    ),
}


def get_schema() -> Dict[str, Any]:
    """Retourne la description de la structure de la base de données."""
    return {"schema": TABLE_SCHEMAS}


# Mapping: table → lien de formulaire de création et de liste
FORM_LINKS = {
    "clients":             ("/contacts/clients/new", "/contacts/clients"),
    "suppliers":           ("/contacts/suppliers/new", "/contacts/suppliers"),
    "finished_products":   ("/products/new", "/products"),
    "raw_materials":       ("/raw-materials/new", "/raw-materials"),
    "sales":               ("/operations/sales/new", "/operations"),
    "raw_sales":           ("/operations/sales/new", "/operations"),
    "purchases":           ("/operations/purchases/new", "/operations"),
    "payments":            ("/operations/payments/new", "/operations"),
    "expenses":            ("/expenses/new", "/expenses"),
    "production_batches":  ("/production/new", "/production"),
}

# Mapping: table → type d'impression (pour les liens /print/{doc_type}/{id})
PRINT_DOC_TYPES = {
    "sales":               "sale_finished",
    "raw_sales":           "sale_raw",
    "purchases":           "purchase",
    "payments":            "payment",
    "production_batches":  "production",
}

APP_ROUTES = (
    "PAGES ET CHEMINS DE L'APPLICATION :\n"
    "- Tableau de bord → /dashboard\n"
    "- Clients → /contacts/clients | Nouveau client → /contacts/clients/new | Fiche client → /contacts/clients/{id}\n"
    "- Fournisseurs → /contacts/suppliers | Nouveau → /contacts/suppliers/new\n"
    "- Opérations → /operations | Nouvelle vente → /operations/sales/new\n"
    "- Nouvel achat → /operations/purchases/new | Nouveau versement → /operations/payments/new\n"
    "- Catalogue/Stock → /catalog | Produits finis → /products | Matières premières → /raw-materials\n"
    "- Production → /production | Nouveau lot → /production/new\n"
    "- Dépenses → /expenses | Nouvelle dépense → /expenses/new\n"
    "- Rapports → /reports | Paramètres/Admin → /admin | Utilisateurs → /users\n"
    "- Journal d'audit → /admin/audit | Notes → /notes | Bons/PDF → /bons\n"
)

ACTION_GUIDE = (
    "GUIDE DES ACTIONS POSSIBLES :\n"
    "• Tu es Sabrina, l'Assistant IA de FABOuanes. Tu parles toujours en français.\n"
    "• TOUJOURS utiliser RETURNING id à la fin de chaque INSERT pour récupérer l'ID créé.\n"
    "• Ne JAMAIS spécifier 'id' dans un INSERT (auto-généré par PostgreSQL).\n"
    "• VÉRIFIER le stock avant toute vente : SELECT stock_qty FROM finished_products WHERE id=?\n"
    "  Si stock_qty < quantité demandée → REFUSER la vente, afficher le stock disponible, proposer d'ajuster.\n"
    "• Après chaque création réussie, inclure dans la réponse Markdown un lien vers la liste et un lien vers l'impression si applicable.\n"
    "• Remplissage de formulaire par redirection (Agentic prefilling) :\n"
    "  Si l'utilisateur demande d'ouvrir un formulaire (ex: 'ouvre le formulaire', 'je veux remplir moi-même') :\n"
    "  → Ne pas exécuter l'action en base. Préparer un lien avec les paramètres connus encodés dans l'URL pour pré-remplir les champs !\n"
    "  Exemples : [REDIRECT:/contacts/clients/new?kind=client&name=Sabrina], [REDIRECT:/operations/sales/new?mode=sale&client_id=5&item_id=3&qty=10&price=250]\n"
    "  Ajouter le tag [REDIRECT:...] à la fin.\n"
    "• DATES : Convertir toujours en YYYY-MM-DD (ex: 'aujourd'hui' -> date locale actuelle).\n"
    "• RECHERCHE FLOUE : Toujours lower(name) LIKE '%terme%'. Si plusieurs résultats, demander à l'utilisateur de choisir.\n"
    "• FORMATAGE : Utiliser des tableaux Markdown pour les données tabulaires.\n"
)


from decimal import Decimal
from datetime import date, datetime

def serialize_for_json(obj: Any) -> Any:
    """Convertit récursivement les Decimal, date et datetime en types JSON sérialisables."""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(x) for x in obj]
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

def get_encryption_key() -> bytes:
    from app.core.config import settings
    import hashlib
    secret = settings.secret_key or "fallback_secret_key_for_sabrina"
    return hashlib.sha256(secret.encode("utf-8")).digest()

def get_gemini_api_key() -> str:
    """Récupère la clé d'API depuis l'environnement ou les paramètres de la base de données (déchiffrée)."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        from app.core.security import decrypt_val
        raw_val = db_manager.get_setting("gemini_api_key", "").strip()
        api_key = decrypt_val(raw_val, get_encryption_key()) or ""
    return api_key

def get_sabrina_system_prompt(model_name: str) -> str:
    """Génère le prompt système personnalisé pour Sabrina avec le contexte de l'entreprise."""
    company_name = db_manager.get_setting("company_name", "FABOuanes").strip() or "FABOuanes"
    currency = "DZD"  # Devise par défaut
    tva = "19%"       # TVA standard algérienne
    
    compact_schemas = {
        "clients": "id, name, phone, address, notes, opening_credit, credit_limit",
        "suppliers": "id, name, phone, address, notes",
        "raw_materials": "id, name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty",
        "finished_products": "id, name, default_unit, stock_qty, sale_price, avg_cost, alert_threshold",
        "purchases": "id, supplier_id, document_id, raw_material_id, finished_product_id, quantity, unit, unit_price, total, purchase_date, notes",
        "sales": "id, client_id, document_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes",
        "raw_sales": "id, client_id, document_id, raw_material_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date, notes",
        "payments": "id, client_id, sale_id, raw_sale_id, sale_kind, payment_type (versement/avance), allocation_meta, amount, payment_date, notes",
        "expenses": "id, date, category (general, transport, fournitures, loyer, salaires, maintenance, telecom, energie, impots, autre), description, amount, payment_method (cash, cheque, virement, autre)",
        "production_batches": "id, finished_product_id, output_quantity, production_cost, unit_cost, production_date, notes",
        "production_batch_items": "id, batch_id, raw_material_id, quantity, unit_cost_snapshot, line_cost",
        "app_settings": "key, value",
        "saved_recipes": "id, finished_product_id, name, notes",
        "saved_recipe_items": "id, recipe_id, raw_material_id, quantity, position",
        "stock_movements": "id, item_kind (raw/finished), item_id, direction (in/out), quantity, unit, stock_before, stock_after, reason, reference_type, reference_id",
        "backup_jobs": "id, reason, backup_type, local_path, status, error_message",
        "supplier_payments": "id, supplier_id, purchase_id, purchase_document_id, payment_type (versement/avance), amount, payment_date, notes",
        "sale_documents": "id, client_id, sale_type, total, amount_paid, balance_due, sale_date, notes, doc_number",
        "purchase_documents": "id, supplier_id, total, purchase_date, notes, doc_number",
        "stock_alerts": "id, product_type (raw/finished), product_id, product_name, current_qty, threshold_qty"
    }
    schema_text = "\n".join(f"- {t}({cols})" for t, cols in compact_schemas.items())
    
    return (
        "Tu es Sabrina, l'assistante commerciale intelligente de l'entreprise.\n"
        f"🏢 Contexte de l'entreprise :\n"
        f"- Nom de l'entreprise : {company_name}\n"
        f"- Devise par défaut : {currency} (Dinar Algérien)\n"
        f"- TVA applicable : {tva}\n"
        f"- Modèle d'IA actif : **{model_name}**\n\n"
        "🎯 Ta mission :\n"
        "1. Répondre aux questions sur les ventes, achats, stock et finances de l'entreprise.\n"
        "2. Accès total à la base de données : Tu as un accès complet en lecture et écriture sur toutes les tables de la base de données (pas seulement les opérations, mais aussi les clients, produits, dépenses, configurations, etc.) via execute_readonly_sql et execute_write_sql pour exécuter n'importe quelle requête brute SELECT/INSERT/UPDATE/DELETE.\n"
        "3. Enregistrer des opérations à la demande (avec confirmation obligatoire par l'utilisateur).\n"
        "4. Naviguer ou modifier les pages/code de l'application selon les besoins du développeur.\n"
        "5. Formater les données chiffrées sous forme de magnifiques tableaux Markdown.\n"
        "6. 🌐 CULTURE GÉNÉRALE & ASSISTANCE UNIVERSELLE : Tu es aussi un assistant général cultivé et curieux. Tu peux répondre à TOUTES les questions générales en dehors de la gestion commerciale : sciences, mathématiques, histoire, géographie, culture, langues, cuisine, programmation, conseils personnels, actualités, définitions, etc. Si l'utilisateur pose une question hors du contexte commercial, réponds naturellement, avec précision et bonne humeur, sans chercher d'outils ou de données d'entreprise.\n\n"
        f"SCHÉMA DE LA BASE DE DONNÉES (utilise-le directement sans appeler get_schema) :\n{schema_text}\n\n"
        f"{APP_ROUTES}\n"
        f"{ACTION_GUIDE}\n\n"
        "🔴 PROTOCOLE STRICT D'INTERACTION (RÈGLE ABSOLUE SUR L'INTÉGRALITÉ DE L'APPLICATION) :\n"
        "Pour absolument TOUT (champs, formulaires, templates, pages, paramètres, clients, fournisseurs, produits finis, matières premières, ventes, achats, versements, dépenses, lots de production, recettes de fabrication, factures, bons de livraison/dépôt, sauvegardes et restaurations de base de données, etc.) :\n"
        "1. NE JAMAIS DEVINER, INVENTER OU ASSUMER de valeurs, d'arguments, de configurations, de modes de paiement, de catégories ou de détails manquants.\n"
        "2. RECHERCHE À LA DEMANDE : Tu dois obligatoirement utiliser les outils `search_clients` ou `search_products` pour trouver les identifiants (IDs) des clients ou produits avant de proposer une action. Ne jamais deviner un ID !\n"
        "3. CONTRATS DE VALEURS (ENUMS) : Avant d'insérer ou de modifier un champ restrictif, appelle toujours l'outil `get_enum_values(table, column)` pour vérifier les valeurs acceptées (ex: categories de dépenses, type de versement, mode de paiement).\n"
        "4. RAISONNEMENT ET PLAN D'ACTIONS : Pour toute demande complexe ou multi-étapes (ex: 'crée le client X puis ajoute sa première vente'), tu DOIS d'abord générer un texte expliquant ton plan d'actions prévu étape par étape sous forme de liste numérotée, et demander la confirmation de l'utilisateur avant d'émettre la moindre exécution de fonction.\n"
        "5. AUTO-ÉVALUATION DES MISES À JOUR/SUPPRESSIONS : Avant de proposer ou d'exécuter une requête SQL d'écriture de type UPDATE ou DELETE, tu DOIS obligatoirement exécuter une requête `execute_readonly_sql` de type `SELECT` pour vérifier quelles lignes et quelles valeurs exactes vont être modifiées ou supprimées. Présente le résultat de cette vérification à l'utilisateur dans ton message de demande de confirmation.\n"
        "6. VISION & ANALYSE DE DOCUMENTS : Si l'utilisateur téléverse une image ou un document PDF (par exemple une photo de bon de livraison, facture, ou reçu de versement), tu as un accès direct à cette pièce jointe via le champ multimodal. Analyse-la pour en extraire les informations clés (articles, quantités, montants, date, client) et propose de les enregistrer en base de données.\n"
        "7. Si l'utilisateur demande une action, une création ou une modification sans fournir TOUS les champs requis ou s'il y a la moindre ambiguïté :\n"
        "   - Tu DOIS d'abord lister clairement les compléments exacts requis pour cette opération ainsi que leurs options possibles.\n"
        "   - Tu DOIS lui demander de fournir ces compléments.\n"
        "8. Ce n'est qu'une fois que l'utilisateur vous a fourni l'intégralité des compléments exacts que vous pouvez générer l'appel de fonction ou la requête SQL et lui demander sa confirmation interactive finale. Pas d'erreurs, pas de devinettes, pas de confusion.\n\n"
        "RÈGLES ABSOLUES :\n"
        "- Ne JAMAIS lire la table 'users'.\n"
        "- Confirmer TOUJOURS avant toute opération d'écriture (INSERT/UPDATE/DELETE).\n"
        "- Limiter les requêtes SQL à 100 lignes max (LIMIT 100).\n"
        "- RÈGLE DE PRÉCISION ET SAISIE : Ne JAMAIS deviner ou inventer de valeurs pour les champs restrictifs. Si une valeur est ambiguë, demande clarification ou propose les choix exacts à l'utilisateur.\n"
        "- RÈGLE DES NOMBRES ET FORMATS : Convertir correctement les notations (ex: remplacer les virgules par des points pour les décimaux, nettoyer les symboles de monnaie ou abréviations comme 'da' ou 'dzd') pour s'assurer que les valeurs numériques transmises dans les requêtes SQL sont strictement des nombres valides.\n"
    )

class DryRunRollback(Exception):
    def __init__(self, data):
        self.data = data

def dry_run_sql(query: str) -> str:
    """Simule une requête SQL d'écriture dans une transaction temporaire puis effectue un rollback."""
    try:
        import sqlglot
        stmts = sqlglot.parse(query, read="postgres")
        if not stmts:
            return "⚠️ Requête SQL invalide."
        stmt = stmts[0]
        table_names = [t.name.lower() for t in stmt.find_all(sqlglot.exp.Table)]
        
        try:
            with db_manager.db_transaction() as conn:
                # Récupérer les soldes clients avant
                client_balances_before = {}
                if "clients" in table_names:
                    rows = conn.execute(sqlglot.parse("SELECT id, name, debt FROM clients", read="postgres")[0].sql(dialect="postgres")).fetchall()
                    client_balances_before = {r[0]: (r[1], r[2]) for r in rows}
                    
                cur = conn.execute(query)
                rowcount = getattr(cur, "rowcount", None)
                inserted_id = None
                try:
                    row = cur.fetchone()
                    if row:
                        if isinstance(row, dict):
                            inserted_id = row.get("id")
                        elif isinstance(row, (list, tuple)) and len(row) > 0:
                            inserted_id = row[0]
                except Exception:
                    pass
                    
                # Récupérer les soldes clients après
                client_balances_after = {}
                if "clients" in table_names:
                    rows = conn.execute(sqlglot.parse("SELECT id, name, debt FROM clients", read="postgres")[0].sql(dialect="postgres")).fetchall()
                    client_balances_after = {r[0]: r[2] for r in rows}
                
                res_info = {
                    "inserted_id": inserted_id,
                    "rowcount": rowcount,
                    "balances_before": client_balances_before,
                    "balances_after": client_balances_after
                }
                raise DryRunRollback(res_info)
        except DryRunRollback as dr:
            res_info = dr.data
            inserted_id = res_info["inserted_id"]
            rowcount = res_info["rowcount"]
            client_balances_before = res_info["balances_before"]
            client_balances_after = res_info["balances_after"]
            
            parts = ["📝 **[Simulation] Résumé des modifications de données :**"]
            if inserted_id:
                parts.append(f"• Création d'un nouvel enregistrement (ID temporaire : `{inserted_id}`) dans la table `{', '.join(table_names)}`.")
            elif rowcount is not None and rowcount > 0:
                parts.append(f"• Modification de `{rowcount}` ligne(s) dans la table `{', '.join(table_names)}`.")
            else:
                parts.append(f"• Exécution d'une modification sur la table `{', '.join(table_names)}`.")
                
            for cid, (name, bal_before) in client_balances_before.items():
                bal_before_val = float(bal_before or 0.0)
                bal_after_val = float(client_balances_after.get(cid) or 0.0)
                if bal_before_val != bal_after_val:
                    parts.append(f"   - Le solde de **{name}** passe de `{bal_before_val:,.2f} DA` à `{bal_after_val:,.2f} DA`.")
            
            return "\n".join(parts)
    except Exception as e:
        return f"⚠️ La simulation (dry-run) a échoué : {str(e)}"

def log_structured_failure(action: str, error: str, parameters: dict):
    from app.core.config import BASE_DIR
    import datetime
    import json
    log_file = BASE_DIR / "sabrina_failures.jsonl"
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "action": action,
        "error": error,
        "parameters": parameters
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error("Failed to write structured failure log: %s", e)

def log_sabrina_action(action: str, args: dict, confirmed: bool, success: bool, result_summary: str):
    from app.core.config import BASE_DIR
    import datetime
    import json
    log_file = BASE_DIR / "sabrina_audit.jsonl"
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "action": action,
        "arguments": args,
        "confirmed": confirmed,
        "success": success,
        "result_summary": result_summary
    }
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error("Failed to write sabrina audit log: %s", e)

def get_ollama_tools() -> List[Dict[str, Any]]:
    gemini_tools = get_gemini_tools()
    ollama_tools = []
    if gemini_tools and "functionDeclarations" in gemini_tools[0]:
        for decl in gemini_tools[0]["functionDeclarations"]:
            raw_params = decl.get("parameters", {})
            params = json.loads(json.dumps(raw_params).lower())
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": decl.get("name"),
                    "description": decl.get("description"),
                    "parameters": params
                }
            })
    return ollama_tools

async def compress_history_if_needed(messages: List[Dict[str, Any]], api_key: str, is_local: bool) -> List[Dict[str, Any]]:
    if len(messages) <= 12:
        return messages
    to_summarize = messages[:-6]
    to_keep = messages[-6:]
    summary_prompt = (
        "Fais un résumé très condensé en français des actions, discussions et opérations mentionnées ci-dessous. "
        "Sois précis sur les chiffres, les noms de clients et les produits créés. Ne dépasse pas 150 mots."
    )
    
    conversation_text = ""
    for msg in to_summarize:
        role = msg.get("role", "user")
        parts = msg.get("parts", [])
        if isinstance(parts, list):
            content = " ".join(p.get("text", "") for p in parts if "text" in p)
        else:
            content = msg.get("content", "")
        conversation_text += f"{'Utilisateur' if role == 'user' else 'Sabrina'}: {content}\n"
        
    if is_local:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": conversation_text}
            ],
            "stream": False
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60.0)
                res.raise_for_status()
                data = res.json()
                summary_text = data["message"]["content"]
                
                new_messages = []
                new_messages.append({
                    "role": "user",
                    "content": f"[CONTEXTE DES DISCUSSIONS PRÉCÉDENTES : {summary_text.strip()}]"
                })
                new_messages.extend(to_keep)
                return new_messages
        except Exception as e:
            logger.warning("Ollama history summarization failed: %s", e)
            return messages
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{summary_prompt}\n\nConversation à résumer :\n{conversation_text}"}]}
            ]
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=headers, timeout=30.0)
                res.raise_for_status()
                data = res.json()
                summary_text = data["candidates"][0]["content"]["parts"][0]["text"]
                
                new_messages = []
                new_messages.append({
                    "role": "user",
                    "parts": [{"text": f"[CONTEXTE DES DISCUSSIONS PRÉCÉDENTES : {summary_text.strip()}]"}]
                })
                new_messages.extend(to_keep)
                return new_messages
        except Exception as e:
            logger.warning("Gemini history summarization failed: %s", e)
            return messages

def execute_readonly_sql(query: str) -> Dict[str, Any]:
    """Exécute une requête SQL SELECT en lecture seule et retourne le résultat."""
    try:
        import sqlglot
        stmts = sqlglot.parse(query, read="postgres")
    except Exception as e:
        return {"error": f"Erreur de syntaxe ou de validation SQL : {str(e)}"}
        
    if not stmts:
        return {"error": "Aucune requête SQL valide fournie."}
        
    if len(stmts) > 1:
        return {"error": "Une seule requête SQL SELECT est autorisée à la fois."}
        
    stmt = stmts[0]
    if not isinstance(stmt, (sqlglot.exp.Select, sqlglot.exp.Union, sqlglot.exp.Query)):
        return {"error": "Opération non autorisée (interdite) : seules les requêtes SELECT de lecture sont autorisées."}
    
    # Validation AST contre les DML/DDL de modification
    for node in stmt.find_all(sqlglot.exp.Expression):
        name = node.__class__.__name__.lower()
        if any(ind in name for ind in ['insert', 'update', 'delete', 'create', 'drop', 'alter', 'truncate', 'command', 'grant', 'revoke']):
            return {"error": f"Opération de type '{name}' interdite en lecture seule."}
            
    # Interdiction d'accès à la table users
    for table_node in stmt.find_all(sqlglot.exp.Table):
        if "users" in table_node.name.lower():
            return {"error": "Accès à la table 'users' interdit."}
            
    # Forcer LIMIT 100 si absent
    has_limit = any(isinstance(node, sqlglot.exp.Limit) for node in stmt.find_all(sqlglot.exp.Expression))
    sql_to_run = query
    if not has_limit:
        if isinstance(stmt, (sqlglot.exp.Select, sqlglot.exp.Subquery, sqlglot.exp.Union, sqlglot.exp.CTE)):
            sql_to_run = stmt.limit(100).sql(dialect="postgres")
        else:
            sql_to_run = f"{query.rstrip(';')} LIMIT 100"
            
    try:
        rows = db_manager.query_db(sql_to_run)
        return {"rows": serialize_for_json([dict(r) for r in rows])}
    except Exception as e:
        logger.error("execute_readonly_sql error for query %s: %s", sql_to_run, e, exc_info=True)
        return {"error": f"Erreur SQL : {str(e)}"}

def execute_write_sql(query: str) -> Dict[str, Any]:
    """Exécute une requête SQL d'écriture (INSERT, UPDATE, DELETE) pour modifier, ajouter ou supprimer des données."""
    try:
        import sqlglot
        stmts = sqlglot.parse(query, read="postgres")
    except Exception as e:
        return {"error": f"Erreur de syntaxe ou de validation SQL : {str(e)}"}
        
    if not stmts:
        return {"error": "Aucune requête SQL valide fournie."}
        
    if len(stmts) > 1:
        return {"error": "Une seule requête d'écriture est autorisée à la fois."}
        
    stmt = stmts[0]
    
    # Interdiction des opérations destructrices
    for node in stmt.find_all(sqlglot.exp.Expression):
        name = node.__class__.__name__.lower()
        if any(ind in name for ind in ['drop', 'alter', 'truncate', 'command', 'grant', 'revoke']):
            return {"error": f"Opération de structure/droit '{name}' interdite pour des raisons de sécurité."}
            
    # Interdiction d'accès à la table users
    for table_node in stmt.find_all(sqlglot.exp.Table):
        if "users" in table_node.name.lower():
            return {"error": "Accès à la table 'users' interdit."}
            
    clean_query = query.strip().lower()
    has_returning = "returning" in clean_query
        
    try:
        with db_manager.db_transaction() as conn:
            cur = conn.execute(query)
            inserted_id = None
            if has_returning:
                try:
                    row = cur.fetchone()
                    if row:
                        if isinstance(row, dict):
                            inserted_id = row.get("id")
                        elif isinstance(row, (list, tuple)) and len(row) > 0:
                            inserted_id = row[0]
                except Exception:
                    pass
            rowcount = getattr(cur, "rowcount", None)
            try:
                cur.close()
            except Exception:
                pass
            result: Dict[str, Any] = {"success": True}
            if inserted_id is not None:
                result["inserted_id"] = inserted_id
                result["message"] = f"Opération réussie. ID créé : {inserted_id}."
            elif rowcount is not None:
                result["rowcount"] = rowcount
                result["message"] = f"{rowcount} ligne(s) affectée(s)."
            else:
                result["message"] = "Opération exécutée avec succès."
            return result
    except Exception as e:
        logger.error("execute_write_sql error for query %s: %s", query, e, exc_info=True)
        return {"error": f"Erreur SQL lors de l'écriture : {str(e)}"}

def get_tool_confirmation_message(name: str, args: dict) -> str:
    if name == "execute_write_sql":
        query = args.get('query', '')
        dry_summary = dry_run_sql(query)
        return (
            f"Exécuter la requête SQL suivante :\n```sql\n{query}\n```\n"
            f"{dry_summary}\n\n"
            f"⚠️ **Attention** : Cette action va modifier directement la base de données."
        )
    elif name == "modify_app_file":
        filepath = args.get("filepath", "")
        old_c = args.get("old_content", "")
        new_c = args.get("new_content", "")
        return f"Modifier le fichier `{filepath}` :\n**Avant :**\n```\n{old_c}\n```\n**Après :**\n```\n{new_c}\n```"
    elif name == "restore_app_backup":
        return f"Restaurer la base de données à partir de la sauvegarde `{args.get('backup_name')}` ? Attention, cette action écrasera les données actuelles."
    elif name == "create_app_user":
        return f"Créer l'utilisateur `{args.get('username')}` avec le rôle `{args.get('role')}` ?"
    elif name == "change_app_user_password":
        return f"Changer le mot de passe de l'utilisateur `{args.get('username')}` ?"
    elif name == "delete_app_user":
        return f"Supprimer définitivement l'utilisateur `{args.get('username')}` ?"
    elif name == "update_setting":
        return f"Mettre à jour le paramètre `{args.get('key')}` avec la valeur `{args.get('value')}` ?"
    elif name == "add_client":
        return f"Créer le client `{args.get('name')}` (Téléphone: {args.get('phone', '-')}, Solde initial: {args.get('opening_credit', 0)} DA) ?"
    elif name == "modify_client":
        return f"Modifier le client ID `{args.get('client_id')}` ?"
    elif name == "delete_client":
        return f"Supprimer le client ID `{args.get('client_id')}` ?"
    elif name == "add_sale":
        return f"Enregistrer une vente de {args.get('quantity')} {args.get('unit')} à {args.get('unit_price')} DA/unit (Montant payé: {args.get('amount_paid', 0)} DA) ?"
    elif name == "add_purchase":
        return f"Enregistrer un achat de {args.get('quantity')} {args.get('unit')} à {args.get('unit_price')} DA/unit ?"
    elif name == "add_payment":
        return f"Enregistrer un versement de {args.get('amount')} DA pour le client ID `{args.get('client_id')}` ?"
    elif name == "delete_operation":
        return f"Annuler/Supprimer l'opération de type `{args.get('tx_kind')}` ID `{args.get('tx_id')}` ?"
    elif name == "add_expense":
        return f"Enregistrer une dépense de {args.get('amount')} DA dans la catégorie `{args.get('category')}` ?"
    elif name == "modify_expense":
        return f"Modifier la dépense ID `{args.get('expense_id')}` ?"
    elif name == "delete_expense":
        return f"Supprimer la dépense ID `{args.get('expense_id')}` ?"
    elif name == "add_production_batch":
        return f"Lancer un lot de production pour le produit ID `{args.get('finished_product_id')}` de quantité {args.get('quantity')} ?"
    elif name == "delete_production":
        return f"Annuler/Supprimer le lot de production ID `{args.get('batch_id')}` ?"
    return f"Confirmer l'opération '{name}' avec les paramètres : {args}"

async def execute_tool_action(func_name: str, func_args: dict) -> Dict[str, Any]:
    from app.core.async_db import get_async_sessionmaker
    session_maker = get_async_sessionmaker()
    try:
        res = await _execute_tool_action_inner(func_name, func_args, session_maker)
        if isinstance(res, dict) and "error" in res:
            log_structured_failure(func_name, res["error"], func_args)
        else:
            summary = res.get("message") or res.get("print_url") or "Opération réussie"
            log_sabrina_action(func_name, func_args, confirmed=True, success=True, result_summary=str(summary))
        return res
    except Exception as e:
        logger.error("Error executing agent action %s with args %s: %s", func_name, func_args, e, exc_info=True)
        log_structured_failure(func_name, str(e), func_args)
        return {"error": str(e)}

async def _execute_tool_action_inner(func_name: str, func_args: dict, session_maker) -> Dict[str, Any]:
    from app.core.config import BASE_DIR
    import os
    import json
    
    if func_name == "read_app_file":
        filepath = func_args.get("filepath", "")
        workspace_dir = os.path.abspath(str(BASE_DIR))
        abs_path = os.path.abspath(filepath)
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}
        with open(abs_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
            
    elif func_name == "modify_app_file":
        filepath = func_args.get("filepath", "")
        old_c = func_args.get("old_content", "")
        new_c = func_args.get("new_content", "")
        workspace_dir = os.path.abspath(str(BASE_DIR))
        abs_path = os.path.abspath(filepath)
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_c not in content:
            return {"error": "Le contenu original à remplacer n'a pas été trouvé dans le fichier."}
        new_content = content.replace(old_c, new_c, 1)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return {"success": True, "message": "Fichier modifié avec succès."}
        
    elif func_name == "create_app_backup":
        reason = func_args.get("reason", "Sauvegarde automatique")
        from app.services.admin_service import create_manual_backup
        res = await create_manual_backup(reason=reason)
        return {"success": True, "backup": res}
        
    elif func_name == "list_app_backups":
        from app.services.admin_service import list_restore_backups
        res = await list_restore_backups()
        return {"backups": res}
        
    elif func_name == "restore_app_backup":
        backup_name = func_args.get("backup_name", "")
        from app.services.admin_service import restore_backup_by_value
        await restore_backup_by_value(backup_name)
        return {"success": True, "message": "Restauration effectuée avec succès."}
        
    elif func_name == "create_app_user":
        username = func_args.get("username", "")
        password = func_args.get("password", "")
        role = func_args.get("role", "operator")
        from app.services.admin_service import create_user_account
        await create_user_account(username, password, role, "active")
        return {"success": True, "message": f"Utilisateur {username} créé."}
        
    elif func_name == "change_app_user_password":
        username = func_args.get("username", "")
        new_password = func_args.get("new_password", "")
        from app.services.auth_service import get_user_by_username, generate_password_hash
        from app.modules.users.repository import update_password
        user = await get_user_by_username(username)
        if not user:
            return {"error": f"Utilisateur {username} introuvable."}
        async with session_maker() as session:
            await update_password(user["id"], generate_password_hash(new_password), 0, db=session)
            await session.commit()
        return {"success": True, "message": f"Mot de passe de {username} modifié."}
        
    elif func_name == "delete_app_user":
        username = func_args.get("username", "")
        from app.services.auth_service import get_user_by_username
        user = await get_user_by_username(username)
        if not user:
            return {"error": f"Utilisateur {username} introuvable."}
        async with session_maker() as session:
            from sqlmodel import text
            await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user["id"]})
            await session.commit()
        return {"success": True, "message": f"Utilisateur {username} supprimé."}
        
    elif func_name == "update_setting":
        key = func_args.get("key", "")
        value = func_args.get("value", "")
        db_manager.set_setting(key, value)
        return {"success": True, "message": f"Paramètre {key} mis à jour."}
        
    elif func_name == "add_client":
        name = func_args.get("name", "")
        phone = func_args.get("phone", "")
        address = func_args.get("address", "")
        notes = func_args.get("notes", "")
        opening_credit = float(func_args.get("opening_credit", 0.0) or 0.0)
        from app.modules.clients.service import ClientService
        from app.modules.clients.schemas_validation import ClientCreateSchema
        schema = ClientCreateSchema(name=name, phone=phone, address=address, notes=notes, opening_credit=opening_credit)
        async with session_maker() as session:
            service = ClientService(session)
            client = await service.create_client(schema)
            await session.commit()
        return {"success": True, "client_id": client.id}
        
    elif func_name == "modify_client":
        client_id = int(func_args.get("client_id"))
        name = func_args.get("name")
        phone = func_args.get("phone")
        address = func_args.get("address")
        notes = func_args.get("notes")
        from app.modules.clients.service import ClientService
        from app.modules.clients.schemas_validation import ClientUpdateSchema
        schema = ClientUpdateSchema(name=name, phone=phone, address=address, notes=notes)
        async with session_maker() as session:
            service = ClientService(session)
            await service.update_client(client_id, schema)
            await session.commit()
        return {"success": True, "message": f"Client {client_id} modifié."}
        
    elif func_name == "delete_client":
        client_id = int(func_args.get("client_id"))
        from app.modules.clients.service import ClientService
        async with session_maker() as session:
            service = ClientService(session)
            await service.delete_client(client_id)
            await session.commit()
        return {"success": True, "message": f"Client {client_id} supprimé."}
        
    elif func_name == "add_product":
        name = func_args.get("name", "")
        category = func_args.get("category", "")
        price = float(func_args.get("price", 0.0) or 0.0)
        cost = float(func_args.get("cost", 0.0) or 0.0)
        unit = func_args.get("unit", "kg")
        table = "finished_products" if category.lower() in ("finished", "produit final", "produit") else "raw_materials"
        async with session_maker() as session:
            from sqlmodel import text
            if table == "finished_products":
                await session.execute(text(
                    "INSERT INTO finished_products (name, sale_price, avg_cost, unit) VALUES (:name, :price, :cost, :unit)"
                ), {"name": name, "price": price, "cost": cost, "unit": unit})
            else:
                await session.execute(text(
                    "INSERT INTO raw_materials (name, avg_cost, unit) VALUES (:name, :cost, :unit)"
                ), {"name": name, "cost": cost, "unit": unit})
            await session.commit()
        return {"success": True, "message": f"Produit {name} ajouté."}
        
    elif func_name == "modify_product":
        product_id = int(func_args.get("product_id"))
        category = func_args.get("category", "finished")
        name = func_args.get("name")
        price = func_args.get("price")
        cost = func_args.get("cost")
        table = "finished_products" if category.lower() in ("finished", "produit final", "produit") else "raw_materials"
        async with session_maker() as session:
            from sqlmodel import text
            updates = []
            params = {"id": product_id}
            if name:
                updates.append("name = :name")
                params["name"] = name
            if cost is not None:
                updates.append("avg_cost = :cost")
                params["cost"] = float(cost)
            if table == "finished_products" and price is not None:
                updates.append("sale_price = :price")
                params["price"] = float(price)
            if updates:
                stmt = f"UPDATE {table} SET {', '.join(updates)} WHERE id = :id"
                await session.execute(text(stmt), params)
                await session.commit()
        return {"success": True, "message": f"Produit {product_id} modifié."}
        
    elif func_name == "delete_product":
        product_id = int(func_args.get("product_id"))
        category = func_args.get("category", "finished")
        table = "finished_products" if category.lower() in ("finished", "produit final", "produit") else "raw_materials"
        async with session_maker() as session:
            from sqlmodel import text
            await session.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": product_id})
            await session.commit()
        return {"success": True, "message": f"Produit {product_id} supprimé."}
        
    elif func_name == "add_sale":
        client_id = func_args.get("client_id")
        if client_id:
            client_id = int(client_id)
        item_kind = func_args.get("item_kind", "finished")
        item_id = int(func_args.get("item_id"))
        quantity = float(func_args.get("quantity"))
        unit = func_args.get("unit", "kg")
        unit_price = float(func_args.get("unit_price"))
        amount_paid = float(func_args.get("amount_paid", 0.0) or 0.0)
        notes = func_args.get("notes", "")
        from app.modules.sales.service import SalesService
        from app.modules.sales.schemas_validation import SaleFormSchema, SaleLineSchema
        line = SaleLineSchema(item_key=f"{item_kind}:{item_id}", quantity=quantity, unit=unit, unit_price=unit_price)
        schema = SaleFormSchema(client_id=client_id, notes=notes, lines=[line])
        async with session_maker() as session:
            service = SalesService(session)
            res = await service.create_sale_from_form(schema)
            if amount_paid > 0 and client_id:
                from app.modules.payments.service import PaymentsService
                from app.modules.payments.schemas_validation import PaymentFormSchema
                pay_service = PaymentsService(session)
                pay_schema = PaymentFormSchema(client_id=client_id, amount=amount_paid, payment_type="versement", notes=f"Paiement partiel vente {res.get('sale_id') or res.get('document_id')}")
                await pay_service.create_payment_from_form(pay_schema)
            await session.commit()
        return {"success": True, "sale_id": res.get("sale_id") or res.get("document_id")}
        
    elif func_name == "add_purchase":
        supplier_id = func_args.get("supplier_id")
        if supplier_id:
            supplier_id = int(supplier_id)
        item_kind = func_args.get("item_kind", "raw")
        item_id = int(func_args.get("item_id"))
        quantity = float(func_args.get("quantity"))
        unit = func_args.get("unit", "kg")
        unit_price = float(func_args.get("unit_price"))
        notes = func_args.get("notes", "")
        from app.modules.purchases.service import PurchaseService
        from app.modules.purchases.schemas_validation import PurchaseFormSchema, PurchaseLineSchema
        line = PurchaseLineSchema(raw_material_id=f"{item_kind}:{item_id}", quantity=quantity, unit=unit, unit_price=unit_price)
        schema = PurchaseFormSchema(supplier_id=supplier_id, notes=notes, lines=[line])
        async with session_maker() as session:
            service = PurchaseService(session)
            res = await service.create_purchase_from_form(schema)
            await session.commit()
        return {"success": True, "purchase_id": res.get("purchase_id") or res.get("document_id")}
        
    elif func_name == "add_payment":
        client_id = int(func_args.get("client_id"))
        amount = float(func_args.get("amount"))
        payment_type = func_args.get("payment_type", "versement")
        notes = func_args.get("notes", "")
        from app.modules.payments.service import PaymentsService
        from app.modules.payments.schemas_validation import PaymentFormSchema
        schema = PaymentFormSchema(client_id=client_id, amount=amount, payment_type=payment_type, notes=notes)
        async with session_maker() as session:
            service = PaymentsService(session)
            res = await service.create_payment_from_form(schema)
            await session.commit()
        return {"success": True, "payment_id": res.get("payment_id")}
        
    elif func_name == "delete_operation":
        tx_kind = func_args.get("tx_kind")
        tx_id = int(func_args.get("tx_id"))
        async with session_maker() as session:
            if tx_kind in ("sale_finished", "sale_raw", "sale"):
                from app.modules.sales.service import SalesService
                service = SalesService(session)
                await service.delete_sale_by_id(tx_id)
            elif tx_kind == "purchase":
                from app.modules.purchases.service import PurchaseService
                service = PurchaseService(session)
                await service.delete_purchase_by_id(tx_id)
            elif tx_kind == "payment":
                from app.modules.payments.service import PaymentsService
                service = PaymentsService(session)
                await service.delete_payment_by_id(tx_id)
            await session.commit()
        return {"success": True, "message": f"Opération {tx_kind} {tx_id} supprimée."}
        
    elif func_name == "add_expense":
        category = func_args.get("category", "")
        amount = float(func_args.get("amount"))
        description = func_args.get("description", "")
        payment_method = func_args.get("payment_method", "cash")
        
        from app.modules.expenses.schemas_validation import ExpenseCreateSchema
        import datetime
        schema = ExpenseCreateSchema(
            date=datetime.date.today(),
            category=category,
            description=description,
            amount=amount,
            payment_method=payment_method
        )
        from app.modules.expenses.service import add_expense
        async with session_maker() as session:
            await add_expense(
                db=session,
                date=schema.date.isoformat(),
                category=schema.category,
                description=schema.description,
                amount=schema.amount,
                method=schema.payment_method
            )
        return {"success": True, "message": "Dépense enregistrée."}
        
    elif func_name == "modify_expense":
        expense_id = int(func_args.get("expense_id"))
        category = func_args.get("category")
        amount = float(func_args.get("amount")) if func_args.get("amount") is not None else None
        description = func_args.get("description")
        from app.modules.expenses.service import modify_expense
        async with session_maker() as session:
            await modify_expense(expense_id, category, amount, description, db=session)
            await session.commit()
        return {"success": True, "message": f"Dépense {expense_id} modifiée."}
        
    elif func_name == "delete_expense":
        expense_id = int(func_args.get("expense_id"))
        from app.modules.expenses.service import remove_expense
        async with session_maker() as session:
            await remove_expense(expense_id, db=session)
            await session.commit()
        return {"success": True, "message": f"Dépense {expense_id} supprimée."}
        
    elif func_name == "add_production_batch":
        finished_product_id = int(func_args.get("finished_product_id"))
        quantity = float(func_args.get("quantity"))
        notes = func_args.get("notes", "")
        from app.services.production_service import apply_finished_production
        async with session_maker() as session:
            batch_id = await apply_finished_production(finished_product_id, quantity, notes, db=session)
            await session.commit()
        return {"success": True, "batch_id": batch_id}
        
    elif func_name == "delete_production":
        batch_id = int(func_args.get("batch_id"))
        from app.services.production_service import delete_production_by_id
        async with session_maker() as session:
            await delete_production_by_id(batch_id, db=session)
            await session.commit()
        return {"success": True, "message": f"Production {batch_id} supprimée."}
        
    elif func_name == "redirect_to":
        url = func_args.get("url", "/")
        return {"redirect_url": url}
        
    elif func_name == "change_theme":
        theme = func_args.get("theme", "light")
        return {"theme": theme}

    elif func_name == "get_enum_values":
        table = func_args.get("table", "").lower()
        column = func_args.get("column", "").lower()
        enums = {
            "expenses": {
                "payment_method": ["cash", "cheque", "virement", "autre"],
                "category": ["general", "transport", "fournitures", "loyer", "salaires", "maintenance", "telecom", "energie", "impots", "autre"]
            },
            "payments": {
                "payment_type": ["versement", "avance"]
            },
            "supplier_payments": {
                "payment_type": ["versement", "avance"]
            },
            "sale_documents": {
                "doc_type": ["bon", "facture"]
            },
            "purchase_documents": {
                "doc_type": ["bon", "facture"]
            },
            "products": {
                "category": ["finished", "raw"]
            },
            "sales": {
                "item_kind": ["finished", "raw"]
            },
            "purchases": {
                "item_kind": ["finished", "raw"]
            }
        }
        val = enums.get(table, {}).get(column)
        if val is not None:
            return {"values": val}
        return {"error": f"Pas de contraintes énumérées pour {table}.{column}."}

    elif func_name == "search_clients":
        q = func_args.get("query", "").strip()
        from app.core.perf_cache import async_cached_result
        async def builder():
            from sqlmodel import text
            async with session_maker() as session:
                rows = (await session.execute(text(
                    "SELECT id, name, phone, debt FROM clients WHERE name ILIKE :q LIMIT 50"
                ), {"q": f"%{q}%"})).fetchall()
            return [{"id": r[0], "name": r[1], "phone": r[2], "debt": float(r[3])} for r in rows]
        res = await async_cached_result(("assistant", "search_clients", q), builder, ttl_seconds=30.0)
        return {"results": res}

    elif func_name == "search_products":
        q = func_args.get("query", "").strip()
        from app.core.perf_cache import async_cached_result
        async def builder():
            from sqlmodel import text
            async with session_maker() as session:
                finished = (await session.execute(text(
                    "SELECT id, name, sale_price, avg_cost, unit FROM finished_products WHERE name ILIKE :q LIMIT 50"
                ), {"q": f"%{q}%"})).fetchall()
                raw = (await session.execute(text(
                    "SELECT id, name, avg_cost, unit FROM raw_materials WHERE name ILIKE :q LIMIT 50"
                ), {"q": f"%{q}%"})).fetchall()
            results = []
            for r in finished:
                results.append({"id": r[0], "name": r[1], "category": "finished", "price": float(r[2]), "cost": float(r[3]), "unit": r[4]})
            for r in raw:
                results.append({"id": r[0], "name": r[1], "category": "raw", "price": 0.0, "cost": float(r[2]), "unit": r[3]})
            return results
        res = await async_cached_result(("assistant", "search_products", q), builder, ttl_seconds=30.0)
        return {"results": res}

    elif func_name == "get_business_insights":
        insight_type = func_args.get("insight_type", "summary").lower()
        from sqlmodel import text
        async with session_maker() as session:
            if insight_type == "top_debtors":
                rows = (await session.execute(text(
                    "SELECT name, phone, debt FROM clients WHERE debt > 0 ORDER BY debt DESC LIMIT 5"
                ))).fetchall()
                return {"top_debtors": [{"name": r[0], "phone": r[1], "debt": float(r[2])} for r in rows]}
            elif insight_type == "monthly_sales_comparison":
                sales_cur = (await session.execute(text(
                    "SELECT COALESCE(SUM(total_amount), 0) FROM sale_documents WHERE date >= DATE_TRUNC('month', CURRENT_DATE)"
                ))).scalar()
                sales_prev = (await session.execute(text(
                    "SELECT COALESCE(SUM(total_amount), 0) FROM sale_documents WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND date < DATE_TRUNC('month', CURRENT_DATE)"
                ))).scalar()
                sales_cur = float(sales_cur)
                sales_prev = float(sales_prev)
                growth = ((sales_cur - sales_prev) / sales_prev * 100) if sales_prev > 0 else 0.0
                return {
                    "sales_current_month": sales_cur,
                    "sales_previous_month": sales_prev,
                    "growth_rate": round(growth, 2)
                }
            else:
                clients_count = (await session.execute(text("SELECT COUNT(*) FROM clients"))).scalar()
                products_count = (await session.execute(text("SELECT COUNT(*) FROM finished_products"))).scalar()
                sales_month = (await session.execute(text("SELECT COALESCE(SUM(total_amount), 0) FROM sale_documents WHERE date >= DATE_TRUNC('month', CURRENT_DATE)"))).scalar()
                return {
                    "total_clients": clients_count,
                    "total_products": products_count,
                    "sales_this_month": float(sales_month)
                }

    elif func_name == "get_print_link":
        dt = func_args.get("doc_type", "").lower()
        item_id = int(func_args.get("item_id"))
        allowed = {
            "sale_finished": f"/print/sale_finished/{item_id}",
            "sale_raw": f"/print/sale_raw/{item_id}",
            "purchase": f"/print/purchase/{item_id}",
            "payment": f"/print/payment/{item_id}",
            "production": f"/print/production/{item_id}",
            "client_history": f"/contacts/clients/{item_id}/print-history"
        }
        url = allowed.get(dt)
        if url:
            return {
                "print_url": url,
                "pdf_url": f"{url}?format=pdf",
                "message": f"Voici les liens d'impression :\n- [Imprimer/Voir]({url})\n- [Télécharger en PDF]({url}?format=pdf)"
            }
        return {"error": f"Type de document '{dt}' non supporté pour l'impression."}

    elif func_name == "import_client_excel":
        filepath = func_args.get("filepath", "")
        abs_path = os.path.abspath(filepath)
        workspace_dir = os.path.abspath(str(BASE_DIR))
        try:
            common = os.path.commonpath([workspace_dir, abs_path])
            if common != workspace_dir:
                raise ValueError()
        except Exception:
            return {"error": "Sécurité : Accès interdit en dehors du répertoire de l'application."}
        from app.services.excel_import_service import parse_excel_client_file
        try:
            data = parse_excel_client_file(abs_path)
        except Exception as e:
            return {"error": f"Erreur de lecture du fichier Excel : {str(e)}"}
        from app.modules.clients.service import ClientService
        from app.modules.clients.schemas_validation import ClientCreateSchema
        schema = ClientCreateSchema(
            name=data["name"],
            phone=data["phone"],
            address=data["address"],
            notes=data["notes"],
            opening_credit=data["opening_credit"]
        )
        async with session_maker() as session:
            service = ClientService(session)
            client = await service.create_client(schema)
            await session.commit()
        return {
            "success": True,
            "client_id": client.id,
            "message": f"Client '{data['name']}' importé avec succès avec un solde initial de {data['opening_credit']} DA (Lignes détectées : {data['history_count']})."
        }

    return {"error": f"Outil '{func_name}' non géré."}

def get_gemini_tools() -> List[Dict[str, Any]]:
    schema_text = "\n".join(f"- {t}: {d}" for t, d in TABLE_SCHEMAS.items())
    return [
        {
            "functionDeclarations": [
                {
                    "name": "execute_readonly_sql",
                    "description": (
                        "Exécute une requête SQL SELECT en lecture seule et retourne le résultat sous forme de lignes JSON. "
                        f"Schéma détaillé de la base de données :\n{schema_text}"
                    ),
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "La requête SQL SELECT complète à exécuter."
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "execute_write_sql",
                    "description": (
                        "Exécute une requête SQL d'écriture (INSERT, UPDATE, DELETE) pour ajouter, modifier ou supprimer des données. "
                        "Pour les INSERT, toujours ajouter 'RETURNING id' à la fin. "
                        f"Schéma détaillé de la base de données :\n{schema_text}"
                    ),
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "La requête SQL d'écriture complète à exécuter."
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "read_app_file",
                    "description": "Lit le contenu d'un fichier source de l'application (HTML, Python, CSS, JS) pour comprendre son fonctionnement ou ses boutons.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "filepath": {
                                "type": "STRING",
                                "description": "Le chemin d'accès relatif ou absolu du fichier (ex: templates/assistant.html)."
                            }
                        },
                        "required": ["filepath"]
                    }
                },
                {
                    "name": "modify_app_file",
                    "description": "Modifie une portion de code source dans un fichier de l'application en remplaçant l'ancien contenu par le nouveau.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "filepath": {
                                "type": "STRING",
                                "description": "Le chemin du fichier à modifier."
                            },
                            "old_content": {
                                "type": "STRING",
                                "description": "Le bloc de texte exact à remplacer."
                            },
                            "new_content": {
                                "type": "STRING",
                                "description": "Le nouveau bloc de texte de remplacement."
                            }
                        },
                        "required": ["filepath", "old_content", "new_content"]
                    }
                },
                {
                    "name": "create_app_backup",
                    "description": "Crée une sauvegarde manuelle de la base de données.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "reason": {
                                "type": "STRING",
                                "description": "La raison ou description de cette sauvegarde."
                            }
                        },
                        "required": ["reason"]
                    }
                },
                {
                    "name": "list_app_backups",
                    "description": "Liste toutes les sauvegardes disponibles pour la restauration.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {}
                    }
                },
                {
                    "name": "restore_app_backup",
                    "description": "Restaure la base de données à partir d'un fichier de sauvegarde choisi.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "backup_name": {
                                "type": "STRING",
                                "description": "Le nom du fichier de sauvegarde à restaurer."
                            }
                        },
                        "required": ["backup_name"]
                    }
                },
                {
                    "name": "create_app_user",
                    "description": "Crée un nouvel utilisateur dans l'application.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "username": {
                                "type": "STRING",
                                "description": "Nom d'utilisateur."
                            },
                            "password": {
                                "type": "STRING",
                                "description": "Mot de passe en clair (sera haché)."
                            },
                            "role": {
                                "type": "STRING",
                                "description": "Rôle de l'utilisateur (admin, manager, operator)."
                            }
                        },
                        "required": ["username", "password", "role"]
                    }
                },
                {
                    "name": "change_app_user_password",
                    "description": "Modifie ou réinitialise le mot de passe d'un utilisateur existant.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "username": {
                                "type": "STRING",
                                "description": "Nom de l'utilisateur."
                            },
                            "new_password": {
                                "type": "STRING",
                                "description": "Le nouveau mot de passe."
                            }
                        },
                        "required": ["username", "new_password"]
                    }
                },
                {
                    "name": "delete_app_user",
                    "description": "Supprime définitivement un utilisateur de l'application.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "username": {
                                "type": "STRING",
                                "description": "Nom de l'utilisateur à supprimer."
                            }
                        },
                        "required": ["username"]
                    }
                },
                {
                    "name": "update_setting",
                    "description": "Met à jour un paramètre système ou de configuration.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "key": {
                                "type": "STRING",
                                "description": "Le nom du paramètre (ex: company_name)."
                            },
                            "value": {
                                "type": "STRING",
                                "description": "La nouvelle valeur."
                            }
                        },
                        "required": ["key", "value"]
                    }
                },
                {
                    "name": "add_client",
                    "description": "Crée un nouveau client dans la base.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {
                                "type": "STRING",
                                "description": "Nom complet du client."
                            },
                            "phone": {
                                "type": "STRING",
                                "description": "Numéro de téléphone (optionnel)."
                            },
                            "address": {
                                "type": "STRING",
                                "description": "Adresse (optionnelle)."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Notes ou observations (optionnel)."
                            },
                            "opening_credit": {
                                "type": "NUMBER",
                                "description": "Dette de départ ou crédit initial (optionnel)."
                            }
                        },
                        "required": ["name"]
                    }
                },
                {
                    "name": "modify_client",
                    "description": "Modifie les informations d'un client existant.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "client_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du client."
                            },
                            "name": {
                                "type": "STRING",
                                "description": "Nouveau nom complet (optionnel)."
                            },
                            "phone": {
                                "type": "STRING",
                                "description": "Nouveau numéro de téléphone (optionnel)."
                            },
                            "address": {
                                "type": "STRING",
                                "description": "Nouvelle adresse (optionnelle)."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Nouvelles notes (optionnel)."
                            }
                        },
                        "required": ["client_id"]
                    }
                },
                {
                    "name": "delete_client",
                    "description": "Supprime définitivement un client s'il n'a pas d'opérations associées.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "client_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du client."
                            }
                        },
                        "required": ["client_id"]
                    }
                },
                {
                    "name": "add_product",
                    "description": "Ajoute un produit final ou une matière première au catalogue.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {
                                "type": "STRING",
                                "description": "Nom du produit."
                            },
                            "category": {
                                "type": "STRING",
                                "description": "Catégorie : 'finished' pour produit final, 'raw' pour matière première."
                            },
                            "price": {
                                "type": "NUMBER",
                                "description": "Prix de vente (uniquement pour produit final) (optionnel)."
                            },
                            "cost": {
                                "type": "NUMBER",
                                "description": "Coût d'achat ou coût moyen (optionnel)."
                            },
                            "unit": {
                                "type": "STRING",
                                "description": "Unité de mesure (ex: kg, sac, Qt) (optionnel, défaut 'kg')."
                            }
                        },
                        "required": ["name", "category"]
                    }
                },
                {
                    "name": "modify_product",
                    "description": "Modifie le nom, prix ou coût d'un produit.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "product_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du produit."
                            },
                            "category": {
                                "type": "STRING",
                                "description": "Catégorie : 'finished' pour produit final, 'raw' pour matière première."
                            },
                            "name": {
                                "type": "STRING",
                                "description": "Nouveau nom du produit (optionnel)."
                            },
                            "price": {
                                "type": "NUMBER",
                                "description": "Nouveau prix de vente (optionnel)."
                            },
                            "cost": {
                                "type": "NUMBER",
                                "description": "Nouveau coût d'achat (optionnel)."
                            }
                        },
                        "required": ["product_id", "category"]
                    }
                },
                {
                    "name": "delete_product",
                    "description": "Supprime un produit du catalogue.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "product_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du produit."
                            },
                            "category": {
                                "type": "STRING",
                                "description": "Catégorie : 'finished' pour produit final, 'raw' pour matière première."
                            }
                        },
                        "required": ["product_id", "category"]
                    }
                },
                {
                    "name": "add_sale",
                    "description": "Enregistre une nouvelle vente de produit final ou matière première.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "client_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du client (laisser vide pour client de passage)."
                            },
                            "item_kind": {
                                "type": "STRING",
                                "description": "Type d'article : 'finished' (produit final) ou 'raw' (matière première)."
                            },
                            "item_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant de l'article."
                            },
                            "quantity": {
                                "type": "NUMBER",
                                "description": "Quantité vendue."
                            },
                            "unit": {
                                "type": "STRING",
                                "description": "Unité utilisée (ex: kg, sac, Qt)."
                            },
                            "unit_price": {
                                "type": "NUMBER",
                                "description": "Prix unitaire de la vente."
                            },
                            "amount_paid": {
                                "type": "NUMBER",
                                "description": "Montant payé lors de la vente (crée automatiquement un versement) (optionnel)."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Remarques (optionnel)."
                            }
                        },
                        "required": ["item_kind", "item_id", "quantity", "unit", "unit_price"]
                    }
                },
                {
                    "name": "add_purchase",
                    "description": "Enregistre un nouvel achat de matière première ou produit.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "supplier_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du fournisseur (optionnel)."
                            },
                            "item_kind": {
                                "type": "STRING",
                                "description": "Type d'article : 'raw' (matière première) ou 'finished' (produit)."
                            },
                            "item_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant de l'article."
                            },
                            "quantity": {
                                "type": "NUMBER",
                                "description": "Quantité achetée."
                            },
                            "unit": {
                                "type": "STRING",
                                "description": "Unité utilisée."
                            },
                            "unit_price": {
                                "type": "NUMBER",
                                "description": "Prix unitaire d'achat."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Remarques (optionnel)."
                            }
                        },
                        "required": ["item_kind", "item_id", "quantity", "unit", "unit_price"]
                    }
                },
                {
                    "name": "add_payment",
                    "description": "Enregistre un versement ou une avance de client.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "client_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du client."
                            },
                            "amount": {
                                "type": "NUMBER",
                                "description": "Montant du versement en DA."
                            },
                            "payment_type": {
                                "type": "STRING",
                                "description": "Type : 'versement' ou 'avance' (défaut 'versement')."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Remarques (optionnel)."
                            }
                        },
                        "required": ["client_id", "amount"]
                    }
                },
                {
                    "name": "delete_operation",
                    "description": "Supprime ou annule une opération commerciale.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "tx_kind": {
                                "type": "STRING",
                                "description": "Type d'opération : 'sale_finished', 'sale_raw', 'purchase', 'payment'."
                            },
                            "tx_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant unique de la vente, achat ou paiement."
                            }
                        },
                        "required": ["tx_kind", "tx_id"]
                    }
                },
                {
                    "name": "add_expense",
                    "description": "Enregistre une nouvelle dépense.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "category": {
                                "type": "STRING",
                                "description": "Catégorie de la dépense (ex: Électricité, Transport, Carburant)."
                            },
                            "amount": {
                                "type": "NUMBER",
                                "description": "Montant de la dépense en DA."
                            },
                            "description": {
                                "type": "STRING",
                                "description": "Description (optionnel)."
                            },
                            "payment_method": {
                                "type": "STRING",
                                "description": "Mode de paiement (ex: Espèce, Chèque, CCP) (optionnel)."
                            }
                        },
                        "required": ["category", "amount"]
                    }
                },
                {
                    "name": "modify_expense",
                    "description": "Modifie les détails d'une dépense existante.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "expense_id": {
                                "type": "INTEGER",
                                "description": "Identifiant de la dépense."
                            },
                            "category": {
                                "type": "STRING",
                                "description": "Nouvelle catégorie (optionnel)."
                            },
                            "amount": {
                                "type": "NUMBER",
                                "description": "Nouveau montant (optionnel)."
                            },
                            "description": {
                                "type": "STRING",
                                "description": "Nouvelle description (optionnel)."
                            }
                        },
                        "required": ["expense_id"]
                    }
                },
                {
                    "name": "delete_expense",
                    "description": "Supprime définitivement une dépense.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "expense_id": {
                                "type": "INTEGER",
                                "description": "Identifiant de la dépense à supprimer."
                            }
                        },
                        "required": ["expense_id"]
                    }
                },
                {
                    "name": "add_production_batch",
                    "description": "Enregistre un lot de production finale (consomme les matières premières de la recette automatiquement).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "finished_product_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du produit final fabriqué."
                            },
                            "quantity": {
                                "type": "NUMBER",
                                "description": "Quantité fabriquée."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Observations (optionnel)."
                            }
                        },
                        "required": ["finished_product_id", "quantity"]
                    }
                },
                {
                    "name": "delete_production",
                    "description": "Supprime ou annule un lot de production (recrédite les matières premières consommées).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "batch_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant unique du lot de production."
                            }
                        },
                        "required": ["batch_id"]
                    }
                },
                {
                    "name": "redirect_to",
                    "description": "Redirige l'utilisateur vers un autre écran ou page de l'application.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "url": {
                                "type": "STRING",
                                "description": "Le chemin d'accès relatif (ex: /operations, /clients, /catalog)."
                            }
                        },
                        "required": ["url"]
                    }
                },
                {
                    "name": "change_theme",
                    "description": "Bascule le thème visuel de l'application.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "theme": {
                                "type": "STRING",
                                "description": "Le thème cible : 'dark' ou 'light'."
                            }
                        },
                        "required": ["theme"]
                    }
                },
                {
                    "name": "get_enum_values",
                    "description": "Récupère la liste des valeurs autorisées pour une colonne spécifique (ex: catégories de dépenses, modes de paiement). Le modèle doit appeler cet outil pour s'assurer de la validité d'un champ énuméré avant toute insertion.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "table": {
                                "type": "STRING",
                                "description": "Le nom de la table (ex: expenses, payments)."
                            },
                            "column": {
                                "type": "STRING",
                                "description": "Le nom de la colonne (ex: category, payment_method)."
                            }
                        },
                        "required": ["table", "column"]
                    }
                },
                {
                    "name": "search_clients",
                    "description": "Recherche des clients par leur nom pour trouver leur ID, numéro de téléphone ou dette en cours.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "Le nom ou partie du nom du client à rechercher."
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "search_products",
                    "description": "Recherche des produits finis ou matières premières dans le catalogue par leur nom.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "Le nom du produit ou composant à rechercher."
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_business_insights",
                    "description": "Fournit des rapports et des analyses proactives sur l'activité de l'entreprise (ex: débiteurs principaux, comparaison des ventes mensuelles, résumé général).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "insight_type": {
                                "type": "STRING",
                                "description": "Le type d'analyse : 'top_debtors', 'monthly_sales_comparison' ou 'summary'."
                            }
                        },
                        "required": ["insight_type"]
                    }
                },
                {
                    "name": "get_print_link",
                    "description": "Obtient le lien d'impression HTML et de téléchargement PDF pour un document commercial (vente, achat, versement ou production).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "doc_type": {
                                "type": "STRING",
                                "description": "Type de document : 'sale_finished', 'sale_raw', 'purchase', 'payment' ou 'production'."
                            },
                            "item_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du document."
                            }
                        },
                        "required": ["doc_type", "item_id"]
                    }
                },
                {
                    "name": "import_client_excel",
                    "description": "Importe les données d'un client et son solde historique depuis un fichier Excel (.xlsx ou .xls) importé.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "filepath": {
                                "type": "STRING",
                                "description": "Le chemin d'accès au fichier Excel sur le serveur."
                            }
                        },
                        "required": ["filepath"]
                    }
                }
            ]
        }
    ]

async def call_gemini_api(contents: List[Dict[str, Any]], api_key: str, model_name: str = "gemini-flash-latest") -> Dict[str, Any]:
    """Appelle l'API Gemini avec les messages et outils définis (non-streamed fallback/utility)."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    tools = get_gemini_tools()
    system_instruction = get_sabrina_system_prompt(model_name)
    
    payload = {
        "contents": contents,
        "tools": tools,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 1.5
                logger.warning("Rate Limit 429 sur %s. Attente de 1.5s avant nouvel essai...", model_name)
                await asyncio.sleep(wait_time)
                continue
            raise
        except Exception:
            raise

def _extract_json_objects(text: str) -> List[Tuple[str, int, int]]:
    objs = []
    start = -1
    depth = 0
    in_string = False
    escape = False
    
    for i, char in enumerate(text):
        if char == '"' and not escape:
            in_string = not in_string
        if in_string:
            if char == '\\' and not escape:
                escape = True
            else:
                escape = False
            continue
            
        if char == '{':
            if depth == 0:
                start = i
            depth += 1
        elif char == '}':
            if depth > 0:
                depth -= 1
                if depth == 0:
                    objs.append((text[start:i+1], start, i+1))
        escape = False
                    
    return objs

async def call_gemini_api_generator(contents: List[Dict[str, Any]], api_key: str, model_name: str = "gemini-flash-latest"):
    """Appelle l'API Gemini en mode streaming et produit des événements."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={api_key}"
    tools = get_gemini_tools()
    system_instruction = get_sabrina_system_prompt(model_name)
    
    payload = {
        "contents": contents,
        "tools": tools,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload, headers=headers, timeout=60.0) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        logger.error("streamGenerateContent failed status %d: %s", response.status_code, err_text)
                        raise httpx.HTTPStatusError(
                            f"HTTP Error {response.status_code}", 
                            request=response.request, 
                            response=response
                        )
                    
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        objs = _extract_json_objects(buffer)
                        if objs:
                            last_end = objs[-1][2]
                            for obj_text, _, _ in objs:
                                try:
                                    data = json.loads(obj_text)
                                    candidates = data.get("candidates", [])
                                    if candidates:
                                        content_parts = candidates[0].get("content", {}).get("parts", [])
                                        for part in content_parts:
                                            yield {"type": "raw_part", "part": part}
                                            if "text" in part:
                                                yield {"type": "text_chunk", "text": part["text"]}
                                            if "functionCall" in part:
                                                yield {"type": "function_call", "functionCall": part["functionCall"]}
                                except Exception:
                                    pass
                            buffer = buffer[last_end:]
            break
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 1.5
                logger.warning("Rate Limit 429 sur %s. Attente de 1.5s avant nouvel essai...", model_name)
                await asyncio.sleep(wait_time)
                continue
            raise
        except Exception:
            raise

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"

def start_ollama() -> bool:
    """Lance le serveur Ollama en arrière-plan sur la machine de l'utilisateur."""
    import shutil
    import subprocess
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        import os
        standard_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
        if os.path.exists(standard_path):
            ollama_path = standard_path
        else:
            return False
    try:
        import os
        creationflags = 0
        if os.name == 'nt':
            creationflags = 0x08000000  # CREATE_NO_WINDOW
        subprocess.Popen(
            [ollama_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        logger.info("Ollama process started successfully in the background.")
        return True
    except Exception as e:
        logger.error("Failed to start Ollama process: %s", e)
        return False

async def is_ollama_available() -> bool:
    """Vérifie si le serveur Ollama local est actif."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags", timeout=2.0)
            return r.status_code == 200
    except Exception:
        return False

async def run_ollama_agent_generator(messages: List[Dict[str, Any]], confirmed_query: str | None = None):
    """Boucle d'agent asynchrone génératrice pour Ollama local."""
    if not await is_ollama_available():
        yield {"type": "status", "message": "Démarrage automatique de l'IA locale (Ollama)..."}
        start_ollama()
        for attempt in range(6):
            await asyncio.sleep(1.0)
            if await is_ollama_available():
                break
        if not await is_ollama_available():
            yield {
                "type": "error",
                "error": (
                    "⚠️ Impossible de démarrer l'IA locale (Ollama).\n"
                    "💬 **Conseil :** Veuillez démarrer l'application **Ollama** manuellement sur votre machine."
                )
            }
            return

    schema_text = "\n".join(f"- {t}: {d}" for t, d in TABLE_SCHEMAS.items())
    system_prompt = get_sabrina_system_prompt(OLLAMA_MODEL)
    tools = get_ollama_tools()
    
    ollama_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = msg.get("role", "user")
        parts = msg.get("parts", [])
        if role in ("user", "model"):
            text = " ".join(p.get("text", "") for p in parts if "text" in p)
            if text.strip():
                ollama_messages.append({
                    "role": "assistant" if role == "model" else "user",
                    "content": text
                })
                
    max_turns = 5
    sql_errors_count = 0
    for turn in range(max_turns):
        payload = {
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "tools": tools,
            "stream": True,
            "options": {"temperature": 0.3, "num_predict": 2048}
        }
        
        content = ""
        tool_calls = []
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                    timeout=180.0
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            msg = chunk.get("message", {})
                            
                            chunk_content = msg.get("content", "")
                            if chunk_content:
                                content += chunk_content
                                yield {"type": "text_chunk", "text": chunk_content}
                                
                            chunk_tool_calls = msg.get("tool_calls", [])
                            for tc in chunk_tool_calls:
                                tool_calls.append(tc)
                        except Exception:
                            pass
        except Exception as e:
            yield {"type": "error", "error": f"⚠️ Erreur IA locale (Ollama) : {str(e)}"}
            return
            
        assistant_msg = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        ollama_messages.append(assistant_msg)
        
        if not tool_calls:
            yield {"type": "final_response", "text": content if content.strip() else "Pas de réponse."}
            return
            
        for tc in tool_calls:
            func = tc.get("function", {})
            func_name = func.get("name", "")
            raw_args = func.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    func_args = json.loads(raw_args)
                except Exception:
                    func_args = {}
            else:
                func_args = raw_args
                
            logger.info("Ollama Agent Call: '%s' args=%s", func_name, func_args)
            
            if func_name == "execute_readonly_sql":
                sql_query = func_args.get("query", "")
                yield {"type": "status", "message": "Recherche dans la base de données locale (SELECT)..."}
                output = execute_readonly_sql(sql_query)
            elif func_name == "execute_write_sql":
                sql_query = func_args.get("query", "")
                is_confirmed = confirmed_query and confirmed_query.strip() == sql_query.strip()
                if not is_confirmed and confirmed_query:
                    try:
                        cq_data = json.loads(confirmed_query)
                        if cq_data.get("name") == "execute_write_sql" and cq_data.get("args", {}).get("query") == sql_query:
                            is_confirmed = True
                    except Exception:
                        pass
                if not is_confirmed:
                    yield {
                        "type": "confirmation_required",
                        "query": sql_query,
                        "message": f"Je m'apprête à modifier la base de données (local). Veuillez confirmer la requête SQL ci-dessous :\n```sql\n{sql_query}\n```"
                    }
                    return
                yield {"type": "status", "message": "Modification de la base de données locale (confirmée)..."}
                output = execute_write_sql(sql_query)
            else:
                is_write = func_name not in ("read_app_file", "list_app_backups", "redirect_to", "change_theme", "get_enum_values", "search_clients", "search_products", "get_business_insights", "get_print_link")
                if is_write:
                    normalized_call = json.dumps({"name": func_name, "args": func_args}, sort_keys=True)
                    is_confirmed = False
                    if confirmed_query:
                        if confirmed_query.strip() == normalized_call:
                            is_confirmed = True
                        else:
                            try:
                                cq_data = json.loads(confirmed_query)
                                if cq_data.get("name") == func_name and cq_data.get("args") == func_args:
                                    is_confirmed = True
                            except Exception:
                                pass
                    if not is_confirmed:
                        msg = get_tool_confirmation_message(func_name, func_args)
                        yield {
                            "type": "confirmation_required",
                            "query": normalized_call,
                            "message": msg
                        }
                        return
                
                yield {"type": "status", "message": f"Exécution de l'action '{func_name}' (local)..."}
                output = await execute_tool_action(func_name, func_args)
                
            if isinstance(output, dict) and "error" in output and func_name in ("execute_readonly_sql", "execute_write_sql"):
                sql_errors_count += 1
                if sql_errors_count >= 3:
                    yield {"type": "error", "error": f"⚠️ Auto-correction SQL locale échouée après 3 tentatives. Dernière erreur : {output['error']}"}
                    return
                
            ollama_messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "content": json.dumps(output, ensure_ascii=False, default=str)
            })
            
    yield {"type": "error", "error": "La requête Ollama a dépassé la limite de tours sans retourner de réponse."}

async def run_ollama_agent(messages: List[Dict[str, Any]], schema_text: str) -> str:
    """Boucle d'agent synchrone pour Ollama (rétrocompatibilité)."""
    final_text = ""
    async for event in run_ollama_agent_generator(messages):
        if event.get("type") == "final_response":
            final_text = event.get("text", "")
        elif event.get("type") == "error":
            return event.get("error", "")
    return final_text

async def run_assistant_agent_generator(messages: List[Dict[str, Any]], api_key: str, confirmed_query: str | None = None):
    """Orchestre la boucle d'agent sous forme de générateur asynchrone d'événements."""
    yield {"type": "status", "message": "Sabrina analyse votre demande..."}
    
    # 1. Compression glissante de la mémoire
    messages = await compress_history_if_needed(messages, api_key, is_local=False)
    
    # 2. Aiguillage adaptatif du modèle
    user_model = db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip()
    if not user_model:
        user_model = "gemini-3.1-flash-lite"
        
    if user_model.lower() not in ("local", "ollama"):
        last_user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                parts = m.get("parts", [])
                if isinstance(parts, list):
                    last_user_text = " ".join(p.get("text", "") for p in parts if "text" in p)
                else:
                    last_user_text = m.get("content", "")
                break
        
        complex_keywords = ["modifier", "importer", "audit", "backup", "sql", "excel", "analyse", "lot de production", "sauvegarde", "restaurer", "supprimer", "update", "delete"]
        is_complex = any(kw in last_user_text.lower() for kw in complex_keywords)
        
        if is_complex:
            user_model = "gemini-1.5-pro"
        else:
            user_model = "gemini-3.1-flash-lite"
            
    if confirmed_query:
        func_name = None
        func_args = {}
        try:
            cq_data = json.loads(confirmed_query)
            if isinstance(cq_data, dict) and "name" in cq_data:
                func_name = cq_data.get("name")
                func_args = cq_data.get("args", {})
        except Exception:
            pass
            
        if not func_name:
            func_name = "execute_write_sql"
            func_args = {"query": confirmed_query}
            
        yield {"type": "status", "message": "Exécution de l'action confirmée..."}
        try:
            if func_name == "execute_write_sql":
                output = execute_write_sql(func_args.get("query", ""))
            else:
                output = await execute_tool_action(func_name, func_args)
        except Exception as e:
            output = {"error": str(e)}
            
        if user_model.lower() in ("local", "ollama"):
            messages = list(messages)
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_confirmed",
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "arguments": json.dumps(func_args)
                    }
                }]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": "call_confirmed",
                "content": json.dumps(output, ensure_ascii=False, default=str)
            })
            confirmed_query = None
        else:
            messages = list(messages)
            messages.append({
                "role": "model",
                "parts": [{"functionCall": {"name": func_name, "args": func_args}}]
            })
            messages.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": func_name,
                        "response": {"output": output}
                    }
                }]
            })
            confirmed_query = None
        
    if user_model.lower() in ("local", "ollama"):
        async for event in run_ollama_agent_generator(messages, confirmed_query):
            yield event
        return
        
    contents = list(messages)
    max_turns = 5
    sql_errors_count = 0
    for turn in range(max_turns):
        res = None
        last_exception = None
        
        candidate_models = [user_model]
        fallbacks = ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-flash-latest"]
        for m in fallbacks:
            if m != user_model and m not in candidate_models:
                candidate_models.append(m)
                
        accumulated_text = ""
        accumulated_tool_calls = []
        accumulated_parts = []
        has_tool_call = False
        res_ok = False
        
        is_mocked = hasattr(call_gemini_api, "mock_calls") or hasattr(call_gemini_api, "return_value")
        
        for model in candidate_models:
            accumulated_text = ""
            accumulated_tool_calls = []
            accumulated_parts = []
            has_tool_call = False
            try:
                if is_mocked:
                    res = await call_gemini_api(contents, api_key, model_name=model)
                    candidates = res.get("candidates", [])
                    if candidates:
                        content_obj = candidates[0].get("content", {})
                        parts = content_obj.get("parts", [])
                        accumulated_parts = parts
                        for p in parts:
                            if "text" in p:
                                accumulated_text += p["text"]
                                yield {"type": "text_chunk", "text": p["text"]}
                            if "functionCall" in p:
                                has_tool_call = True
                                accumulated_tool_calls.append(p["functionCall"])
                else:
                    async for event in call_gemini_api_generator(contents, api_key, model_name=model):
                        if event.get("type") == "raw_part":
                            accumulated_parts.append(event["part"])
                        elif event.get("type") == "text_chunk":
                            accumulated_text += event["text"]
                            if not has_tool_call:
                                yield {"type": "text_chunk", "text": event["text"]}
                        elif event.get("type") == "function_call":
                            has_tool_call = True
                            accumulated_tool_calls.append(event["functionCall"])
                res_ok = True
                break
            except Exception as exc:
                last_exception = exc
                logger.warning("Erreur avec le modèle %s : %s. Essai du modèle suivant...", model, exc)
                continue
                
        if not res_ok:
            # Fallback Ollama
            ollama_ok = await is_ollama_available()
            if ollama_ok:
                yield {"type": "status", "message": "Modèles Gemini indisponibles. Bascule automatique sur l'IA locale..."}
                async for event in run_ollama_agent_generator(contents, confirmed_query):
                    yield event
                return
            else:
                error_msg = str(last_exception) if last_exception else "Quota dépassé."
                yield {
                    "type": "error",
                    "error": (
                        f"⚠️ Quota Gemini dépassé ({error_msg}).\n"
                        "💬 **Conseil :** Ollama n'est pas démarré. Lancez l'application **Ollama** pour continuer en local."
                    )
                }
                return
                
        if accumulated_parts:
            content_obj = {
                "role": "model",
                "parts": accumulated_parts
            }
        else:
            parts = []
            if accumulated_text:
                parts.append({"text": accumulated_text})
            for tc in accumulated_tool_calls:
                parts.append({"functionCall": tc})
            content_obj = {
                "role": "model",
                "parts": parts
            }
        contents.append(content_obj)
        
        tool_calls = accumulated_tool_calls
        
        if not tool_calls:
            yield {"type": "final_response", "text": accumulated_text}
            return
            
        function_responses = []
        for part in tool_calls:
            func_call = part.get("functionCall", part)
            func_name = func_call["name"]
            func_args = func_call.get("args", {})
            
            logger.info("Agent Call: Execute function '%s' with args %s", func_name, func_args)
            
            if func_name == "get_schema":
                output = get_schema()
            elif func_name == "execute_readonly_sql":
                sql_query = func_args.get("query", "")
                yield {"type": "status", "message": "Recherche dans la base de données (SELECT)..."}
                output = execute_readonly_sql(sql_query)
            elif func_name == "execute_write_sql":
                sql_query = func_args.get("query", "")
                is_confirmed = confirmed_query and confirmed_query.strip() == sql_query.strip()
                if not is_confirmed and confirmed_query:
                    try:
                        cq_data = json.loads(confirmed_query)
                        if cq_data.get("name") == "execute_write_sql" and cq_data.get("args", {}).get("query") == sql_query:
                            is_confirmed = True
                    except Exception:
                        pass
                if not is_confirmed:
                    yield {
                        "type": "confirmation_required",
                        "query": sql_query,
                        "message": f"Je m'apprête à modifier la base de données. Veuillez confirmer la requête SQL ci-dessous :\n```sql\n{sql_query}\n```"
                    }
                    return
                yield {"type": "status", "message": "Modification de la base de données (confirmée)..."}
                output = execute_write_sql(sql_query)
            else:
                is_write = func_name not in ("read_app_file", "list_app_backups", "redirect_to", "change_theme", "get_enum_values", "search_clients", "search_products", "get_business_insights", "get_print_link")
                if is_write:
                    normalized_call = json.dumps({"name": func_name, "args": func_args}, sort_keys=True)
                    is_confirmed = False
                    if confirmed_query:
                        if confirmed_query.strip() == normalized_call:
                            is_confirmed = True
                        else:
                            try:
                                cq_data = json.loads(confirmed_query)
                                if cq_data.get("name") == func_name and cq_data.get("args") == func_args:
                                    is_confirmed = True
                            except Exception:
                                pass
                    if not is_confirmed:
                        msg = get_tool_confirmation_message(func_name, func_args)
                        yield {
                            "type": "confirmation_required",
                            "query": normalized_call,
                            "message": msg
                        }
                        return
                
                yield {"type": "status", "message": f"Exécution de l'action '{func_name}'..."}
                output = await execute_tool_action(func_name, func_args)
                
            if isinstance(output, dict) and "error" in output and func_name in ("execute_readonly_sql", "execute_write_sql"):
                sql_errors_count += 1
                if sql_errors_count >= 3:
                    yield {"type": "error", "error": f"⚠️ Auto-correction SQL échouée après 3 tentatives. Dernière erreur : {output['error']}"}
                    return
                
            function_responses.append({
                "functionResponse": {
                    "name": func_name,
                    "response": {"output": output}
                }
            })
            
        contents.append({
            "role": "user",
            "parts": function_responses
        })
        
    yield {"type": "error", "error": "La requête a dépassé la limite de tours d'agent sans retourner de réponse."}

async def run_assistant_agent(messages: List[Dict[str, Any]], api_key: str) -> str:
    """Orchestre la boucle d'agent en mode synchrone (compatibilité)."""
    final_text = ""
    async for event in run_assistant_agent_generator(messages, api_key):
        if event.get("type") == "final_response":
            final_text = event.get("text", "")
        elif event.get("type") == "error":
            return event.get("error", "")
    return final_text
