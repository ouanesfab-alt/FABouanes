# Changelog

Toutes les évolutions notables de FABOuanes sont documentées ici.

Le format s'inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/) et le projet suit un versionnement inspiré de [SemVer](https://semver.org/lang/fr/).

> **Note** : ce fichier est un point de départ, reconstruit à partir des migrations de base de données présentes dans `alembic/versions/`. Aucun historique Git n'était disponible au moment de sa création. À partir de maintenant, ajoutez une entrée à chaque version publiée.

---

## [Non publié]

### À venir
- Augmentation du seuil de couverture de tests en CI (actuellement 20 %)
- Backend Redis optionnel pour le cache et le rate limiting (multi-worker)

---

## [1.3.0] — en cours

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
