# Règles d'Architecture Strictes — FABOuanes

## 1. Source de vérité unique (Architecture Modulaire)
- Toute la logique métier, les routes web et les schémas Pydantic DOIVENT résider dans `app/modules/<domaine>/` (`repository.py`, `service.py`, `schemas.py`, `web.py`).
- INTERDICTION d'ajouter de nouveaux fichiers dans `app/services/`, `app/core/schema/` ou `app/web/*_pages.py` (ces dossiers sont en cours de dépréciation/fusion vers `app/modules/`).
- INTERDICTION de créer des fichiers de contournement (`*compat*.py`, `*helpers*.py`, `*bootstrap*.py`).

## 2. Base de données & Transactions
- Toute écriture en base DOIT passer par le Unit of Work (`app/core/uow.py`).
- Les migrations passent EXCLUSIVEMENT par Alembic (`alembic/versions/`). Ne jamais modifier ou utiliser `app/core/schema_bootstrap.py`.
- Tous les montants financiers et quantités de stock utilisent `Decimal` / `Numeric` (jamais `float`).

## 3. Assistant IA (Sabrina)
- Les outils dans `app/modules/assistant/tool_actions_*.py` ne doivent JAMAIS exécuter de SQL d'écriture direct : ils doivent appeler les services métiers via `uow.py`.
- `app/modules/assistant/sql_tools.py` est strictement réservé au `SELECT` en lecture seule.

## 4. Tests & Qualité
- INTERDICTION de créer des fichiers `test_coverage_boost*` ou `test_ultra_coverage*`.
- Chaque test doit porter le nom du module métier testé (ex: `tests/test_sales.py`, `tests/test_payments.py`).