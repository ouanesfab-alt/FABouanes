# Guide d'Installation de FABOuanes sur Termux (Android)

Ce guide explique comment installer et faire tourner le serveur **FABOuanes** sur un smartphone Android à l'aide de **Termux**, pour l'utiliser en mode Serveur/Client (soit sur le même téléphone, soit sur d'autres appareils connectés au même réseau Wi-Fi).

---

## 📋 Prérequis sur Android

1. **Installer Termux** :
   > [!IMPORTANT]
   > N'installez **PAS** Termux depuis le Google Play Store (version obsolète). Téléchargez-le depuis **F-Droid** ou directement depuis son dépôt officiel **GitHub Releases**.
   - [Télécharger Termux sur F-Droid](https://f-droid.org/fr/packages/com.termux/)

2. **Accès réseau** :
   - Assurez-vous d'être connecté sur le même réseau Wi-Fi si vous souhaitez connecter d'autres machines (PC, tablettes, autres téléphones) au serveur de votre smartphone.

---

## 🛠️ Étape 1 : Préparation de l'environnement Termux

Ouvrez Termux sur votre smartphone et exécutez les commandes suivantes pour mettre à jour les paquets et installer les dépendances système :

```bash
# 1. Mise à jour des dépôts et paquets système
pkg update && pkg upgrade -y

# 2. Installation de Python, Git, PostgreSQL et des outils de compilation
pkg install python git postgresql build-essential -y
```

---

## 🗄️ Étape 2 : Configuration et Lancement de PostgreSQL

FABOuanes nécessite une base de données PostgreSQL active. Configurez-la localement dans Termux :

```bash
# 1. Initialiser le stockage de la base de données
initdb -D $PREFIX/var/lib/postgresql

# 2. Démarrer le service PostgreSQL en arrière-plan
pg_ctl -D $PREFIX/var/lib/postgresql start

# 3. Créer la base de données de l'application
createdb fabouanes
```

> [!TIP]
> Si vous redémarrez Termux ou votre smartphone plus tard, vous n'aurez qu'à exécuter la commande de démarrage : `pg_ctl -D $PREFIX/var/lib/postgresql start`.

---

## 📥 Étape 3 : Téléchargement du projet et Installation de FABOuanes

```bash
# 1. Cloner le dépôt GitHub officiel
git clone https://github.com/ouanesfab-alt/FABouanes.git
cd FABouanes

# 2. Créer un environnement virtuel Python
python -m venv .venv
source .venv/bin/activate

# 3. Mettre à jour pip et installer les bibliothèques requises
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ⚙️ Étape 4 : Configuration des Variables d'Environnement

Créez le fichier de configuration `.env` :

```bash
nano .env
```

Ajoutez-y les lignes suivantes :
```ini
FASTAPI_ENV=production
DATABASE_URL=postgresql://localhost:5432/fabouanes
SECRET_KEY=generez_une_cle_securisee_ici_ou_laissez_vide_pour_creation_auto
FAB_HOST=0.0.0.0
FAB_PORT=5000
```
*(Appuyez sur `Ctrl+O` puis `Entrée` pour sauvegarder, et `Ctrl+X` pour quitter nano).*

---

## 🚀 Étape 5 : Lancement et Utilisation

```bash
# 1. Préparer les tables de la base de données (Bootstrap)
python launcher.py --bootstrap-only

# 2. Lancer le serveur web en mode "serveur uniquement"
python launcher.py --server-only
```

L'application démarre et affiche ses adresses d'accès :
```text
===========================================================
           FABOUANES - ACCES RESEAU & MOBILE               
===========================================================
  PC Local : http://127.0.0.1:5000
  Mobile   : http://192.168.1.50:5000
```

---

## 📱 Accéder à l'Application (Mode Client)

- **Sur le même smartphone** : Ouvrez votre navigateur internet (Chrome, Firefox) et rendez-vous sur `http://127.0.0.1:5000`.
- **Depuis d'autres appareils du réseau** : Utilisez l'adresse IP locale affichée par le terminal Termux (ex. `http://192.168.1.50:5000`).
