# Architecture & Directives Techniques — FABOuanes

Ce document définit les règles architecturales et les conventions de développement du projet FABOuanes.

---

## 1. Directives d'Accès à la Base de Données (Accès Hybride)

L'application utilise un modèle d'accès hybride à la base de données. Chaque couche a un rôle et des règles d'utilisation stricts :

### A. Couche SQLModel / SQLAlchemy (Business & Domaine)
* **Usage :** Modèles métier, entités du domaine (`Sales`, `Purchases`, `Clients`, `FinishedProduct`, `RawMaterial`, `Expenses`, etc.).
* **Composants :** Services applicatifs (`app/services/*`, `app/modules/*/service.py`), routes API (`app/web/*`, `app/api/*`).
* **Session :** `get_async_session` pour l'asynchrone, `get_db_session` pour le synchrone.
* **Règle :** Toute nouvelle entité métier **DOIT** être un modèle SQLModel/SQLAlchemy et passer par l'ORM.

### B. Couche `db_helpers` / SQL Brut (Infrastructure système)
* **Usage :** Infrastructure à haute fréquence et sous-systèmes internes :
  * `background_jobs` (Worker polling loop)
  * `pubsub_events` & `outbox_events`
  * `idempotent_requests`
  * `rate_limit_events` (fallback DB)
* **Composants :** `app/core/db_helpers/manager.py`, `app/core/worker.py`, `app/core/events.py`.
* **Traduction de dialecte :** `CompatConnection` traduit automatiquement les placeholders `%s` en `?` pour SQLite tout en conservant les métadonnées de colonnes.
* **Règle :** N'utilisez `db_helpers` (`query_db`, `execute_db`, `db_transaction`) **QUE** pour le code d'infrastructure système. Ne l'utilisez PAS pour les requêtes métier applicatives.

---

## 2. Gestion du Schéma et Migrations

* **Unique source de vérité des évolutions :** **Alembic** (`alembic/versions/*`).
* **Rôle de `schema_bootstrap.py` :** Création initiale des tables (`CREATE TABLE IF NOT EXISTS`) et peuplement des données de démarrage (`seeds`) lors d'une installation neuve.
* **Interdictions :**
  * ❌ Ne JAMAIS ajouter de `ALTER TABLE` manuels dans `schema_bootstrap.py`.
  * ❌ Toute modification de colonne, ajout d'index ou création de table évolutive **DOIT** faire l'objet d'une migration Alembic versionnée dans `alembic/versions/`.
* **Atomicité :** Le bootstrap s'exécute dans une transaction DDL atomique unique avec rollback global en cas d'échec.

---

## 3. Worker & Tâches de Fond (`app/core/worker.py`)

* **Event Loop :** Le thread worker réutilise un `asyncio.AbstractEventLoop` dédié unique tout au long de son cycle de vie. Aucun loop éphémère ne doit être créé par job.
* **Self-healing & Cleanup :** `cleanup_background_jobs()` s'exécute automatiquement toutes les heures pour purger :
  * Les jobs terminés (>24h) ou échoués (>7j)
  * Les événements pubsub (>24h)
  * Les requêtes idempotentes (>7j)
  * Les entrées de staging offline traitées (>30j)

---

## 4. Découplage des Modules Optionnels (`app/core/plugin_registry.py`)

* **Principe :** `app.core` ne doit pas importer directement des dépendances depuis `app.modules.*` (ex: `assistant`).
* **Pattern :** Les modules enregistrent leurs fonctions dans le `plugin_registry` au chargement.
* **Invocations :** `registry.call("get_api_key")` ou `await registry.acall("get_embedding", text, api_key)`. Si un module n'est pas chargé, l'appel retourne `None` sans erreur.

---

## 5. Cache & Rate Limiting

* **Rate Limiting :** In-memory thread-safe par défaut (`_InMemoryRateLimitStore`). Compatible Redis via `REDIS_URL` ou DB via `FAB_RATE_LIMIT_BACKEND=db`.
* **Cache applicatif :** Interface `CacheBackend` avec invalidation par clés (`invalidate_keys(*keys)`). Compatible `InMemoryCache`, `RedisCache` et `HybridCache`.
