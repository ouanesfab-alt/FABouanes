"""
Service de Comptabilité Système Comptable Financier (SCF Algérie).
Génère la Balance Générale, le Bilan (Actif/Passif) et le Tableau des Comptes de Résultat (TCR).
"""
from __future__ import annotations
from typing import Dict, List, Any
from app.core.db_helpers import query_db


class SCFService:
    """Calculateur d'états financiers selon les normes du SCF Algérie."""

    @staticmethod
    def get_plan_comptable() -> List[Dict[str, str]]:
        """Retourne la nomenclature standard des comptes du SCF."""
        return [
            {"code": "101", "name": "Capital social", "class": "1"},
            {"code": "215", "name": "Installations techniques & matériel", "class": "2"},
            {"code": "300", "name": "Stocks de matières premières", "class": "3"},
            {"code": "355", "name": "Stocks de produits finis", "class": "3"},
            {"code": "401", "name": "Fournisseurs d'exploitations", "class": "4"},
            {"code": "411", "name": "Clients", "class": "4"},
            {"code": "530", "name": "Caisse", "class": "5"},
            {"code": "600", "name": "Achats consommés de matières premières", "class": "6"},
            {"code": "607", "name": "Achats de marchandises", "class": "6"},
            {"code": "625", "name": "Déplacements, missions et réceptions", "class": "6"},
            {"code": "629", "name": "Autres dépenses d'exploitation", "class": "6"},
            {"code": "700", "name": "Ventes de produits finis", "class": "7"},
            {"code": "707", "name": "Ventes de marchandises / matières", "class": "7"},
        ]

    @staticmethod
    async def get_balance_generale() -> List[Dict[str, Any]]:
        """
        Calcule la Balance Générale (Comptes 1 à 7) avec débits, crédits et soldes débiteurs/créditeurs.
        """
        # 1. Ventilation des Ventes (Compte 700 / 707)
        sales_row = query_db("SELECT COALESCE(SUM(total), 0) as total FROM sales", one=True)
        raw_sales_row = query_db("SELECT COALESCE(SUM(total), 0) as total FROM raw_sales", one=True)
        total_ventes_prod = float(sales_row["total"]) if sales_row else 0.0
        total_ventes_raw = float(raw_sales_row["total"]) if raw_sales_row else 0.0

        # 2. Ventilation des Achats (Compte 600)
        purchases_row = query_db("SELECT COALESCE(SUM(total), 0) as total FROM purchases", one=True)
        total_achats = float(purchases_row["total"]) if purchases_row else 0.0

        # 3. Encaisse et Caisse (Compte 530)
        payments_row = query_db("SELECT COALESCE(SUM(amount), 0) as total FROM payments", one=True)
        expenses_row = query_db("SELECT COALESCE(SUM(amount), 0) as total FROM expenses", one=True)
        total_encaisse = float(payments_row["total"]) if payments_row else 0.0
        total_depenses = float(expenses_row["total"]) if expenses_row else 0.0
        solde_caisse = total_encaisse - total_depenses

        # 4. Solde Clients (Compte 411)
        clients_row = query_db("SELECT COALESCE(SUM(current_debt), 0) as total_debt FROM clients_with_stats", one=True)
        solde_clients = float(clients_row["total_debt"]) if clients_row else 0.0

        # 5. Stocks (Compte 300 & 355)
        raw_stock_row = query_db("SELECT COALESCE(SUM(stock_qty * avg_cost), 0) as val FROM raw_materials", one=True)
        fin_stock_row = query_db("SELECT COALESCE(SUM(stock_qty * avg_cost), 0) as val FROM finished_products", one=True)
        val_stock_raw = float(raw_stock_row["val"]) if raw_stock_row else 0.0
        val_stock_fin = float(fin_stock_row["val"]) if fin_stock_row else 0.0

        accounts = [
            {"code": "300", "label": "Stocks de matières premières", "debit": val_stock_raw, "credit": 0.0},
            {"code": "355", "label": "Stocks de produits finis", "debit": val_stock_fin, "credit": 0.0},
            {"code": "411", "label": "Clients — Créances d'exploitation", "debit": solde_clients if solde_clients >= 0 else 0.0, "credit": abs(solde_clients) if solde_clients < 0 else 0.0},
            {"code": "530", "label": "Caisse / Trésorerie", "debit": solde_caisse if solde_caisse >= 0 else 0.0, "credit": abs(solde_caisse) if solde_caisse < 0 else 0.0},
            {"code": "600", "label": "Achats consommés de matières premières", "debit": total_achats, "credit": 0.0},
            {"code": "629", "label": "Autres charges et dépenses de gestion", "debit": total_depenses, "credit": 0.0},
            {"code": "700", "label": "Ventes de produits finis", "debit": 0.0, "credit": total_ventes_prod},
            {"code": "707", "label": "Ventes de matières / marchandises", "debit": 0.0, "credit": total_ventes_raw},
        ]

        # Calcul des soldes
        for acc in accounts:
            net = acc["debit"] - acc["credit"]
            acc["solde_debiteur"] = net if net > 0 else 0.0
            acc["solde_crediteur"] = abs(net) if net < 0 else 0.0

        return accounts

    @staticmethod
    async def get_tcr() -> Dict[str, Any]:
        """
        Génère le Tableau des Comptes de Résultat (TCR) selon la structure officielle SCF.
        """
        balance = await SCFService.get_balance_generale()
        ventes = sum(a["credit"] for a in balance if a["code"].startswith("7"))
        achats = sum(a["debit"] for a in balance if a["code"] in ("600", "607"))
        charges_autres = sum(a["debit"] for a in balance if a["code"] in ("629", "625"))

        marge_brute = ventes - achats
        valeur_ajoutee = marge_brute - charges_autres
        resultat_net = valeur_ajoutee

        return {
            "chiffre_affaires": ventes,
            "achats_consommes": achats,
            "marge_brute": marge_brute,
            "autres_charges_externes": charges_autres,
            "valeur_ajoutee": valeur_ajoutee,
            "resultat_exploitation": resultat_net,
            "resultat_net": resultat_net,
        }

    @staticmethod
    async def get_bilan() -> Dict[str, Any]:
        """
        Génère le Bilan Synthétique (Actif vs Passif & Capitaux Propres).
        """
        balance = await SCFService.get_balance_generale()

        # Actif Circulant
        stocks = sum(a["solde_debiteur"] for a in balance if a["code"].startswith("3"))
        creances = sum(a["solde_debiteur"] for a in balance if a["code"] == "411")
        trésorerie = sum(a["solde_debiteur"] for a in balance if a["code"] == "530")
        total_actif = stocks + creances + trésorerie

        # Passif & Capitaux Propres
        tcr = await SCFService.get_tcr()
        resultat = tcr["resultat_net"]
        fournisseurs = sum(a["solde_crediteur"] for a in balance if a["code"] == "401")
        capitaux_propres = total_actif - fournisseurs - resultat if total_actif >= (fournisseurs + resultat) else 0.0
        total_passif = capitaux_propres + resultat + fournisseurs

        return {
            "actif": {
                "stocks": stocks,
                "creances_clients": creances,
                "tresorerie_caisse": trésorerie,
                "total": total_actif
            },
            "passif": {
                "capitaux_propres": capitaux_propres,
                "resultat_exercice": resultat,
                "dettes_fournisseurs": fournisseurs,
                "total": total_passif
            }
        }
