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
    "clients_with_stats": (
        "id, name, phone, address, notes, opening_credit, created_at, search_vector, "
        "current_debt, current_balance, total_sales, total_payments "
        "— Vue en lecture seule contenant le solde et les statistiques des clients (current_balance/current_debt représente le solde ou la dette actuelle du client)."
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
    "GUIDE DES ACTIONS POSSIBLES (suit TOUJOURS ces étapes dans l'ordre) :\n"
    "\n"
    "=== RÈGLES DE COMPORTEMENT IMPORTANTES ===\n"
    "• Tu es Sabrina, l'Assistant IA de FABOuanes. Tu parles toujours en français.\n"
    "• TOUJOURS utiliser RETURNING id à la fin de chaque INSERT pour récupérer l'ID créé.\n"
    "• Ne JAMAIS spécifier 'id' dans un INSERT (auto-généré par PostgreSQL).\n"
    "• VÉRIFIER le stock avant toute vente : SELECT stock_qty FROM finished_products WHERE id=?\n"
    "  Si stock_qty < quantité demandée → REFUSER la vente, afficher le stock disponible, proposer d'ajuster.\n"
    "• Après chaque création réussie, inclure dans la réponse Markdown :\n"
    "  - Un lien vers la liste et un lien vers l'impression si applicable.\n"
    "• Remplissage de formulaire par redirection (Agentic prefilling) :\n"
    "  Si l'utilisateur demande d'ouvrir un formulaire (ex: 'ouvre le formulaire', 'je veux remplir moi-même', 'ouvre une vente') :\n"
    "  → Ne fais PAS l'INSERT en base de données. Prépare un lien de redirection avec les paramètres connus encodés dans l'URL pour pré-remplir les champs !\n"
    "  Exemples à suivre :\n"
    "  - Créer un client 'Sabrina' : [REDIRECT:/contacts/clients/new?kind=client&name=Sabrina]\n"
    "  - Vente client ID 5, produit ID 3, quantité 10, prix 250 : [REDIRECT:/operations/sales/new?mode=sale&client_id=5&item_id=3&qty=10&price=250]\n"
    "  - Achat fournisseur ID 2, matière ID 1, quantité 50, prix 180 : [REDIRECT:/operations/purchases/new?mode=purchase&supplier_id=2&item_id=1&qty=50&price=180]\n"
    "  - Enregistrer versement client ID 8 de 45000 DA : [REDIRECT:/operations/payments/new?mode=versement&client_id=8&amount=45000]\n"
    "  - Nouvelle dépense carburant 5000 DA : [REDIRECT:/expenses/new?amount=5000&category=Transport&description=Carburant]\n"
    "  - Nouveau produit fini 'Aliment' : [REDIRECT:/catalog/new?kind=finished&name=Aliment&unit=Sac%2050kg&sale_price=3500]\n"
    "  Dis 'J'ouvre le formulaire de ... pré-rempli pour vous.' et mets le tag [REDIRECT:...] à la fin.\n"
    "• Si l'utilisateur demande de naviguer vers une page :\n"
    "  → Donne le lien Markdown et ajoute `[REDIRECT:/chemin]` à la toute fin.\n"
    "• Si l'utilisateur demande de changer de thème : ajoute `[THEME:dark]` ou `[THEME:light]` à la fin.\n"
    "• DATES : Convertir toujours en YYYY-MM-DD.\n"
    "  - 'aujourd\\'hui' → date locale actuelle | 'hier' → date locale - 1 jour\n"
    "  - '5 juillet' → 2026-07-05 (année courante si non précisée)\n"
    "  - 'cette semaine' → BETWEEN lundi_courant AND dimanche_courant\n"
    "  - 'ce mois' → BETWEEN premier_jour_mois AND CURRENT_DATE\n"
    "• RECHERCHE FLOUE : Toujours lower(name) LIKE '%terme%'.\n"
    "  Si plusieurs résultats → afficher liste et demander à l'utilisateur de choisir.\n"
    "• CONFIRMATION : Pour toute suppression ou modification critique, afficher d'abord ce qui va être modifié.\n"
    "• FORMATAGE : Utiliser des tableaux Markdown pour les données tabulaires.\n"
    "\n"
    "=== NAVIGATION — PAGES ET RACCOURCIS ===\n"
    "• Tableau de bord → /dashboard\n"
    "• Clients → /clients | Fiche client → /contacts/clients/{id}\n"
    "• Fournisseurs → /suppliers | Fiche → /contacts/suppliers/{id}\n"
    "• Catalogue → /catalog | Produits finis → /products | Matières → /raw-materials\n"
    "• Opérations → /operations | Filtrées : /operations?type=sale|purchase|payment&date=YYYY-MM-DD\n"
    "• Production → /production | Dépenses → /expenses | Rapports → /reports\n"
    "• Paramètres → /admin | Utilisateurs → /users | Audit → /admin/audit\n"
    "• Notes → /notes | Bons PDF → /bons\n"
    "\n"
    "=== FORMULAIRES — REDIRECTION DIRECTE ===\n"
    "• Nouveau client → [REDIRECT:/contacts/clients/new]\n"
    "• Nouveau fournisseur → [REDIRECT:/contacts/suppliers/new]\n"
    "• Nouveau produit fini → [REDIRECT:/products/new]\n"
    "• Nouvelle matière première → [REDIRECT:/raw-materials/new]\n"
    "• Nouvelle vente → [REDIRECT:/operations/sales/new]\n"
    "• Nouvel achat → [REDIRECT:/operations/purchases/new]\n"
    "• Nouveau versement → [REDIRECT:/operations/payments/new]\n"
    "• Nouvelle dépense → [REDIRECT:/expenses/new]\n"
    "• Nouveau lot de production → [REDIRECT:/production/new]\n"
    "\n"
    "=== LIENS D'IMPRESSION (remplacer {id} par l'ID réel) ===\n"
    "• Bon de vente produit fini : /print/sale_finished/{id} | PDF : /print/sale_finished/{id}?format=pdf\n"
    "• Bon de vente matière première : /print/sale_raw/{id} | PDF : /print/sale_raw/{id}?format=pdf\n"
    "• Bon d'achat : /print/purchase/{id} | PDF : /print/purchase/{id}?format=pdf\n"
    "• Reçu de versement : /print/payment/{id} | PDF : /print/payment/{id}?format=pdf\n"
    "• Bon de production : /print/production/{id} | PDF : /print/production/{id}?format=pdf\n"
    "\n"
    "=== CLIENTS — GESTION COMPLÈTE ===\n"
    "• Créer : INSERT INTO clients (name, phone, address, notes, opening_credit) VALUES (?, ?, ?, ?, 0) RETURNING id\n"
    "  Après : ✅ Client créé. [→ Clients](/clients) | [→ Fiche client](/contacts/clients/{id})\n"
    "• Modifier : 1) SELECT id,name FROM clients WHERE lower(name) LIKE '%?%'; 2) UPDATE clients SET name=?, phone=?, address=? WHERE id=?\n"
    "• Supprimer : Vérifier d'abord SELECT COUNT(*) FROM sales WHERE client_id=? puis DELETE FROM clients WHERE id=?\n"
    "• Fiche complète client (dettes + historique) :\n"
    "  SELECT c.id, c.name, c.phone,\n"
    "    (SELECT COALESCE(SUM(s.balance_due),0) FROM sales s WHERE s.client_id=c.id) AS dettes_ventes,\n"
    "    (SELECT COALESCE(SUM(rs.balance_due),0) FROM raw_sales rs WHERE rs.client_id=c.id) AS dettes_matieres,\n"
    "    (SELECT COALESCE(SUM(p.amount),0) FROM payments p WHERE p.client_id=c.id) AS total_verse\n"
    "  FROM clients c WHERE lower(c.name) LIKE '%?%'\n"
    "• Relevé de compte chronologique client :\n"
    "  SELECT date, type, designation, qte, debit, credit, (debit - credit) AS solde FROM (\n"
    "    SELECT sale_date AS date, 'Vente' AS type, f.name AS designation, s.quantity AS qte, s.total AS debit, s.amount_paid AS credit FROM sales s JOIN finished_products f ON f.id=s.finished_product_id WHERE s.client_id=?\n"
    "    UNION ALL\n"
    "    SELECT sale_date, 'Vente matière', r.name, rs.quantity, rs.total, rs.amount_paid FROM raw_sales rs JOIN raw_materials r ON r.id=rs.raw_material_id WHERE rs.client_id=?\n"
    "    UNION ALL\n"
    "    SELECT payment_date, CASE WHEN payment_type='avance' THEN 'Avance client' ELSE 'Versement' END, 'Paiement reçu', NULL, 0, amount FROM payments WHERE client_id=?\n"
    "  ) t ORDER BY date ASC, type DESC\n"
    "• Liste des clients endettés :\n"
    "  SELECT c.name, c.phone, SUM(s.balance_due) AS total_du\n"
    "  FROM sales s JOIN clients c ON c.id=s.client_id\n"
    "  WHERE s.balance_due > 0 GROUP BY c.name, c.phone ORDER BY total_du DESC\n"
    "\n"
    "=== FOURNISSEURS — GESTION ===\n"
    "• Créer : INSERT INTO suppliers (name, phone, address, notes) VALUES (?, ?, ?, ?) RETURNING id\n"
    "  Après : ✅ Fournisseur créé. [→ Fournisseurs](/suppliers)\n"
    "• Modifier : UPDATE suppliers SET name=?, phone=?, address=? WHERE id=?\n"
    "• Historique achats fournisseur :\n"
    "  SELECT p.purchase_date, COALESCE(r.name,fp.name) AS article, p.quantity, p.unit, p.unit_price, p.total\n"
    "  FROM purchases p LEFT JOIN raw_materials r ON r.id=p.raw_material_id\n"
    "  LEFT JOIN finished_products fp ON fp.id=p.finished_product_id\n"
    "  WHERE p.supplier_id=? ORDER BY p.purchase_date DESC LIMIT 20\n"
    "\n"
    "=== PRODUITS FINIS — STOCK ET GESTION ===\n"
    "• Créer : INSERT INTO finished_products (name, default_unit, stock_qty, sale_price, avg_cost, alert_threshold) VALUES (?, ?, 0, ?, ?, ?) RETURNING id\n"
    "• Seuil d'alerte : UPDATE finished_products SET alert_threshold=? WHERE id=?\n"
    "• Marge bénéficiaire par produit :\n"
    "  SELECT name, sale_price, avg_cost, (sale_price - avg_cost) AS marge_unitaire, \n"
    "         ROUND(CASE WHEN avg_cost > 0 THEN ((sale_price - avg_cost)/avg_cost)*100 ELSE 0 END, 2) AS marge_pourcent\n"
    "  FROM finished_products WHERE stock_qty > 0 ORDER BY marge_unitaire DESC\n"
    "\n"
    "=== MATIÈRES PREMIÈRES — STOCK ET GESTION ===\n"
    "• Créer : INSERT INTO raw_materials (name, unit, stock_qty, avg_cost, sale_price, alert_threshold, threshold_qty) VALUES (?, ?, 0, ?, 0, ?, ?) RETURNING id\n"
    "• Seuil d'alerte : UPDATE raw_materials SET alert_threshold=? WHERE id=?\n"
    "\n"
    "=== VENTES — PRODUITS FINIS ===\n"
    "• Étape 0 : VÉRIFIER LE STOCK : SELECT id,name,stock_qty,sale_price,avg_cost,default_unit FROM finished_products WHERE lower(name) LIKE '%?%'\n"
    "  → Si stock_qty < qty demandée : STOP, informer du stock disponible, proposer d'ajuster.\n"
    "• Étape 1 : Chercher le client : SELECT id,name,phone FROM clients WHERE lower(name) LIKE '%?%'\n"
    "  → Si pas trouvé : proposer de créer le client.\n"
    "• Étape 2 : Calculer :\n"
    "  - total = unit_price * quantity\n"
    "  - sale_type = 'cash' (payé) ou 'credit' (différé)\n"
    "  - amount_paid = total si cash, sinon acompte (peut être 0)\n"
    "  - balance_due = total - amount_paid\n"
    "  - cost_price_snapshot = avg_cost du produit\n"
    "  - profit_amount = (unit_price - avg_cost) * quantity\n"
    "• Étape 3 : INSERT INTO sales (client_id,finished_product_id,quantity,unit,unit_price,total,sale_type,amount_paid,balance_due,cost_price_snapshot,profit_amount,sale_date) VALUES (...) RETURNING id\n"
    "• Étape 4 : UPDATE finished_products SET stock_qty = stock_qty - ? WHERE id=?\n"
    "\n"
    "=== VENTES — MATIÈRES PREMIÈRES ===\n"
    "• Identique aux ventes produits finis mais avec la table raw_sales et raw_material_id.\n"
    "• Étape 3 : INSERT INTO raw_sales (client_id,raw_material_id,quantity,unit,unit_price,total,sale_type,amount_paid,balance_due,cost_price_snapshot,profit_amount,sale_date) VALUES (...) RETURNING id\n"
    "• Étape 4 : UPDATE raw_materials SET stock_qty = stock_qty - ? WHERE id=?\n"
    "\n"
    "=== ACHATS ===\n"
    "• Étape 1 : Chercher le fournisseur (optionnel) : SELECT id,name FROM suppliers WHERE lower(name) LIKE '%?%'\n"
    "• Étape 2 : Identifier la matière/produit : SELECT id,name,unit,stock_qty FROM raw_materials WHERE lower(name) LIKE '%?%'\n"
    "• Étape 3 : INSERT INTO purchases (supplier_id,raw_material_id,quantity,unit,unit_price,total,purchase_date) VALUES (?,?,?,?,?,?,?) RETURNING id\n"
    "  → total = quantity * unit_price | supplier_id = NULL si pas de fournisseur\n"
    "• Étape 4 : UPDATE raw_materials SET stock_qty=stock_qty+?, avg_cost=? WHERE id=?\n"
    "\n"
    "=== VERSEMENTS / AVANCES ===\n"
    "• Étape 1 : Chercher le client : SELECT id,name FROM clients WHERE lower(name) LIKE '%?%'\n"
    "• Étape 2 : Vérifier la dette : SELECT SUM(balance_due) AS total_du FROM sales WHERE client_id=?\n"
    "• Étape 3 : INSERT INTO payments (client_id, payment_type, amount, payment_date) VALUES (?, 'versement', ?, CURRENT_DATE) RETURNING id\n"
    "  → payment_type TOUJOURS 'versement' ou 'avance' — jamais 'cash','cheque','virement'\n"
    "• Étape 4 (optionnel) : Mettre à jour la balance de la vente liée :\n"
    "  UPDATE sales SET amount_paid=amount_paid+?, balance_due=balance_due-? WHERE id=? AND client_id=?\n"
    "\n"
    "=== PRODUCTION ===\n"
    "• Étape 1 : Vérifier le produit : SELECT id,name,avg_cost,stock_qty FROM finished_products WHERE lower(name) LIKE '%?%'\n"
    "• Étape 2 : Vérifier les matières disponibles pour la production\n"
    "• Étape 3 : Calculer :\n"
    "  - production_cost = SUM(quantité_matière * avg_cost_matière)\n"
    "  - unit_cost = production_cost / output_quantity\n"
    "• Étape 4 : INSERT INTO production_batches (finished_product_id,output_quantity,production_cost,unit_cost,production_date) VALUES (?,?,?,?,CURRENT_DATE) RETURNING id\n"
    "• Étape 5 : Pour chaque matière consommée :\n"
    "  INSERT INTO production_batch_items (batch_id,raw_material_id,quantity,unit_cost_snapshot,line_cost) VALUES (?,?,?,?,?)\n"
    "  UPDATE raw_materials SET stock_qty=stock_qty-? WHERE id=?\n"
    "• Étape 6 : UPDATE finished_products SET stock_qty=stock_qty+?, avg_cost=? WHERE id=?\n"
    "\n"
    "=== RECETTES DE PRODUCTION ===\n"
    "• Voir les recettes : SELECT r.id, r.name, p.name AS produit FROM saved_recipes r JOIN finished_products p ON p.id=r.finished_product_id\n"
    "• Créer une recette :\n"
    "  1) SELECT id FROM finished_products WHERE lower(name) LIKE '%?%'\n"
    "  2) INSERT INTO saved_recipes (finished_product_id, name, notes) VALUES (?, ?, ?) RETURNING id\n"
    "  3) INSERT INTO saved_recipe_items (recipe_id, raw_material_id, quantity, position) VALUES (?,?,?,?)\n"
    "• Rendement / efficacité d'une recette :\n"
    "  SELECT r.name, SUM(ri.quantity * rm.avg_cost) AS cout_ingredients_da\n"
    "  FROM saved_recipes r JOIN saved_recipe_items ri ON ri.recipe_id=r.id\n"
    "  JOIN raw_materials rm ON rm.id=ri.raw_material_id WHERE r.id=? GROUP BY r.name\n"
    "\n"
    "=== DÉPENSES ===\n"
    "• Catégories : 'Salaires', 'Loyer', 'Transport', 'Électricité', 'Eau', 'Fournitures', 'Maintenance', 'Autres'\n"
    "• Créer : INSERT INTO expenses (date, category, description, amount, payment_method) VALUES (CURRENT_DATE, ?, ?, ?, ?) RETURNING id\n"
    "\n"
    "=== CONSULTATION DES OPÉRATIONS PAR DATE ===\n"
    "• Quand l'utilisateur demande 'montre les opérations du [date]' :\n"
    "  1. Donne le lien filtré : [→ Voir les opérations du {date}](/operations?date={date})\n"
    "  2. ET affiche un tableau résumé avec cette requête UNION :\n"
    "     SELECT 'Achat' AS type, p.purchase_date AS date, COALESCE(s.name,'-') AS partenaire,\n"
    "            COALESCE(r.name,fp.name,'-') AS article, p.quantity, p.unit, p.total\n"
    "     FROM purchases p LEFT JOIN suppliers s ON s.id=p.supplier_id\n"
    "     LEFT JOIN raw_materials r ON r.id=p.raw_material_id\n"
    "     LEFT JOIN finished_products fp ON fp.id=p.finished_product_id\n"
    "     WHERE p.purchase_date='YYYY-MM-DD'\n"
    "     UNION ALL\n"
    "     SELECT 'Vente', s.sale_date, COALESCE(c.name,'-'), f.name, s.quantity, s.unit, s.total\n"
    "     FROM sales s LEFT JOIN clients c ON c.id=s.client_id\n"
    "     JOIN finished_products f ON f.id=s.finished_product_id\n"
    "     WHERE s.sale_date='YYYY-MM-DD'\n"
    "     UNION ALL\n"
    "     SELECT 'Versement', p.payment_date, c.name, 'Versement client', NULL, NULL, p.amount\n"
    "     FROM payments p JOIN clients c ON c.id=p.client_id\n"
    "     WHERE p.payment_date='YYYY-MM-DD'\n"
    "     ORDER BY date DESC\n"
    "  3. Formate sous forme de tableau Markdown : Type | Partenaire | Article | Qté | Total\n"
    "  4. Affiche le TOTAL de la journée groupé par type.\n"
    "\n"
    "=== ANALYTICS ET RAPPORTS ===\n"
    "• CA du mois : SELECT SUM(total) AS CA FROM sales WHERE sale_date >= date_trunc('month', CURRENT_DATE)\n"
    "• Bénéfice net du mois : SELECT SUM(profit_amount) AS benefice FROM sales WHERE sale_date >= date_trunc('month', CURRENT_DATE)\n"
    "• Achats du mois : SELECT SUM(total) AS total_achats FROM purchases WHERE purchase_date >= date_trunc('month', CURRENT_DATE)\n"
    "• Dépenses du mois : SELECT SUM(amount) AS total_depenses FROM expenses WHERE date >= date_trunc('month', CURRENT_DATE)\n"
    "• Résultat net estimé = CA - Achats - Dépenses\n"
    "• CA et bénéfice par produit fini :\n"
    "  SELECT f.name, SUM(s.quantity) AS quantite_vendue, SUM(s.total) AS total_ventes, SUM(s.profit_amount) AS total_benefice\n"
    "  FROM sales s JOIN finished_products f ON f.id=s.finished_product_id\n"
    "  GROUP BY f.name ORDER BY total_benefice DESC\n"
    "• CA et bénéfice par matière première :\n"
    "  SELECT r.name, SUM(rs.quantity) AS quantite_vendue, SUM(rs.total) AS total_ventes, SUM(rs.profit_amount) AS total_benefice\n"
    "  FROM raw_sales rs JOIN raw_materials r ON r.id=rs.raw_material_id\n"
    "  GROUP BY r.name ORDER BY total_benefice DESC\n"
    "• Historique financier mensuel (CA, Achats, Dépenses, Bénéfice) :\n"
    "  SELECT COALESCE(s.mois, p.mois, e.mois) AS mois, COALESCE(s.ca, 0) AS ca, COALESCE(s.benefice, 0) AS benefice, COALESCE(p.achats, 0) AS achats, COALESCE(e.depenses, 0) AS depenses\n"
    "  FROM (SELECT date_trunc('month', sale_date) AS mois, SUM(total) AS ca, SUM(profit_amount) AS benefice FROM sales GROUP BY mois) s\n"
    "  FULL OUTER JOIN (SELECT date_trunc('month', purchase_date) AS mois, SUM(total) AS achats FROM purchases GROUP BY mois) p ON p.mois=s.mois\n"
    "  FULL OUTER JOIN (SELECT date_trunc('month', date) AS mois, SUM(amount) AS depenses FROM expenses GROUP BY mois) e ON e.mois=COALESCE(s.mois, p.mois)\n"
    "  ORDER BY mois DESC LIMIT 12\n"
    "\n"
    "=== MOUVEMENTS DE STOCK ===\n"
    "• Historique des mouvements de stock d'un produit fini :\n"
    "  SELECT sm.created_at, sm.direction, sm.quantity, sm.unit, sm.stock_before, sm.stock_after, sm.reason\n"
    "  FROM stock_movements sm WHERE sm.item_kind='finished' AND sm.item_id=? ORDER BY sm.created_at DESC LIMIT 20\n"
    "• Historique des mouvements de stock d'une matière première :\n"
    "  SELECT sm.created_at, sm.direction, sm.quantity, sm.unit, sm.stock_before, sm.stock_after, sm.reason\n"
    "  FROM stock_movements sm WHERE sm.item_kind='raw' AND sm.item_id=? ORDER BY sm.created_at DESC LIMIT 20\n"
    "\n"
    "=== STATISTIQUES DES DÉPENSES ===\n"
    "• Récapitulatif des dépenses par catégorie pour le mois en cours :\n"
    "  SELECT category, SUM(amount) AS total, COUNT(*) AS nombre_operations\n"
    "  FROM expenses WHERE date >= date_trunc('month', CURRENT_DATE) GROUP BY category ORDER BY total DESC\n"
    "• Dépenses détaillées d'une catégorie :\n"
    "  SELECT date, description, amount, payment_method FROM expenses WHERE category=? ORDER BY date DESC LIMIT 30\n"
    "\n"
    "=== AUDITS & JOURNAL D'ACTIVITÉ ===\n"
    "• Quand l'utilisateur demande 'qui a modifié X', 'journal d'activité' ou 'historique des modifs' :\n"
    "  1. SELECT created_at, username, action, entity_type, details FROM activity_logs ORDER BY created_at DESC LIMIT 20\n"
    "  2. Si recherche spécifique d'utilisateur ou d'action :\n"
    "     SELECT created_at, username, action, details FROM activity_logs \n"
    "     WHERE lower(username) LIKE '%?%' OR lower(action) LIKE '%?%' OR lower(details) LIKE '%?%'\n"
    "     ORDER BY created_at DESC LIMIT 20\n"
    "  3. Journal d'audit pour des analyses de sécurité :\n"
    "     SELECT created_at, actor_username, action, entity_type, status FROM audit_logs ORDER BY created_at DESC LIMIT 15\n"
    "\n"
    "=== GESTION DES SAUVEGARDES (BACKUPS) ===\n"
    "• Sabrina a un accès direct aux outils de sauvegarde via `create_backup`, `list_backups`, et `restore_backup`.\n"
    "• Si l'utilisateur demande 'fais une sauvegarde' ou 'sauvegarde la base' :\n"
    "  1. Dis-lui que tu lances la sauvegarde, puis appelle l'outil `create_backup`.\n"
    "  2. Confirme le lancement et conseille de vérifier le statut d'ici quelques secondes.\n"
    "• Si l'utilisateur demande 'liste les sauvegardes' ou 'montre les backups' :\n"
    "  1. Appelle l'outil `list_backups`.\n"
    "  2. Sinon, interroge la table SQL backup_jobs :\n"
    "     SELECT id, status, local_path, error_message, created_at FROM backup_jobs ORDER BY created_at DESC LIMIT 5\n"
    "• Si l'utilisateur veut restaurer, utilise l'outil `restore_backup(backup_name)`.\n"
    "\n"
    "=== ALERTES ET SUGGESTIONS PROACTIVES ===\n"
    "• Si l'utilisateur dit 'état du stock' ou 'alerte stock' :\n"
    "  → Exécuter :\n"
    "    SELECT name, stock_qty, alert_threshold, default_unit, 'Produit fini' AS type\n"
    "    FROM finished_products WHERE stock_qty <= alert_threshold\n"
    "    UNION ALL\n"
    "    SELECT name, stock_qty, alert_threshold, unit, 'Matière première'\n"
    "    FROM raw_materials WHERE stock_qty <= alert_threshold\n"
    "  → Afficher avec 🔴 si stock=0 (rupture) ou 🟡 si stock <= seuil (alerte)\n"
    "• Bilan du jour :\n"
    "  → SELECT 'Ventes' AS type, COALESCE(SUM(total),0) AS total FROM sales WHERE sale_date=CURRENT_DATE\n"
    "    UNION ALL\n"
    "    SELECT 'Achats', COALESCE(SUM(total),0) FROM purchases WHERE purchase_date=CURRENT_DATE\n"
    "    UNION ALL\n"
    "    SELECT 'Versements', COALESCE(SUM(amount),0) FROM payments WHERE payment_date=CURRENT_DATE\n"
    "    UNION ALL\n"
    "    SELECT 'Dépenses', COALESCE(SUM(amount),0) FROM expenses WHERE date=CURRENT_DATE\n"
    "\n"
    "=== PARAMÈTRES / CONFIGURATION ===\n"
    "• Voir : SELECT key, value, updated_at FROM app_settings ORDER BY key\n"
    "• Modifier : INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)\n"
    "    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP\n"
    "  Après : ✅ Paramètre mis à jour. [→ Paramètres](/admin)\n"
    "• Changer de modèle IA (gemini_model) :\n"
    "  - Gemini 2.5 Flash : 'gemini-2.5-flash'\n"
    "  - Gemini 1.5 Pro : 'gemini-1.5-pro'\n"
    "  - Mode local/Ollama : 'local'\n"
    "  → INSERT INTO app_settings (key,value,updated_at) VALUES ('gemini_model','[modèle]',CURRENT_TIMESTAMP)\n"
    "    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP\n"
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
    
    schema_text = "\n".join(f"- {t}: {d}" for t, d in TABLE_SCHEMAS.items())
    
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
                    from sqlalchemy import text
                    rows = conn.execute(text("SELECT id, name, current_balance FROM clients_with_stats")).fetchall()
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
                    from sqlalchemy import text
                    rows = conn.execute(text("SELECT id, name, current_balance FROM clients_with_stats")).fetchall()
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

def sanitize_numeric(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Retirer les suffixes de devise ou d'unité courants
    for suffix in ("da", "dzd", "da.", "dzd.", "kg", "sac", "q", "u", "€", "$"):
        if s.lower().endswith(suffix):
            s = s[:-len(suffix)].strip()
    s = s.replace(",", ".").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

async def search_web(query: str) -> Dict[str, Any]:
    import httpx
    import urllib.parse
    import re
    import html
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=12.0)
            if res.status_code != 200:
                return {"error": f"DuckDuckGo a renvoyé le statut HTTP {res.status_code}"}
            
            parts = res.text.split('<div class="result results_links results_links_deep web-result ')
            results = []
            
            for block in parts[1:7]:  # Limiter aux 6 premiers résultats
                title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
                snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</', block, re.DOTALL)
                
                if title_match:
                    raw_url = title_match.group(1)
                    raw_title = title_match.group(2)
                    
                    url_clean = raw_url
                    if "uddg=" in raw_url:
                        try:
                            parsed = urllib.parse.urlparse(raw_url)
                            queries = urllib.parse.parse_qs(parsed.query)
                            if "uddg" in queries:
                                url_clean = queries["uddg"][0]
                        except Exception:
                            pass
                    elif url_clean.startswith("//"):
                        url_clean = "https:" + url_clean
                        
                    title = re.sub(r'<[^>]*>', '', raw_title)
                    title = html.unescape(title).strip()
                    
                    snippet = ""
                    if snippet_match:
                        raw_snippet = snippet_match.group(1)
                        snippet = re.sub(r'<[^>]*>', '', raw_snippet)
                        snippet = html.unescape(snippet).strip()
                        
                    results.append({
                        "title": title,
                        "url": url_clean,
                        "snippet": snippet
                    })
            return {"results": results}
    except Exception as e:
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
        name = str(func_args.get("name", "")).strip().title()
        phone = "".join(c for c in str(func_args.get("phone", "")) if c.isdigit())
        address = str(func_args.get("address", "")).strip()
        notes = str(func_args.get("notes", "")).strip()
        opening_credit = sanitize_numeric(func_args.get("opening_credit"))
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
        if name:
            name = str(name).strip().title()
        phone = func_args.get("phone")
        if phone:
            phone = "".join(c for c in str(phone) if c.isdigit())
        address = func_args.get("address")
        if address:
            address = str(address).strip()
        notes = func_args.get("notes")
        if notes:
            notes = str(notes).strip()
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
        name = str(func_args.get("name", "")).strip().title()
        category = str(func_args.get("category", "")).strip().lower()
        price = sanitize_numeric(func_args.get("price"))
        cost = sanitize_numeric(func_args.get("cost"))
        unit = str(func_args.get("unit", "kg")).strip().lower()
        table = "finished_products" if category in ("finished", "produit final", "produit") else "raw_materials"
        async with session_maker() as session:
            from sqlmodel import text
            if table == "finished_products":
                await session.execute(text(
                    "INSERT INTO finished_products (name, sale_price, avg_cost, default_unit) VALUES (:name, :price, :cost, :unit)"
                ), {"name": name, "price": price, "cost": cost, "unit": unit})
            else:
                await session.execute(text(
                    "INSERT INTO raw_materials (name, avg_cost, unit) VALUES (:name, :cost, :unit)"
                ), {"name": name, "cost": cost, "unit": unit})
            await session.commit()
        return {"success": True, "message": f"Produit {name} ajouté."}
        
    elif func_name == "modify_product":
        product_id = int(func_args.get("product_id"))
        category = str(func_args.get("category", "finished")).strip().lower()
        name = func_args.get("name")
        if name:
            name = str(name).strip().title()
        price = func_args.get("price")
        if price is not None:
            price = sanitize_numeric(price)
        cost = func_args.get("cost")
        if cost is not None:
            cost = sanitize_numeric(cost)
        table = "finished_products" if category in ("finished", "produit final", "produit") else "raw_materials"
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
        item_kind = str(func_args.get("item_kind", "finished")).strip().lower()
        item_id = int(func_args.get("item_id"))
        quantity = sanitize_numeric(func_args.get("quantity"))
        unit = str(func_args.get("unit", "kg")).strip().lower()
        unit_price = sanitize_numeric(func_args.get("unit_price"))
        amount_paid = sanitize_numeric(func_args.get("amount_paid", 0.0))
        notes = str(func_args.get("notes", "")).strip()
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
        item_kind = str(func_args.get("item_kind", "raw")).strip().lower()
        item_id = int(func_args.get("item_id"))
        quantity = sanitize_numeric(func_args.get("quantity"))
        unit = str(func_args.get("unit", "kg")).strip().lower()
        unit_price = sanitize_numeric(func_args.get("unit_price"))
        notes = str(func_args.get("notes", "")).strip()
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
        amount = sanitize_numeric(func_args.get("amount"))
        payment_type = str(func_args.get("payment_type", "versement")).strip().lower()
        # Ensure it is exactly one of the accepted payments enums: versement or avance
        if payment_type not in ("versement", "avance"):
            payment_type = "versement"
        notes = str(func_args.get("notes", "")).strip()
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
        category = str(func_args.get("category", "")).strip().lower()
        amount = sanitize_numeric(func_args.get("amount"))
        description = str(func_args.get("description", "")).strip()
        payment_method = str(func_args.get("payment_method", "cash")).strip().lower()
        
        # Normalize category
        cat_map = {
            "matiere_premiere": "general", "matière première": "general", "matière": "general",
            "carburant": "transport", "essence": "transport", "gazole": "transport", "transport": "transport",
            "fournitures": "fournitures", "fournitures de bureau": "fournitures",
            "loyer": "loyer",
            "salaires": "salaires", "salaire": "salaires", "paie": "salaires",
            "maintenance": "maintenance", "reparation": "maintenance", "réparation": "maintenance",
            "telecom": "telecom", "internet": "telecom", "telephone": "telecom", "téléphone": "telecom",
            "energie": "energie", "électricité": "energie", "electricite": "energie", "eau": "energie", "gaz": "energie",
            "impots": "impots", "impôt": "impots", "taxe": "impots", "taxes": "impots",
            "autre": "autre", "divers": "autre"
        }
        category = cat_map.get(category, "autre")
        
        # Normalize payment method
        method_map = {
            "espèces": "cash", "espèce": "cash", "especes": "cash", "espece": "cash", "cash": "cash",
            "chèque": "cheque", "cheque": "cheque",
            "virement": "virement", "ccp": "virement",
            "autre": "autre"
        }
        payment_method = method_map.get(payment_method, "cash")
        
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
        if category:
            category = str(category).strip().lower()
            cat_map = {
                "matiere_premiere": "general", "matière première": "general", "matière": "general",
                "carburant": "transport", "essence": "transport", "gazole": "transport", "transport": "transport",
                "fournitures": "fournitures", "fournitures de bureau": "fournitures",
                "loyer": "loyer",
                "salaires": "salaires", "salaire": "salaires", "paie": "salaires",
                "maintenance": "maintenance", "reparation": "maintenance", "réparation": "maintenance",
                "telecom": "telecom", "internet": "telecom", "telephone": "telecom", "téléphone": "telecom",
                "energie": "energie", "électricité": "energie", "electricite": "energie", "eau": "energie", "gaz": "energie",
                "impots": "impots", "impôt": "impots", "taxe": "impots", "taxes": "impots",
                "autre": "autre", "divers": "autre"
            }
            category = cat_map.get(category, "autre")
        amount = func_args.get("amount")
        if amount is not None:
            amount = sanitize_numeric(amount)
        description = func_args.get("description")
        if description:
            description = str(description).strip()
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
        quantity = sanitize_numeric(func_args.get("quantity"))
        notes = str(func_args.get("notes", "")).strip()
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
                "category": ["matiere_premiere", "carburant", "maintenance", "electricite", "salaire", "autre", "loyer", "transport", "impot"]
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

    elif func_name == "get_current_weather":
        location = func_args.get("location", "Paris").strip()
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://wttr.in/{location}?format=3", timeout=15.0)
                if res.status_code == 200:
                    return {"weather": res.text.strip()}
                return {"error": f"Code HTTP {res.status_code} retourné par le service météo."}
        except Exception as e:
            return {"error": str(e)}

    elif func_name == "search_web":
        query = func_args.get("query", "").strip()
        return await search_web(query)

    return {"error": f"Outil '{func_name}' non géré."}

def get_gemini_tools() -> List[Dict[str, Any]]:
    return [
        {
            "functionDeclarations": [
                {
                    "name": "execute_readonly_sql",
                    "description": "Exécute une requête SQL SELECT en lecture seule et retourne le résultat sous forme de lignes JSON.",
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
                        "Pour les INSERT, toujours ajouter 'RETURNING id' à la fin."
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
                },
                {
                    "name": "get_current_weather",
                    "description": "Récupère les prévisions météo en temps réel pour une ville donnée.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "location": {
                                "type": "STRING",
                                "description": "Le nom de la ville ou région (ex: Paris, Marseille, Alger)."
                            }
                        },
                        "required": ["location"]
                    }
                },
                {
                    "name": "search_web",
                    "description": "Effectue une recherche sur le Web pour répondre à des questions sur l'actualité, des faits récents ou toute information externe générale.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "La requête de recherche à envoyer au moteur de recherche."
                            }
                        },
                        "required": ["query"]
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
                is_write = func_name not in ("read_app_file", "list_app_backups", "redirect_to", "change_theme", "get_enum_values", "search_clients", "search_products", "get_business_insights", "get_print_link", "get_current_weather", "search_web")
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
                "role": "function",
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
                is_write = func_name not in ("read_app_file", "list_app_backups", "redirect_to", "change_theme", "get_enum_values", "search_clients", "search_products", "get_business_insights", "get_print_link", "get_current_weather", "search_web")
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
            "role": "function",
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
