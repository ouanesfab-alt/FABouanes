# Alignements Architecturaux à Long Terme

Ce document décrit la vision et la feuille de route technique pour les futures évolutions de l'architecture de l'application **FABOuanes**.

---

## 1. Migration Progressive vers SQLAlchemy ORM & SQLModel

Actuellement, l'application utilise **SQLAlchemy Core** avec du SQL brut combiné à un helper de base de données personnalisé (`db_helpers.py` / `db_access.py`). Bien que cette approche soit performante, elle génère beaucoup de code répétitif et rend la maintenance complexe.

### Stratégie de Transition
- **Modèles Declaratifs** : Introduire progressivement **SQLModel** ou les classes héritées de `DeclarativeBase` (SQLAlchemy 2.0 mapped) pour définir les nouvelles entités et tables.
- **Coexistence** : Les repositories existants basés sur SQL brut coexisteront avec la nouvelle couche ORM.
- **Nouvelles Entités** : Tout nouveau module ou entité doit être créé directement sous forme de modèle ORM/SQLModel.
- **Migration progressive** :
  1. Migrer d'abord les entités simples (ex: `suppliers`, `expenses`).
  2. Migrer ensuite les entités transactionnelles complexes (`sales`, `purchases`, `payments`).

---

## 2. Enrichissement de la Documentation OpenAPI

Les endpoints FastAPI retournent actuellement beaucoup de réponses via des `JSONResponse` brutes ou des helpers génériques (`api_success()`), ce qui entraîne une perte de la documentation automatique des schémas Pydantic dans Swagger.

### Actions Requises
- **Response Models** : Ajouter l'argument `response_model` aux décorateurs de routes FastAPI (ex: `@router.get("/clients", response_model=ClientResponseList)`).
- **Enrichissement Pydantic** : Définir des schémas de retour complets enveloppant le format de succès (`{ "success": true, "data": ... }`).
- **Codes d'Erreur Explicit** : Documenter les réponses d'erreur à l'aide de l'argument `responses` sur les routes critiques (ex: `responses={404: {"model": ErrorResponseSchema}}`).

---

## 3. Versioning et Structure de l'API Mobile

Pour isoler le contrat mobile de l'API web et permettre au client mobile d'évoluer indépendamment, les routes mobiles ont été migrées.

### Architecture Actuelle
- **Préfixe Dédié** : `/api/mobile/v1` au lieu de `/api/v1`.
- **Routage Simplifié** : Suppression du sous-préfixe `/mobile` au sein des routes (ex: `/api/mobile/v1/clients` au lieu de `/api/v1/mobile/clients`).
- **Offline Sync** : Route d'enregistrement et synchronisation déplacée sous `/api/mobile/v1/offline/sync`.
