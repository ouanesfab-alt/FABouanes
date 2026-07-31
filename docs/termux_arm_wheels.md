# Guide des Prérequis & Compilation ARM64 (Termux)

Ce document décrit la procédure de vérification du toolchain de compilation C/Rust et l'utilisation des paquets pré-compilés (wheels ARM64) pour le déploiement de **FABouanes** sous **Termux (Android)**.

---

## 1. Pourquoi des prérequis de compilation sont-ils nécessaires ?

L'application **FABouanes** s'appuie sur plusieurs bibliothèques Python hautes performances qui incluent des extensions natives en C ou en Rust :
- **asyncpg** : Driver PostgreSQL asynchrone codé en C / Cython.
- **pydantic-core** : Cœur de validation de Pydantic v2 écrit en Rust.
- **cryptography** : Module de cryptographie utilisant OpenSSL et des bindings C/Rust.
- **bcrypt** : Hachage sécurisé de mots de passe (dépend des liaisons C/Rust).

Sur les distributions Linux classiques ou Windows x86_64, PyPI fournit des wheels pré-compilés (`.whl`). En revanche, sur Android (environnements `aarch64` / `armv7l` sous Termux / bionic libc), la compilation depuis les sources à la première installation nécessite la présence de la chaîne d'outils C et Rust.

---

## 2. Verification automatique avec `check_termux_requirements.py`

Un script de contrôle automatique est fourni dans le répertoire `scripts/` :

```bash
python scripts/check_termux_requirements.py
```

### Rôle du script :
1. **Détection de l'environnement** : Identifie si l'application s'exécute dans Termux (via les variables d'environnement `TERMUX_VERSION` ou le chemin `$PREFIX`).
2. **Contrôle des outils CLI** : Vérifie l'existence dans le `PATH` de `clang`, `make`, `pkg-config`, `rustc`.
3. **Contrôle des en-têtes et bibliothèques C** : Vérifie la présence de `libffi` et `openssl` via `pkg-config` ou l'inspection des répertoires `$PREFIX/include` et `$PREFIX/lib`.
4. **Diagnostic clair** : En cas de manque, le script affiche la commande exacte à exécuter dans Termux et retourne un code de sortie d'erreur (`1`).

---

## 3. Installation manuelle du Toolchain Termux

Si le script signale des dépendances manquantes, installez le toolchain complet en une seule commande dans Termux :

```bash
pkg update -y
pkg install clang make pkg-config libffi openssl rust -y
```

---

## 4. Utilisation des Wheels ARM64 pré-compilés (Installation Rapide / Hors-Ligne)

Pour accélérer l'installation ou déployer FABouanes sans accès Internet direct :

1. Placer les fichiers `.whl` compatibles `aarch64` dans le dossier `wheels/` à la racine du projet.
2. Lancer l'installation pip en privilégiant les binaries du dossier `wheels/` :

```bash
pip install --find-links=wheels --prefer-binary -r requirements-termux.txt
```

---

## 5. Résolution des Problèmes Fréquents (Troubleshooting)

### Erreur `cargo: command not found` lors de l'installation de `pydantic-core` ou `cryptography`
- **Cause** : Le compilateur Rust n'est pas présent dans Termux.
- **Solution** : Exécuter `pkg install rust -y`.

### Erreur `ffi.h: No such file or directory` lors de la compilation de `cffi`
- **Cause** : Les en-têtes de développement `libffi` sont manquants.
- **Solution** : Exécuter `pkg install libffi -y`.

### Erreur `openssl/ssl.h: No such file or directory`
- **Cause** : Les en-têtes OpenSSL manquent.
- **Solution** : Exécuter `pkg install openssl -y`.

### Conflit de compilation `asyncpg` avec `pg_config`
- **Cause** : PostgreSQL et ses outils d'en-tête ne sont pas installés.
- **Solution** : Exécuter `pkg install postgresql -y`.
