from __future__ import annotations

from app.core.exceptions import get_friendly_error_message, BusinessError

def test_friendly_error_business():
    exc = BusinessError("Erreur métier", code="some_code")
    assert get_friendly_error_message(exc) == "Erreur métier"

def test_friendly_error_foreign_key():
    exc = Exception("violates foreign key constraint 'fk_...'")
    assert "lié à d'autres opérations" in get_friendly_error_message(exc)

    exc_fr = Exception("la clé étrangère empêche la suppression")
    assert "lié à d'autres opérations" in get_friendly_error_message(exc_fr)

def test_friendly_error_unique():
    exc = Exception("duplicate key value violates unique constraint 'uniq_...'")
    assert "cette valeur existe déjà" in get_friendly_error_message(exc)

    exc_fr = Exception("la valeur d'une clé dupliquée rompt la contrainte unique")
    assert "cette valeur existe déjà" in get_friendly_error_message(exc_fr)

def test_friendly_error_out_of_range():
    exc = Exception("numeric value out of range")
    assert "dépasse les limites numériques" in get_friendly_error_message(exc)

    exc_fr = Exception("valeur numérique en dehors des limites")
    assert "dépasse les limites numériques" in get_friendly_error_message(exc_fr)

def test_friendly_error_value_assertion():
    exc_val = ValueError("La quantité produite doit être supérieure à zéro.")
    assert get_friendly_error_message(exc_val) == "La quantité produite doit être supérieure à zéro."

    exc_assert = AssertionError("Stock insuffisant.")
    assert get_friendly_error_message(exc_assert) == "Stock insuffisant."

