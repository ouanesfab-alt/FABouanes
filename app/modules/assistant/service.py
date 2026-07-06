import os
import json
import logging
import asyncio
import httpx
from typing import Any, Dict, List
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
        "RÈGLE: Ne PAS spécifier 'id' dans INSERT."
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
        "2. Être de bon conseil, précise, chaleureuse et professionnelle.\n"
        "3. Enregistrer des opérations à la demande (avec confirmation obligatoire par l'utilisateur).\n"
        "4. Formater les données chiffrées sous forme de magnifiques tableaux Markdown.\n\n"
        f"SCHÉMA DE LA BASE DE DONNÉES (utilise-le directement sans appeler get_schema) :\n{schema_text}\n\n"
        f"{APP_ROUTES}\n"
        f"{ACTION_GUIDE}\n\n"
        "RÈGLES ABSOLUES :\n"
        "- Ne JAMAIS lire la table 'users'.\n"
        "- Confirmer TOUJOURS avant toute opération d'écriture (INSERT/UPDATE/DELETE).\n"
        "- Limiter les requêtes SQL à 100 lignes max (LIMIT 100).\n"
    )

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
        with db_manager.db_transaction() as conn:
            try:
                cur = conn.execute(sql_to_run)
                rows = cur.fetchall()
                cur.close()
                return {"rows": serialize_for_json([dict(r) for r in rows])}
            finally:
                conn.rollback()
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

async def call_gemini_api(contents: List[Dict[str, Any]], api_key: str, model_name: str = "gemini-flash-latest") -> Dict[str, Any]:
    """Appelle l'API Gemini avec les messages et outils définis."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    tools = [
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
                        "Pour les INSERT, toujours ajouter 'RETURNING id' à la fin pour récupérer l'ID créé. "
                        "La réponse contiendra 'inserted_id' si RETURNING est utilisé."
                    ),
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "La requête SQL d'écriture complète à exécuter. Pour INSERT, terminer par 'RETURNING id'."
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
    ]
    
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

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"

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
    schema_text = "\n".join(f"- {t}: {d}" for t, d in TABLE_SCHEMAS.items())
    system_prompt = get_sabrina_system_prompt(OLLAMA_MODEL)
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_readonly_sql",
                "description": "Exécute une requête SQL SELECT en lecture seule et retourne les résultats.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "La requête SQL SELECT complète à exécuter."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "execute_write_sql",
                "description": (
                    "Exécute une requête SQL d'écriture (INSERT, UPDATE, DELETE) pour ajouter, modifier ou supprimer des données. "
                    "Pour les INSERT, toujours ajouter 'RETURNING id' à la fin pour récupérer l'ID créé. "
                    "La réponse contiendra 'inserted_id' si RETURNING est utilisé."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "La requête SQL complète (INSERT ... RETURNING id, UPDATE ou DELETE)."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    
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
    for turn in range(max_turns):
        payload = {
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 2048}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                    timeout=180.0
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            yield {"type": "error", "error": f"⚠️ Erreur IA locale (Ollama) : {str(e)}"}
            return
            
        message = data.get("message", {})
        tool_calls = message.get("tool_calls", [])
        content = message.get("content", "")
        
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
                if confirmed_query and confirmed_query.strip() == sql_query.strip():
                    yield {"type": "status", "message": "Modification de la base de données locale (confirmée)..."}
                    output = execute_write_sql(sql_query)
                else:
                    yield {
                        "type": "confirmation_required",
                        "query": sql_query,
                        "message": "Je m'apprête à modifier la base de données (IA locale). Veuillez confirmer la requête SQL ci-dessous :"
                    }
                    return
            else:
                output = {"error": f"Outil '{func_name}' inconnu."}
                
            ollama_messages.append({
                "role": "tool",
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
    
    user_model = db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip()
    if not user_model:
        user_model = "gemini-3.1-flash-lite"
        
    if user_model.lower() in ("local", "ollama"):
        async for event in run_ollama_agent_generator(messages, confirmed_query):
            yield event
        return
        
    contents = list(messages)
    max_turns = 5
    for turn in range(max_turns):
        res = None
        last_exception = None
        
        candidate_models = [user_model]
        fallbacks = ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-flash-latest"]
        for m in fallbacks:
            if m != user_model and m not in candidate_models:
                candidate_models.append(m)
                
        for model in candidate_models:
            try:
                res = await call_gemini_api(contents, api_key, model_name=model)
                break
            except Exception as exc:
                last_exception = exc
                logger.warning("Erreur avec le modèle %s : %s. Essai du modèle suivant...", model, exc)
                continue
                
        if res is None:
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
                
        candidates = res.get("candidates", [])
        if not candidates:
            yield {"type": "error", "error": "L'assistant n'a pas renvoyé de réponse."}
            return
            
        content_obj = candidates[0].get("content", {})
        parts = content_obj.get("parts", [])
        contents.append(content_obj)
        
        tool_calls = [p for p in parts if "functionCall" in p]
        
        if not tool_calls:
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            yield {"type": "final_response", "text": "".join(text_parts)}
            return
            
        function_responses = []
        for part in tool_calls:
            func_call = part["functionCall"]
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
                
                # Vérification de la confirmation
                if confirmed_query and confirmed_query.strip() == sql_query.strip():
                    yield {"type": "status", "message": "Modification de la base de données (confirmée)..."}
                    output = execute_write_sql(sql_query)
                else:
                    yield {
                        "type": "confirmation_required",
                        "query": sql_query,
                        "message": "Je m'apprête à modifier la base de données. Veuillez confirmer la requête SQL ci-dessous :"
                    }
                    return
            else:
                output = {"error": f"Outil '{func_name}' inconnu."}
                
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
