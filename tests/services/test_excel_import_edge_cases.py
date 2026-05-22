"""
Tests pour les cas limites d'importation Excel de l'historique client.
"""
# Choix importants :
# 1. Utilisation de mock pandas.read_excel pour simuler divers scénarios de structure de fichiers (NaN, désordre, mixte).
# 2. Utilisation de requêtes SQL réelles pour valider que le processus d'importation préserve correctement les données applicatives ('app') tout en nettoyant les anciens imports.

from __future__ import annotations
import pytest
import pandas as pd
from unittest.mock import patch
from app.services.excel_import_service import parse_client_history_excel
from app.services.client_import_service import import_client_history_from_excel
from app.core.db_access import execute_db, query_db


class TestEdgeCases:
    def test_dates_out_of_order_final_balance_unchanged(self):
        """
        Fichier avec dates dans le désordre.
        Le solde final doit être identique qu'on trie ou non.
        total_achats - total_verses = solde_final toujours vrai.
        """
        mock_df_raw = pd.DataFrame([
            [None, "Client Desordre", None, None, None],
            [None, None, None, None, None],
            ["Date", "Designation", "Montant a Payer", "Versement", "Reste a Payer"],
            ["03/01/2026", "Achat 2", "5000", "0", "15000"],
            ["01/01/2026", "Ancien solde", "0", "0", "10000"],
            ["02/01/2026", "Versement 1", "0", "4000", "6000"],
        ])

        with patch("pandas.read_excel") as mock_read_excel:
            mock_read_excel.side_effect = [
                mock_df_raw,
                pd.DataFrame({
                    "date_raw": ["03/01/2026", "01/01/2026", "02/01/2026"],
                    "designation": ["Achat 2", "Ancien solde", "Versement 1"],
                    "montant_achat_raw": ["5000", "0", "0"],
                    "montant_verse_raw": ["0", "0", "4000"],
                    "solde_cumule_raw": ["15000", "10000", "6000"],
                })
            ]

            result = parse_client_history_excel("dummy_desordre.xlsx")
            assert result["nb_dates_hors_ordre"] > 0
            assert result["solde_final"] == 6000.0
            assert result["total_achats"] == 5000.0
            assert result["total_verses"] == 4000.0

    def test_mixed_rows_achat_and_versement_simultaneous(self):
        """
        Ligne avec montant_achat > 0 ET montant_verse > 0.
        Les deux valeurs doivent être stockées. Type = 'mixte' ou 'immediat'.
        """
        mock_df_raw = pd.DataFrame([
            [None, "Client Mixte", None, None, None],
            [None, None, None, None, None],
            ["Date", "Designation", "Montant a Payer", "Versement", "Reste a Payer"],
            ["01/01/2026", "Achat mixte", "5000", "2000", "3000"],
            ["02/01/2026", "Achat immediat", "4000", "4000", "3000"],
        ])

        with patch("pandas.read_excel") as mock_read_excel:
            mock_read_excel.side_effect = [
                mock_df_raw,
                pd.DataFrame({
                    "date_raw": ["01/01/2026", "02/01/2026"],
                    "designation": ["Achat mixte", "Achat immediat"],
                    "montant_achat_raw": ["5000", "4000"],
                    "montant_verse_raw": ["2000", "4000"],
                    "solde_cumule_raw": ["3000", "3000"],
                })
            ]

            result = parse_client_history_excel("dummy_mixte.xlsx")
            rows = result["rows"]
            assert rows[0]["type_operation"] == "mixte"
            assert rows[0]["montant_achat"] == 5000.0
            assert rows[0]["montant_verse"] == 2000.0

            assert rows[1]["type_operation"] == "immediat"
            assert rows[1]["montant_achat"] == 4000.0
            assert rows[1]["montant_verse"] == 4000.0

    def test_reimport_deletes_old_import_excel_rows(self, client):
        """
        force_reimport=True supprime les anciennes lignes source='import_excel'
        mais PRESERVE les lignes source='app'.
        """
        # 1. Créer un client
        client_id = execute_db("INSERT INTO clients (name, opening_credit) VALUES ('Import Client Reimport', 0.0)")

        # 2. Insérer une ligne source='import_excel' et une ligne source='app'
        execute_db(
            """
            INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, solde_cumule, ordre_import, source)
            VALUES (%s, '2026-05-01', 'Ancien solde', 0.0, 0.0, 1000.0, 0, 'import_excel')
            """,
            (client_id,)
        )
        execute_db(
            """
            INSERT INTO client_history (client_id, operation_date, designation, montant_achat, montant_verse, solde_cumule, ordre_import, source)
            VALUES (%s, '2026-05-02', 'Vente app', 500.0, 0.0, 1500.0, 1, 'app')
            """,
            (client_id,)
        )

        # 3. Exécuter l'import avec force_reimport=True (mocker le parseur)
        mock_data = {
            "client_name": "Import Client Reimport",
            "solde_final": 2000.0,
            "rows": [
                {
                    "date": "2026-05-01",
                    "designation": "Nouvel Import Solde",
                    "montant_achat": 0.0,
                    "montant_verse": 0.0,
                    "solde_cumule": 2000.0,
                    "ordre_import": 0,
                }
            ]
        }

        with patch("app.services.client_import_service.parse_client_history_excel", return_value=mock_data):
            import_client_history_from_excel("dummy_reimport.xlsx", client_id=client_id, force_reimport=True)

        # 4. Vérifier que l'ancien 'import_excel' a été supprimé, le nouveau ajouté, et le 'app' préservé
        rows = query_db("SELECT * FROM client_history WHERE client_id = %s ORDER BY id", (client_id,))
        # On doit avoir:
        # - La ligne source='app' existante
        # - La nouvelle ligne importée source='import_excel'
        assert len(rows) == 2
        sources = {r["source"] for r in rows}
        assert sources == {"app", "import_excel"}

        designations = {r["designation"] for r in rows}
        assert "Ancien solde" not in designations
        assert "Vente app" in designations
        assert "Nouvel Import Solde" in designations

    def test_empty_cells_become_zero_not_none(self):
        """Cellules NaN dans le fichier → 0.0, pas None."""
        mock_df_raw = pd.DataFrame([
            [None, "Client NaN Cells", None, None, None],
            [None, None, None, None, None],
            ["Date", "Designation", "Montant a Payer", "Versement", "Reste a Payer"],
            ["01/01/2026", "Achat NaN", None, "nan", ""],
        ])

        with patch("pandas.read_excel") as mock_read_excel:
            mock_read_excel.side_effect = [
                mock_df_raw,
                pd.DataFrame({
                    "date_raw": ["01/01/2026"],
                    "designation": ["Achat NaN"],
                    "montant_achat_raw": [None],
                    "montant_verse_raw": ["nan"],
                    "solde_cumule_raw": [""],
                })
            ]

            result = parse_client_history_excel("dummy_nan.xlsx")
            row = result["rows"][0]
            assert row["montant_achat"] == 0.0
            assert row["montant_verse"] == 0.0
            assert row["solde_cumule"] == 0.0

    def test_corrupted_file_raises_value_error(self):
        """Fichier Excel sans aucune ligne valide → ValueError claire."""
        mock_df_raw = pd.DataFrame([
            [None, "Client Corrupted", None, None, None],
            [None, None, None, None, None],
            ["Date", "Designation", "Montant a Payer", "Versement", "Reste a Payer"],
            ["Date", "Header repeté", "Montant", "Verse", "Solde"],  # ligne invalide
        ])

        with patch("pandas.read_excel") as mock_read_excel:
            mock_read_excel.side_effect = [
                mock_df_raw,
                pd.DataFrame({
                    "date_raw": ["Date"],
                    "designation": ["Header repeté"],
                    "montant_achat_raw": ["Montant"],
                    "montant_verse_raw": ["Verse"],
                    "solde_cumule_raw": ["Solde"],
                })
            ]

            with pytest.raises(ValueError, match="Aucune ligne de données valide trouvée"):
                parse_client_history_excel("dummy_corrupt.xlsx")

    def test_ordre_import_is_sequential_from_zero(self):
        """ordre_import doit être 0, 1, 2... dans l'ordre exact du fichier."""
        mock_df_raw = pd.DataFrame([
            [None, "Client Sequentiel", None, None, None],
            [None, None, None, None, None],
            ["Date", "Designation", "Montant a Payer", "Versement", "Reste a Payer"],
            ["01/01/2026", "Achat 1", "1000", "0", "1000"],
            ["02/01/2026", "Achat 2", "2000", "0", "3000"],
            ["03/01/2026", "Versement 1", "0", "1500", "1500"],
        ])

        with patch("pandas.read_excel") as mock_read_excel:
            mock_read_excel.side_effect = [
                mock_df_raw,
                pd.DataFrame({
                    "date_raw": ["01/01/2026", "02/01/2026", "03/01/2026"],
                    "designation": ["Achat 1", "Achat 2", "Versement 1"],
                    "montant_achat_raw": ["1000", "2000", "0"],
                    "montant_verse_raw": ["0", "0", "1500"],
                    "solde_cumule_raw": ["1000", "3000", "1500"],
                })
            ]

            result = parse_client_history_excel("dummy_seq.xlsx")
            rows = result["rows"]
            assert len(rows) == 3
            assert rows[0]["ordre_import"] == 0
            assert rows[1]["ordre_import"] == 1
            assert rows[2]["ordre_import"] == 2
