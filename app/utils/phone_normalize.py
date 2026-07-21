"""
Bilingual/International phone number normalization utility.
"""
from __future__ import annotations


def normalize_phone_number(phone: str) -> str:
    """Normalize Algerian/international phone numbers into a standard clean format (+213XXXXX)."""
    if not phone:
        return ""
    # Strip all non-digit characters except '+'
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
    
    # If starts with '00213', replace with '+213'
    if cleaned.startswith("00213"):
        cleaned = "+213" + cleaned[5:]
    
    # If starts with '0' (but not '00'), replace with '+213'
    elif cleaned.startswith("0") and not cleaned.startswith("00"):
        cleaned = "+213" + cleaned[1:]
        
    # If starts with '213' without '+', add '+'
    elif cleaned.startswith("213") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned

    # If it is a local 9-digit number without prefix, assume Algerian +213
    elif len(cleaned) == 9 and not cleaned.startswith("+"):
        cleaned = "+213" + cleaned
        
    return cleaned
