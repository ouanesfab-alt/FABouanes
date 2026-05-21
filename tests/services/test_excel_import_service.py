from __future__ import annotations
from unittest.mock import patch
import pandas as pd
import pytest
from app.services.excel_import_service import parse_client_history_excel


def test_parse_client_history_excel_success():
    # Mock data for Excel file
    # First iloc[0, 1] is client name.
    # Ligne 2 (index 2) is headers: Date | Designation | Montant a Payer | Versement | Reste a Payer
    mock_df_raw = pd.DataFrame([
        [None, "Achour Boudjmaa", None, "TEL :", None],
        [None, None, None, None, None],
        ["Date", "Designation", "Montant a Payer", "Versement", "Reste a Payer"],
        ["01/01/2026", "Ancien solde", "0", "0", "10000"],
        ["02/01/2026", "Achat 1", "5000", "0", "15000"],
        ["03/01/2026", "Versement 1", "0", "4000", "11000"],
    ])

    with patch("pandas.read_excel") as mock_read_excel:
        # Mock first read (raw) and second read (with skiprows)
        mock_read_excel.side_effect = [
            mock_df_raw,  # First call (header=None)
            pd.DataFrame({
                "date_raw": ["01/01/2026", "02/01/2026", "03/01/2026"],
                "designation": ["Ancien solde", "Achat 1", "Versement 1"],
                "montant_achat_raw": ["0", "5000", "0"],
                "montant_verse_raw": ["0", "0", "4000"],
                "solde_cumule_raw": ["10000", "15000", "11000"],
            })  # Second call (with skiprows=2)
        ]

        result = parse_client_history_excel("dummy_path.xlsx")
        
        assert result["client_name"] == "Achour Boudjmaa"
        assert result["solde_final"] == 11000.0
        assert result["total_achats"] == 5000.0
        assert result["total_verses"] == 4000.0
        assert result["nb_lignes"] == 3
        
        # Verify rows classification
        rows = result["rows"]
        assert rows[0]["type_operation"] == "ouverture"
        assert rows[1]["type_operation"] == "achat"
        assert rows[2]["type_operation"] == "versement"
