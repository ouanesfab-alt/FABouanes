# Documentation Technique : Synchronisation Hors-ligne (Offline Sync)

Ce document décrit le fonctionnement de l'architecture hors-ligne (Offline PWA) de l'application **FABOuanes**, incluant le caching du Service Worker, le stockage local client avec IndexedDB et le protocole de synchronisation asynchrone sécurisé par idempotence.

---

## 1. Architecture Générale

Le mode hors-ligne repose sur la synergie de trois composants :

```mermaid
graph TD
    User[Utilisateur] -->|Saisit Opération| UI[Interface Web Offline]
    UI -->|Stocke localement| IDB[(IndexedDB)]
    SW[Service Worker] -->|Précâche les fichiers statiques| Cache[(Cache Storage)]
    Sync[offline-sync.js] -->|Détecte Réseau Online| API[/api/mobile/v1/offline/sync]
    IDB -->|Récupère opérations en attente| Sync
    API -->|Valide & Intègre| DB[(Base PostgreSQL)]
```

*   **Service Worker (`sw.js`)** : Intercepte les requêtes réseau pour servir les ressources statiques depuis le cache local (stratégie Cache-First) ou afficher une page fallback en cas de déconnexion.
*   **IndexedDB (`static/js/offline-db.js`)** : Base de données locale thread-safe intégrée au navigateur, utilisée pour mettre en cache les données de référence (clients, catalogue) et stocker les opérations (ventes, achats, paiements) saisies lorsque l'utilisateur est hors-ligne.
*   **Synchronisation Automatique (`static/js/offline-sync.js`)** : Script client qui écoute les événements réseau, détecte le retour de la connexion internet, et transmet séquentiellement les transactions en attente au serveur.

---

## 2. Rôle et Cycle de Vie du Service Worker (`sw.js`)

Le Service Worker gère deux types de caches :
1.  **Cache Statique (`STATIC_CACHE`)** : Contient l'ensemble des fichiers requis pour le fonctionnement minimal de l'interface (fichiers CSS, JS, icônes, polices).
2.  **Cache Dynamique (`RUNTIME_CACHE`)** : Conserve temporairement les pages visitées pour y accéder hors-ligne.

### Stratégies de mise en cache
*   **Asset statique (JS, CSS, images)** : **Cache-First**. Servis instantanément depuis le cache. En cas de mise à jour, la version du cache est incrémentée à la compilation.
*   **Pages de navigation principales** : **Network-First**. Tente d'abord le réseau pour obtenir la page la plus récente. En cas d'échec de connexion, sert la page depuis le cache ou affiche la page de secours `/static/offline.html`.
*   **Pages critiques exclusivement en ligne** : Les routes sous `/reports`, `/production`, `/admin` et `/purchases` ne sont jamais servies depuis le cache et affichent directement le fallback offline en cas de coupure réseau.

---

## 3. Stockage Local IndexedDB (`offline-db.js`)

IndexedDB stocke deux types de banques d'objets (Object Stores) :

### `reference_data`
Stocke les données de référence requises pour alimenter les listes déroulantes de saisie d'opérations hors-ligne :
*   `clients` : Liste des clients actifs.
*   `catalog` : Liste des produits finis vendables.
*   `suppliers` : Liste des fournisseurs.
*   `raw_materials` : Liste des matières premières achetables.

Ces données sont rafraîchies automatiquement en arrière-plan toutes les 2 minutes (si connexion réseau active) par appel asynchrone :
```javascript
fetch('/api/v1/clients?limit=500')
fetch('/api/v1/sellable-items')
```

### `pending_operations`
Stocke les opérations saisies en attente de synchronisation. Chaque enregistrement comprend :
*   `id` : Clé primaire auto-incrémentée.
*   `type` : Type d'opération (`create_sale`, `create_purchase`, `create_payment`).
*   `payload` : Dictionnaire contenant les arguments de l'opération (id client, lignes, montants, etc.).
*   `status` : État de synchronisation (`pending`, `synced`, `failed`).
*   `retry_count` : Nombre de tentatives d'envoi réseau.
*   `error` : Message d'erreur éventuel retourné par le serveur.

---

## 4. Protocole de Synchronisation

Le processus de synchronisation est déclenché :
1.  Au retour de la connexion réseau (événement `online`).
2.  Périodiquement toutes les 120 secondes via `setInterval`.

### Cinématique d'une requête de synchronisation

Pour chaque opération en attente, le script envoie une requête POST à l'API de synchronisation :

```http
POST /api/mobile/v1/offline/sync HTTP/1.1
Content-Type: application/json
X-CSRF-Token: [TOKEN_CSRF]
X-Idempotency-Key: fab-[OPERATION_LOCAL_ID]-[TIMESTAMP]

{
  "type": "create_sale",
  "payload": {
    "client_id": 42,
    "lines": [
      {
        "item_key": "finished:2",
        "quantity": 150.0,
        "unit": "kg",
        "unit_price": 1400.0
      }
    ],
    "notes": "Vente hors-ligne"
  }
}
```

### Sécurité et Idempotence du Serveur

Pour parer aux coupures de connexion réseau intermittentes où le serveur reçoit l'écriture mais le client ne reçoit pas la réponse de succès, le serveur implémente une **sécurité d'idempotence forte** :
1.  Le client génère une clé d'idempotence unique et reproductible : `fab-[op.id]-[timestamp]`.
2.  Cette clé est passée via l'en-tête `X-Idempotency-Key` (ou dans le payload JSON).
3.  Le serveur vérifie dans la table `idempotent_requests` si cette clé existe :
    *   **Si oui** : Il retourne immédiatement la réponse enregistrée lors du premier appel, évitant de dupliquer la transaction en base de données.
    *   **Si non** : Il traite la transaction en base (dans une transaction SQL), enregistre le résultat dans la table d'idempotence et retourne la réponse de succès.
4.  Si l'opération réussit (HTTP 200), le statut de l'opération locale dans IndexedDB passe à `synced`. En cas d'erreur métier irrécupérable (HTTP 422), elle passe à `failed`.

---

## 5. Comment Tester et Déboguer

### Simuler le mode Hors-ligne
1.  Ouvrez Google Chrome DevTools (`F12`).
2.  Allez dans l'onglet **Application** -> **Service Workers**.
3.  Cochez la case **Offline** pour couper le réseau virtuel pour le Service Worker.
4.  Allez dans l'onglet **Network** et passez le profil réseau à **Offline**.
5.  Saisissez une opération (par exemple, un versement client). Vous verrez le badge de la barre de navigation augmenter indiquant `1` opération en attente.

### Inspecter la Base de Données Locale
1.  Dans DevTools, allez sur **Application** -> **IndexedDB** -> `fabouanes-offline-db`.
2.  Cliquez sur `pending_operations` pour visualiser l'opération en attente de synchronisation et son payload JSON.

### Déclencher la Synchronisation
1.  Décochez la case **Offline** (dans Application et Network) pour rétablir la connexion.
2.  Le script détecte le changement d'état réseau et déclenche instantanément la synchronisation.
3.  Consultez la console JavaScript et l'onglet Network pour voir passer l'appel asynchrone à `/sync` et confirmer la réponse HTTP 200.
