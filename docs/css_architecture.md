# Architecture et Règles CSS de FABouanes

## Responsabilités des Fichiers CSS

La base CSS sur-mesure de FABouanes est découpée selon une frontière stricte :

1. **`static/css/tokens.css`** (Design System & Variables)
   - **Rôle** : Unique source de vérité pour les variables globales CSS (`:root`, `[data-theme="dark"]`, `[data-theme="windows"]`).
   - **Contenu** : Polices système, palettes de couleurs Apple, variables de matériaux verres translucides, ombres, et en-tête de tableau sticky.
   - **Interdiction** : Aucun sélecteur de composant spécifique à une vue, aucun `!important` non justifié.

2. **`static/css/components.css`** (Composants UI Réutilisables)
   - **Rôle** : Composants graphiques et widgets partagés sur l'ensemble des pages.
   - **Contenu** : Buttons, cards, badges de statut (`.status-pill`), Spotlight Search (`.search-overlay`), modales de rapport, KPIs.

3. **`static/fonts/fonts.css`** (Polices Locales Subsettées)
   - **Rôle** : Déclaration des polices *Plus Jakarta Sans* en format `.woff2` avec plages Unicode précises pour les langues supportées.

4. **`static/app.css`** (Mise en Page Applicative & Métier)
   - **Rôle** : Layout principal (`.app-shell`, `.app-navbar`, `.app-sidebar`, `.app-content`), réactivité et surcharges spécifiques par page (Ventes, Achats, SCF, Production).

---

## Règles d'Évolution et Bonnes Pratiques

- **Toutes les media queries** doivent respecter la nomenclature standard des breakpoints (`576px`, `768px`, `992px`, `1200px`, `1400px`).
- **Aucune duplication de sélecteur** : Avant d'ajouter une classe, vérifier qu'elle n'existe pas déjà dans `components.css` ou `app.css`.
- **Limitation stricte du `!important`** : réservé uniquement aux utilitaires prioritaires ou aux surcharges explicites de bibliothèques tierces.
- **Build de Production** : Générer le paquet minifié via `python scripts/build_css.py`.
