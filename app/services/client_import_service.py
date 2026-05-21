from __future__ import annotations

from app.core.db_helpers import execute_db, query_db, db_transaction
from app.services.excel_import_service import parse_client_history_excel


def import_client_history_from_excel(
    file_path: str,
    client_id: int | None = None,
    force_reimport: bool = True
) -> dict:
    """
    Importe l'historique complet d'un client à partir de son fichier Excel.

    Arguments:
      - file_path : chemin absolu du fichier Excel temporaire
      - client_id : ID optionnel d'un client existant (si déjà associé dans l'UI)
      - force_reimport : si True, écrase l'historique importé existant

    Retourne:
      {
        "client_id": int,
        "client_name": str,
        "nb_lignes": int,
        "solde_final": float
      }
    """
    # 1. Parser le fichier Excel
    data = parse_client_history_excel(file_path)
    client_name = data["client_name"]
    solde_final = data["solde_final"]
    rows = data["rows"]

    with db_transaction() as _:
        # 2. Résoudre ou créer le client
        if client_id is not None:
            # Vérifier que le client existe
            client = query_db(
                "SELECT id, name FROM clients WHERE id = %s",
                (client_id,),
                one=True,
            )
            if not client:
                raise ValueError(f"Le client spécifié (ID {client_id}) n'existe pas.")
        else:
            # Recherche par nom (insensible à la casse, espaces nettoyés)
            existing = query_db(
                "SELECT id, name FROM clients WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))",
                (client_name,),
                one=True,
            )
            if existing:
                client_id = existing["id"]
            else:
                # Créer le client avec le solde final comme opening_credit
                client_id = execute_db(
                    """
                    INSERT INTO clients (name, opening_credit, created_at, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (client_name, solde_final),
                )

        # 3. Vérifier s'il y a déjà un historique importé
        existing_history = query_db(
            "SELECT 1 FROM client_history WHERE client_id = %s AND source = 'import_excel' LIMIT 1",
            (client_id,),
            one=True,
        )

        if existing_history:
            if not force_reimport:
                raise ValueError(
                    f"Un historique Excel importé existe déjà pour le client '{client_name}' "
                    "et force_reimport est désactivé."
                )
            # Supprimer l'ancien historique Excel importé
            execute_db(
                "DELETE FROM client_history WHERE client_id = %s AND source = 'import_excel'",
                (client_id,),
            )

        # 4. Mettre à jour le solde (opening_credit) du client dans la table clients
        execute_db(
            "UPDATE clients SET opening_credit = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (solde_final, client_id),
        )

        # 5. Insérer en lot les nouvelles lignes dans client_history
        for r in rows:
            execute_db(
                """
                INSERT INTO client_history (
                    client_id, operation_date, designation,
                    montant_achat, montant_verse, solde_cumule,
                    ordre_import, source, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'import_excel', CURRENT_TIMESTAMP)
                """,
                (
                    client_id,
                    r["date"],
                    r["designation"],
                    r["montant_achat"],
                    r["montant_verse"],
                    r["solde_cumule"],
                    r["ordre_import"],
                ),
            )

    return {
        "client_id": client_id,
        "client_name": client_name,
        "nb_lignes": len(rows),
        "solde_final": solde_final,
    }
