# Changelog

Toutes les évolutions notables de FABOuanes sont documentées ici.

Le format s'inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/) et le projet suit un versionnement inspiré de [SemVer](https://semver.org/lang/fr/).

> **Note** : ce fichier est un point de départ, reconstruit à partir des migrations de base de données présentes dans `alembic/versions/`. Aucun historique Git n'était disponible au moment de sa création. À partir de maintenant, ajoutez une entrée à chaque version publiée.

---

## [2.3.0] — 2026-09-16

### Architecture & Unification des Données
- **Domaine Production Standardisé** : Création des classes `ProductionBatchRepository`, `ProductionBatchItemRepository` et `ProductionService` alignées sur l'architecture en couches du projet, avec session asynchrone `AsyncSession` injectée via `Depends(get_async_session)`.
- **Accès aux Données Async ORM (SQLAlchemy 2.0)** :
  - Migration intégrale du service de comptabilité SCF (`scf_service.py`) vers des requêtes typées SQLAlchemy 2.0 Async sans SQL brut.
  - Migration des exports de rapports (Livre Journal et Marge Brute) dans `ReportsRepository` et `ReportsService`.
  - Migration des sélections de partenaires (`operations_pages.py`) et du calcul prédictif Sabrina (`dashboard_pages.py`).
- **Élimination des Conflits et Duplications** :
  - Suppression de `app/core/db.py` en doublon avec le package `app/core/db/`.
  - Résolution de la double inclusion du router comptabilité (`AccountingModule` unifié).
  - Déduplication de `recipe_service.py` délégant directement à `SavedRecipeRepository`.
  - Protection contre la duplication d'entités clientes (`ConflictError` sur doublon de nom).
- **Performances & Base de Données** :
  - Migration Alembic `0039_perf_indexes_v2_3` ajoutant les index de performance B-Tree sur `production_batches`, `expenses`, `payments` et `sales`.
- **Nettoyage & Outillage** :
  - 0 warning / 0 erreur Ruff sur l'ensemble du projet.
  - Synchronisation stricte des versions (`pyproject.toml`, `app/version.py`, `README.md`).

---

## [2.2.0] — 2026-08-08

### Refactorisation CSS Majeure
- **Nettoyage & Consolidation CSS** : Branche `refacto/css-cleanup` avec zéro régression visuelle et 1323 tests validés (96.84% couverture).
- **Suppression du Code Mort & Doublons** : Nettoyage des `@font-face` `.ttf` superflus, suppression des fichiers `.woff2` non référencés, fusion des sélecteurs `.btn` (6 occurrences réduites à 1) et `.app-content`.
- **Outillage & Production** : Ajout de `.editorconfig`, `.stylelintrc.json`, script de bundling/minification `scripts/build_css.py` et documentation dans `docs/css_architecture.md`.

---

## [2.1.0] — 2026-07-19

### Ajouté
- Suite de tests complète : 541 tests automatisés couvrant les modules métier, les helpers, l'assistant Sabrina, les validateurs, la couche DB et la gestion des exceptions.
- Nouveaux fichiers de tests ciblés : `test_db_helpers.py`, `test_rate_limit_store.py`, `test_exception_handlers.py`, `test_low_coverage_boost.py`, `test_coverage_final_push.py`.

### Amélioré
- Couverture de tests portée à **78 %** (seuil CI élevé de 20 % → 75 %).
- README entièrement reécrit : badges à jour, configuration complète, section limitations, tableau des métriques de tests.
- `.gitignore` enrichi : exclusion des logs de stress test, des rapports de couverture HTML, des audits Sabrina.

### Corrigé
- `app/core/lifespan.py` : le worker de fond (`background_jobs`) démarre désormais **après** `bootstrap_and_migrate()`, ce qui élimine l'erreur `la relation « background_jobs » n'existe pas` au premier démarrage.
- Mocks des tests corrigés : chemins d'importation (`app.core.db_helpers.execute_db`), appel de méthode statique (`_DbRateLimitStore().clear_all()`), signatures d'exceptions (`NotFoundError`, `ValidationError`).

### Nettoyé
- Suppression des fichiers parasites de la racine du dépôt : `http_stress_test.log`, `sabrina_audit.jsonl`, `sabrina_failures.jsonl`.

---

## [2.0.5] — 2026-07-19

### Sécurisé (Correctif final)
- Déduplication intelligente des ventes et paiements lors du traitement asynchrone des tables de staging (PWA offline sync).
- Ajout d'une validation stricte de la dimension de l'embedding (longueur 1536) retourné par Gemini pour éviter tout plantage SQL pgvector.

---

## [2.0.3] — 2026-07-19

### Optimisé
- Mise en cache en mémoire (`_embedding_cache`) des embeddings de requêtes pour Sabrina afin de diviser par deux le délai réseau et d'éviter les appels API Gemini redondants.
- Filtrage par seuil de pertinence (score >= 0.5) sur la recherche vectorielle afin de n'injecter dans le RAG de Sabrina que des produits sémantiquement pertinents.

---

## [2.0.2] — 2026-07-19

### Ajouté
- Indexation sémantique automatique du catalogue : liaison du bus d'événements (`app/core/events.py`) pour déclencher automatiquement l'indexation vectorielle en arrière-plan dès qu'un produit fini ou une matière première est créé(e) ou modifié(e).

---

## [2.0.1] — 2026-07-19

### Optimisé & Sécurisé
- Purge automatique de la file d'attente (`background_jobs`) : suppression automatique des jobs terminés depuis plus de 24h et des jobs échoués depuis plus de 7 jours.
- Récupération automatique des tâches bloquées (`stale jobs`) restées à l'état `'running'` suite à un crash/arrêt de worker.
- Amélioration de la résilience lors de l'appel d'embeddings (Gemini API) avec intégration de retries automatiques et de backoff exponentiel.

---

## [2.0.0] — 2026-07-19

### Ajouté
- File d'attente distribuée de tâches d'arrière-plan (`background_jobs`) s'appuyant sur PostgreSQL `FOR UPDATE SKIP LOCKED`.
- Verrous applicatifs PostgreSQL transactionnels (`Advisory Locks`) pour sécuriser la facturation sans doublon.
- Support de l'extension `pgvector` de PostgreSQL avec RAG sémantique pour Sabrina IA, et fallback mathématique Python sur SQLite/Postgres standard.
- Tables de staging (`offline_sales_staging`, `offline_payments_staging`) et API de synchronisation asynchrone pour la PWA.
- Chargement des librairies réactives HTMX et AlpineJS avec mise en conformité de la Content-Security-Policy (CSP).

---

## [1.3.0] — 2026-07-19

### Ajouté
- Mémoire persistante pour l'assistant Sabrina (migration `0036_sabrina_memory`)
- Système de gamification (migration `0034_gamification`)
- Historique client enrichi et impression dédiée (migration `0032_client_history`)
- Vues et alertes de rapports (migration `0033_views_and_alerts`)
- Triggers `updated_at` automatiques sur les tables principales (migration `0031_updated_at_triggers`)
- Index et optimisations de vues pour les tableaux de bord (migration `0029_db_opt_idx_views`)

### Corrigé
- Conversions de types de données incohérentes (migrations `0030_type_conversions`, `0035_data_types_fix`)
- Correction du graphe de Progression - Créances (KPI) en remplaçant la compilation native des types Enum par des chaînes de caractères simples (String) sous SQLAlchemy.
- Correction du problème de boucle de confirmation de l'assistant Sabrina et de la duplication de messages utilisateur dans l'historique de discussion.

---

## Comment utiliser ce fichier

Avant chaque publication :

1. Déplacez le contenu de `[Non publié]` sous une nouvelle section versionnée, ex. `## [1.4.0] — 2026-08-01`
2. Classez les changements sous les catégories standards : `Ajouté`, `Modifié`, `Déprécié`, `Retiré`, `Corrigé`, `Sécurité`
3. Mettez à jour le numéro de version dans `pyproject.toml`
