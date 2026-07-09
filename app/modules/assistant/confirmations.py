from __future__ import annotations

from app.modules.assistant.sql_tools import dry_run_sql


READ_ONLY_TOOL_NAMES = frozenset({
    "change_theme",
    "execute_readonly_sql",
    "forget",
    "get_business_insights",
    "get_current_weather",
    "get_enum_values",
    "get_print_link",
    "get_schema",
    "get_user_note",
    "list_app_backups",
    "list_user_notes",
    "read_app_file",
    "recall",
    "redirect_to",
    "remember",
    "search_clients",
    "search_products",
    "search_web",
})


def tool_requires_confirmation(tool_name: str) -> bool:
    return tool_name not in READ_ONLY_TOOL_NAMES


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
    elif name == "add_supplier":
        return f"Creer le fournisseur `{args.get('name')}` ?"
    elif name == "modify_supplier":
        return f"Modifier le fournisseur ID `{args.get('supplier_id')}` ?"
    elif name == "delete_supplier":
        return f"Supprimer le fournisseur ID `{args.get('supplier_id')}` ?"
    elif name == "add_sale":
        return f"Enregistrer une vente de {args.get('quantity')} {args.get('unit')} à {args.get('unit_price')} DA/unit (Montant payé: {args.get('amount_paid', 0)} DA) ?"
    elif name == "add_purchase":
        return f"Enregistrer un achat de {args.get('quantity')} {args.get('unit')} à {args.get('unit_price')} DA/unit ?"
    elif name == "add_payment":
        return f"Enregistrer un versement de {args.get('amount')} DA pour le client ID `{args.get('client_id')}` ?"
    elif name == "add_supplier_payment":
        return f"Enregistrer un versement de {args.get('amount')} DA au fournisseur ID `{args.get('supplier_id')}` ({args.get('payment_type', 'versement')}) ?"
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
    elif name == "create_user_note":
        return f"Créer une nouvelle note '{args.get('title', 'Sans titre')}' ?"
    elif name == "save_user_note":
        return f"Enregistrer les modifications sur la note '{args.get('title') or args.get('note_id')}' ?"
    elif name == "delete_user_note":
        return f"Supprimer la note ID '{args.get('note_id')}' ?"
    return f"Confirmer l'opération '{name}' avec les paramètres : {args}"
