from __future__ import annotations

import json
from typing import Any, Dict, List


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
                        "Exécute une seule requête SQL d'écriture (INSERT, UPDATE ou DELETE) "
                        "pour ajouter, modifier ou supprimer des données. Les instructions multiples, "
                        "les modifications de schéma et la table users sont interdites. Pour les INSERT, "
                        "ajouter 'RETURNING id' à la fin quand l'identifiant créé est utile."
                    ),
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "Une seule requête SQL d'écriture complète à exécuter."
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
                    "name": "add_supplier",
                    "description": "Cree un nouveau fournisseur via le service contacts.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {
                                "type": "STRING",
                                "description": "Nom du fournisseur."
                            },
                            "phone": {
                                "type": "STRING",
                                "description": "Telephone (optionnel)."
                            },
                            "address": {
                                "type": "STRING",
                                "description": "Adresse (optionnelle)."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Notes (optionnel)."
                            }
                        },
                        "required": ["name"]
                    }
                },
                {
                    "name": "modify_supplier",
                    "description": "Modifie un fournisseur existant via le service contacts.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "supplier_id": {
                                "type": "INTEGER",
                                "description": "Identifiant du fournisseur."
                            },
                            "name": {
                                "type": "STRING",
                                "description": "Nouveau nom (optionnel)."
                            },
                            "phone": {
                                "type": "STRING",
                                "description": "Nouveau telephone (optionnel)."
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
                        "required": ["supplier_id"]
                    }
                },
                {
                    "name": "delete_supplier",
                    "description": "Supprime un fournisseur uniquement s'il n'est lie a aucun achat.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "supplier_id": {
                                "type": "INTEGER",
                                "description": "Identifiant du fournisseur."
                            }
                        },
                        "required": ["supplier_id"]
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
                            },
                            "stock_qty": {
                                "type": "NUMBER",
                                "description": "Stock initial (optionnel)."
                            },
                            "alert_threshold": {
                                "type": "NUMBER",
                                "description": "Seuil d'alerte stock pour les matieres premieres (optionnel)."
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
                            },
                            "unit": {
                                "type": "STRING",
                                "description": "Nouvelle unite de mesure (optionnel)."
                            },
                            "stock_qty": {
                                "type": "NUMBER",
                                "description": "Nouveau stock (optionnel)."
                            },
                            "alert_threshold": {
                                "type": "NUMBER",
                                "description": "Nouveau seuil d'alerte pour les matieres premieres (optionnel)."
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
                    "name": "add_supplier_payment",
                    "description": "Enregistre un versement ou une avance effectuée à un fournisseur.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "supplier_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du fournisseur."
                            },
                            "amount": {
                                "type": "NUMBER",
                                "description": "Montant du versement en DA."
                            },
                            "payment_type": {
                                "type": "STRING",
                                "description": "Type : 'versement' ou 'avance' (défaut 'versement')."
                            },
                            "purchase_id": {
                                "type": "INTEGER",
                                "description": "Identifiant de l'achat associé (optionnel)."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Remarques (optionnel)."
                            }
                        },
                        "required": ["supplier_id", "amount"]
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
                    "description": "Fournit des rapports et des analyses proactives sur l'activité de l'entreprise (ex: débiteurs principaux, comparaison des ventes mensuelles, valorisation du stock, alertes stock, bilan financier synthétique).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "insight_type": {
                                "type": "STRING",
                                "description": "Le type d'analyse : 'top_debtors', 'monthly_sales_comparison', 'stock_valuation', 'stock_alerts', 'financial_summary' ou 'summary'."
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
                    "name": "import_client_history_excel",
                    "description": "Importe l'historique complet des transactions (achats/ventes, versements) d'un client à partir de son fichier Excel FABouanes.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "filepath": {
                                "type": "STRING",
                                "description": "Le chemin d'accès au fichier Excel sur le serveur."
                            },
                            "client_id": {
                                "type": "INTEGER",
                                "description": "ID facultatif du client (s'il existe déjà dans l'application)."
                            }
                        },
                        "required": ["filepath"]
                    }
                },
                {
                    "name": "import_bulk_clients_excel",
                    "description": "Importe une liste de plusieurs clients en masse à partir d'un fichier Excel.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "filepath": {
                                "type": "STRING",
                                "description": "Le chemin d'accès au fichier Excel contenant la liste des clients."
                            }
                        },
                        "required": ["filepath"]
                    }
                },
                {
                    "name": "import_bulk_products_excel",
                    "description": "Importe une liste de plusieurs produits (finis ou matières premières) en masse à partir d'un fichier Excel.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "filepath": {
                                "type": "STRING",
                                "description": "Le chemin d'accès au fichier Excel contenant la liste des produits."
                            },
                            "is_raw_material": {
                                "type": "BOOLEAN",
                                "description": "Mettre True si ce sont des matières premières, ou False si ce sont des produits finis."
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
                },
                {
                    "name": "remember",
                    "description": "Mémorise une information importante dans la mémoire persistante de Sabrina (préférences client, règles métier, corrections). Utilise cet outil quand l'utilisateur exprime une préférence, te corrige, ou te demande de retenir quelque chose.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "content": {
                                "type": "STRING",
                                "description": "L'information à mémoriser (ex: 'Ali préfère payer en espèces', 'Le prix du sac 50kg est toujours 3500 DA')."
                            },
                            "category": {
                                "type": "STRING",
                                "description": "Catégorie du souvenir : 'preference' (préférence utilisateur/client), 'rule' (règle métier), 'context' (contexte important), 'learned' (appris automatiquement), 'correction' (correction d'erreur), 'general' (autre)."
                            }
                        },
                        "required": ["content"]
                    }
                },
                {
                    "name": "recall",
                    "description": "Recherche dans la mémoire persistante de Sabrina pour retrouver des informations mémorisées précédemment (préférences, règles, corrections).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "Le terme de recherche pour retrouver des souvenirs pertinents. Laisser vide pour voir les plus récents."
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "forget",
                    "description": "Supprime un souvenir spécifique de la mémoire persistante de Sabrina.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "memory_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du souvenir à supprimer (obtenu via recall)."
                            }
                        },
                        "required": ["memory_id"]
                    }
                },
                {
                    "name": "list_user_notes",
                    "description": "Liste toutes les notes enregistrées de l'utilisateur dans son bloc-notes (retourne les IDs, titres, couleurs, épinglages, etc.).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {}
                    }
                },
                {
                    "name": "get_user_note",
                    "description": "Récupère le contenu complet d'une note spécifique à partir de son identifiant.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "note_id": {
                                "type": "STRING",
                                "description": "L'identifiant de la note (ex: note_123456)."
                            }
                        },
                        "required": ["note_id"]
                    }
                },
                {
                    "name": "create_user_note",
                    "description": "Crée une nouvelle note dans le bloc-notes avec un titre, du contenu et une couleur optionnelle.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {
                                "type": "STRING",
                                "description": "Le titre de la note."
                            },
                            "content": {
                                "type": "STRING",
                                "description": "Le contenu textuel de la note (Markdown supporté)."
                            },
                            "color": {
                                "type": "STRING",
                                "description": "La couleur visuelle de la note (yellow, rose, mint, blue, lavender, black)."
                            }
                        },
                        "required": ["title", "content"]
                    }
                },
                {
                    "name": "save_user_note",
                    "description": "Enregistre ou met à jour les informations d'une note existante (titre, contenu, couleur, épinglage).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "note_id": {
                                "type": "STRING",
                                "description": "L'identifiant de la note à sauvegarder."
                            },
                            "title": {
                                "type": "STRING",
                                "description": "Le nouveau titre de la note."
                            },
                            "content": {
                                "type": "STRING",
                                "description": "Le nouveau contenu textuel de la note."
                            },
                            "color": {
                                "type": "STRING",
                                "description": "La couleur de la note (yellow, rose, mint, blue, lavender, black)."
                            },
                            "pinned": {
                                "type": "BOOLEAN",
                                "description": "Mettre à True pour épingler la note en haut de la liste."
                            }
                        },
                        "required": ["note_id", "title", "content"]
                    }
                },
                {
                    "name": "delete_user_note",
                    "description": "Supprime définitivement une note du bloc-notes.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "note_id": {
                                "type": "STRING",
                                "description": "L'identifiant de la note à supprimer."
                            }
                        },
                        "required": ["note_id"]
                    }
                },
                {
                    "name": "list_recipes",
                    "description": "Liste toutes les recettes de production enregistrées avec leurs composants (matières premières et quantités).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {}
                    }
                },
                {
                    "name": "create_recipe",
                    "description": "Crée ou met à jour une recette de production pour un produit fini spécifique.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "finished_product_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du produit fini fabriqué."
                            },
                            "name": {
                                "type": "STRING",
                                "description": "Le nom de la recette."
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Notes ou remarques facultatives."
                            },
                            "items": {
                                "type": "ARRAY",
                                "description": "Liste des ingrédients. Chaque ingrédient doit être un objet contenant 'raw_material_id' et 'quantity'.",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "raw_material_id": {
                                            "type": "INTEGER"
                                        },
                                        "quantity": {
                                            "type": "NUMBER",
                                            "description": "Quantité nécessaire en kg."
                                        }
                                    },
                                    "required": ["raw_material_id", "quantity"]
                                }
                            }
                        },
                        "required": ["finished_product_id", "name", "items"]
                    }
                },
                {
                    "name": "delete_recipe",
                    "description": "Supprime définitivement une recette de production existante.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "recipe_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant de la recette à supprimer."
                            }
                        },
                        "required": ["recipe_id"]
                    }
                },
                {
                    "name": "list_bon_space_documents",
                    "description": "Recherche et liste les documents numérisés (PDF, factures, bons d'achat/vente, lots de production) de l'Espace Bons.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "Terme de recherche facultatif (nom de client, produit, date)."
                            },
                            "kind": {
                                "type": "STRING",
                                "description": "Filtre facultatif par type de document : 'sale' (vente), 'purchase' (achat), 'payment' (versement), 'production' (production), 'external' (PDF)."
                            },
                            "limit": {
                                "type": "INTEGER",
                                "description": "Nombre maximum de résultats (défaut 80)."
                            }
                        }
                    }
                },
                {
                    "name": "get_recent_activity_logs",
                    "description": "Récupère les derniers journaux d'activité et d'audit du système.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "limit": {
                                "type": "INTEGER",
                                "description": "Nombre maximum de logs à récupérer (défaut 50)."
                            }
                        }
                    }
                },
                {
                    "name": "get_active_alerts",
                    "description": "Récupère toutes les alertes de stock critique actuelles et les clients débiteurs en retard de paiement.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {}
                    }
                },
                {
                    "name": "run_system_maintenance",
                    "description": "Déclenche la maintenance de la base de données (optimisation des index, nettoyage des logs et caches). Uniquement disponible pour les administrateurs.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {}
                    }
                },
                {
                    "name": "save_backup_settings",
                    "description": "Enregistre la configuration des sauvegardes (dossier Google Drive local, rétentions et heure du snapshot quotidien).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "gdrive_backup_dir": {
                                "type": "STRING",
                                "description": "Chemin local du dossier synchronisé par Google Drive Desktop."
                            },
                            "backup_snapshot_time": {
                                "type": "STRING",
                                "description": "Heure du snapshot quotidien au format HH:MM (ex: 02:00)."
                            },
                            "backup_local_retention": {
                                "type": "INTEGER",
                                "description": "Nombre de jours de rétention pour les sauvegardes de nuit locales."
                            },
                            "backup_event_retention": {
                                "type": "INTEGER",
                                "description": "Nombre maximal d'événements de sauvegarde à conserver."
                            }
                        }
                    }
                },
                {
                    "name": "update_app_user",
                    "description": "Modifie les paramètres d'un utilisateur existant (rôle, statut actif/inactif, ou nouveau code PIN de mot de passe).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "user_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant unique de l'utilisateur à modifier."
                            },
                            "role": {
                                "type": "STRING",
                                "description": "Nouveau rôle de l'utilisateur (admin, manager, operator)."
                            },
                            "is_active": {
                                "type": "BOOLEAN",
                                "description": "Définir à True pour activer le compte, False pour le désactiver."
                            },
                            "new_password": {
                                "type": "STRING",
                                "description": "Nouveau code PIN de 4 chiffres pour réinitialiser le mot de passe (optionnel)."
                            }
                        },
                        "required": ["user_id", "role", "is_active"]
                    }
                },
                {
                    "name": "get_export_link",
                    "description": "Obtient le lien de téléchargement d'un export de données CSV ou JSON (clients, rapports globaux, journaux d'audit ou diagnostic système).",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "export_type": {
                                "type": "STRING",
                                "description": "Type d'export souhaité : 'clients' (tous les clients avec stats), 'reports' (résumé ventes/achats/bénéfices), 'audit' (journaux d'audit), ou 'diagnostic' (état technique système)."
                            },
                            "date_from": {
                                "type": "STRING",
                                "description": "Date de début pour filtrer l'export au format YYYY-MM-DD (optionnel, pour 'reports' et 'audit')."
                            },
                            "date_to": {
                                "type": "STRING",
                                "description": "Date de fin pour filtrer l'export au format YYYY-MM-DD (optionnel, pour 'reports' et 'audit')."
                            },
                            "audit_filters": {
                                "type": "OBJECT",
                                "description": "Filtres additionnels pour l'export 'audit' (optionnel).",
                                "properties": {
                                    "actor": {
                                        "type": "STRING",
                                        "description": "Nom de l'acteur (utilisateur)."
                                    },
                                    "action": {
                                        "type": "STRING",
                                        "description": "Nom de l'action."
                                    },
                                    "entity_type": {
                                        "type": "STRING",
                                        "description": "Type de l'entité."
                                    },
                                    "status": {
                                        "type": "STRING",
                                        "description": "Statut de l'action ('success' ou 'failure')."
                                    }
                                }
                            }
                        },
                        "required": ["export_type"]
                    }
                },
                {
                    "name": "create_invoice_document",
                    "description": "Crée une facture multi-lignes pour un client avec une liste d'articles vendus.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "client_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du client (optionnel)."
                            },
                            "lines": {
                                "type": "ARRAY",
                                "description": "La liste des lignes de facture.",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "item_key": {
                                            "type": "STRING",
                                            "description": "Clé de l'article au format 'finished:ID' ou 'raw:ID'."
                                        },
                                        "quantity": {
                                            "type": "NUMBER",
                                            "description": "Quantité vendue."
                                        },
                                        "unit": {
                                            "type": "STRING",
                                            "description": "Unité de mesure (ex: kg, sac, Qt)."
                                        },
                                        "unit_price": {
                                            "type": "NUMBER",
                                            "description": "Prix unitaire."
                                        },
                                        "custom_item_name": {
                                            "type": "STRING",
                                            "description": "Précision pour la ligne AUTRE (optionnel)."
                                        }
                                    },
                                    "required": ["item_key", "quantity", "unit", "unit_price"]
                                }
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Remarques (optionnel)."
                            },
                            "sale_date": {
                                "type": "STRING",
                                "description": "Date de la vente au format YYYY-MM-DD (optionnel)."
                            }
                        },
                        "required": ["lines"]
                    }
                },
                {
                    "name": "generate_quote",
                    "description": "Génère un devis ou une facture proforma estimative sans modifier les stocks ni les finances.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "client_name": {
                                "type": "STRING",
                                "description": "Nom du client destinataire du devis (optionnel)."
                            },
                            "lines": {
                                "type": "ARRAY",
                                "description": "La liste des lignes de devis.",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "item_name": {
                                            "type": "STRING",
                                            "description": "Nom du produit ou description de l'article."
                                        },
                                        "quantity": {
                                            "type": "NUMBER",
                                            "description": "Quantité."
                                        },
                                        "unit": {
                                            "type": "STRING",
                                            "description": "Unité de mesure."
                                        },
                                        "unit_price": {
                                            "type": "NUMBER",
                                            "description": "Prix unitaire estimé."
                                        }
                                    },
                                    "required": ["item_name", "quantity", "unit", "unit_price"]
                                }
                            },
                            "notes": {
                                "type": "STRING",
                                "description": "Notes ou conditions de validité (optionnel)."
                            }
                        },
                        "required": ["lines"]
                    }
                },
                {
                    "name": "get_stock_status",
                    "description": "Consulte l'état du stock des produits et signale les articles en rupture ou sous le seuil d'alerte.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "product_type": {
                                "type": "STRING",
                                "description": "Filtre par type de produit : 'finished' (produits finis), 'raw' (matières premières) ou 'all' (tous)."
                            },
                            "product_name": {
                                "type": "STRING",
                                "description": "Recherche par nom partiel (optionnel)."
                            }
                        }
                    }
                },
                {
                    "name": "get_payment_status",
                    "description": "Vérifie les règlements, le solde dû d'un client ou le statut de paiement d'une facture spécifique.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "client_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant du client (optionnel)."
                            },
                            "document_id": {
                                "type": "INTEGER",
                                "description": "L'identifiant de la facture (optionnel)."
                            }
                        }
                    }
                },
                {
                    "name": "get_financial_report",
                    "description": "Génère un rapport financier dynamique synthétisant les ventes, achats, dépenses et bénéfices nets sur une période.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "start_date": {
                                "type": "STRING",
                                "description": "Date de début de la période au format YYYY-MM-DD (optionnel)."
                            },
                            "end_date": {
                                "type": "STRING",
                                "description": "Date de fin de la période au format YYYY-MM-DD (optionnel)."
                            }
                        }
                    }
                }
            ]
        }
    ]
