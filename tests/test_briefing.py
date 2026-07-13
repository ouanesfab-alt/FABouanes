# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from app.modules.assistant.briefing import generate_briefing


class TestAssistantBriefing(unittest.TestCase):
    @patch("app.modules.assistant.briefing.db_manager")
    def test_generate_briefing_success(self, mock_db):
        # 1. Mock stock alerts
        mock_db.query_db.side_effect = [
            # Stock alerts return value
            [
                {"name": "Produit A", "stock_qty": 5, "alert_threshold": 10, "default_unit": "kg", "type": "Produit fini"},
                {"name": "Matiere B", "stock_qty": 0, "alert_threshold": 20, "unit": "litres", "type": "Matière première"}
            ],
            # Yesterday summary return value
            [
                {"ventes_hier": 15000, "achats_hier": 5000, "versements_hier": 12000, "depenses_hier": 2000}
            ],
            # Month summary return value
            [
                {"ca_mois": 450000, "benefice_mois": 95000}
            ],
            # Debtors return value
            [
                {"name": "Client A", "current_balance": 18000},
                {"name": "Client B", "current_balance": 9000}
            ]
        ]

        result = generate_briefing()

        assert result["has_briefing"] is True
        assert result["sections_count"] == 4
        assert result["alert_count"] == 2  # Produit A and Matiere B have high priority priority
        assert "☀️ **Bonjour ! Voici votre résumé :**" in result["markdown"]
        assert "⚠️ Alertes de Stock" in result["markdown"]
        assert "📋 Bilan d'hier" in result["markdown"]
        assert "📈 Ce mois-ci" in result["markdown"]
        assert "💳 Principaux débiteurs" in result["markdown"]

    @patch("app.modules.assistant.briefing.db_manager")
    def test_generate_briefing_empty(self, mock_db):
        # All queries return empty lists
        mock_db.query_db.return_value = []

        result = generate_briefing()

        assert result["has_briefing"] is False
        assert result["markdown"] == ""

    @patch("app.modules.assistant.briefing.db_manager")
    def test_generate_briefing_queries_exceptions(self, mock_db):
        # All queries raise exceptions
        mock_db.query_db.side_effect = Exception("DB Connection Error")

        result = generate_briefing()

        assert result["has_briefing"] is False
        assert result["markdown"] == ""

    @patch("app.modules.assistant.briefing.db_manager")
    def test_generate_briefing_non_dict_rows(self, mock_db):
        # SQLite queries might return tuple-like rows that fail dict conversion, testing fallback logic
        mock_db.query_db.side_effect = [
            # Stock alerts as tuples
            [
                ("Produit C", 2, 5, "kg", "Produit fini")
            ],
            # Yesterday summary as tuple
            [
                (1000, 0, 0, 0)
            ],
            # Month summary as tuple
            [
                (10000, 2000)
            ],
            # Debtors as tuple
            [
                ("Debiteur C", 5000)
            ]
        ]

        result = generate_briefing()

        assert result["has_briefing"] is True
        assert result["sections_count"] == 4
        assert result["alert_count"] == 1
        assert "Produit C" in result["markdown"]
        assert "Debiteur C" in result["markdown"]
