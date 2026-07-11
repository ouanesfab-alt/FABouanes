from app.core.db_helpers import execute_db
try:
    n = execute_db("DELETE FROM rate_limit_events")
    print(f"Rate limit cleared — {n} entrées supprimées")
except Exception as e:
    print(f"Erreur: {e}")
