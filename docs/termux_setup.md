# Guide de Configuration Termux pour FABOuanes

Ce guide explique comment faire fonctionner **FABOuanes** en mode client-serveur directement depuis un smartphone Android en utilisant **Termux**.

Il existe deux manières d'utiliser l'application sur smartphone :
1. **Smartphone en tant que Client** (le serveur tourne sur votre PC) : Le plus simple, ne nécessite aucune installation sur le téléphone.
2. **Smartphone en tant que Serveur** (le serveur et la base de données tournent sur le téléphone) : Idéal pour un usage 100% mobile et autonome.

---

## Mode 1 : Smartphone en tant que Client (Recommandé)

Si votre serveur FABOuanes tourne sur votre PC principal (Windows) :

1. Connectez votre PC et votre smartphone au **même réseau Wi-Fi**.
2. Lancez FABOuanes sur votre PC. La console affichera les adresses d'accès, par exemple :
   - `PC Local : http://127.0.0.1:5000`
   - `Mobile / Réseau local : http://192.168.1.50:5000`
3. Ouvrez le navigateur internet de votre smartphone (Chrome, Safari, Firefox).
4. Saisissez l'adresse mobile (ex. `http://192.168.1.50:5000`).
5. **Astuce PWA** : Dans le menu de votre navigateur sur mobile, cliquez sur **"Ajouter à l'écran d'accueil"** pour installer FABOuanes comme une application native autonome (icône sur le bureau, mode plein écran, performance optimisée).

---

## Mode 2 : Smartphone en tant que Serveur (via Termux)

Pour héberger la base de données PostgreSQL et le serveur FABOuanes directement sur votre smartphone :

### 1. Installation de Termux
> [!IMPORTANT]
> Téléchargez et installez **Termux** depuis [F-Droid](https://f-droid.org/packages/com.termux/) (la version du Google Play Store est obsolète et ne reçoit plus de mises à jour).

### 2. Mise à jour et Installation des paquets requis
Ouvrez Termux sur votre smartphone et exécutez les commandes suivantes :

```bash
# Mettre à jour les paquets
pkg update && pkg upgrade -y

# Installer Git, Python, PostgreSQL et les dépendances système de compilation
pkg install git python postgresql make clang -y
```

### 3. Configuration et Démarrage de PostgreSQL dans Termux
Initialisez la base de données locale dans l'espace de stockage de Termux :

```bash
# Initialiser le répertoire de données
initdb -D $PREFIX/var/lib/postgresql

# Démarrer le service PostgreSQL
pg_ctl -D $PREFIX/var/lib/postgresql start

# Créer la base de données et l'utilisateur par défaut
createdb fabouanes
createuser -s postgres
```

### 4. Récupération et installation de FABOuanes
Clonez votre dépôt de code et installez les paquets Python requis :

```bash
# Cloner le projet (remplacez par votre URL si nécessaire)
git clone https://github.com/ouanesfab-alt/FABouanes.git
cd FABouanes

# Installer les dépendances Python
pip install -r requirements.txt
```

### 5. Configuration des variables d'environnement
Créez le fichier de configuration `.env` dans le dossier `FABouanes` :

```bash
nano .env
```
Collez la configuration suivante (adaptez selon vos besoins) :
```env
FASTAPI_ENV=production
DATABASE_URL=postgresql://postgres@localhost:5432/fabouanes
SECRET_KEY=générez_une_clé_secrète_aléatoire_et_forte
FAB_HOST=0.0.0.0
FAB_PORT=5000
FAB_DESKTOP=0
```
*(Appuyez sur `Ctrl+O` puis `Entrée` pour sauvegarder, et `Ctrl+X` pour quitter nano).*

### 6. Initialisation et Lancement
Lancez la phase de bootstrap pour créer les tables et index :
```bash
python launcher.py --bootstrap-only
```

Puis démarrez le serveur :
```bash
python launcher.py --server-only
```

### 7. Accès à l'application
- **Depuis le smartphone lui-même** : Ouvrez votre navigateur et accédez à `http://localhost:5000`.
- **Depuis d'autres appareils** (PC, tablettes, autres téléphones sur le même Wi-Fi) : 
  1. Récupérez l'adresse IP locale du smartphone dans Termux en exécutant `ifconfig` (cherchez la ligne `inet` sous `wlan0`, ex: `192.168.1.15`).
  2. Sur les autres appareils, connectez-vous à `http://192.168.1.15:5000`.

---

## ⚡ Automatisation du démarrage (Script rapide pour Termux)
Pour ne pas retaper toutes les commandes à chaque fois, vous pouvez créer un raccourci de lancement dans Termux :

```bash
nano ~/start_fab.sh
```
Ajoutez-y :
```bash
#!/data/data/com.termux/files/usr/bin/bash
pg_ctl -D $PREFIX/var/lib/postgresql start
cd ~/FABouanes
python launcher.py --server-only
```
Rendez le script exécutable :
```bash
chmod +x ~/start_fab.sh
```
Pour lancer l'application à l'avenir, ouvrez Termux et tapez simplement :
```bash
./start_fab.sh
```

---

## 🚨 Pièges & Astuces indispensables sous Android (Termux)

Pour que FABOuanes fonctionne de manière fluide et stable 24h/24 en mode serveur sur votre smartphone, appliquez ces réglages :

### 1. Empêcher Android de couper le serveur (Wake Lock)
Par défaut, Android met en veille les applications en arrière-plan pour économiser la batterie, ce qui couperait le serveur de base de données et l'application.
- **Activer le Wake Lock** : Faites glisser votre barre de notifications Android vers le bas, trouvez la notification **Termux**, et cliquez sur **"Acquire WakeLock"**. Cela force le processeur du téléphone à rester éveillé.
- **Désactiver l'optimisation de la batterie** : Allez dans les paramètres d'Android -> Applications -> Termux -> Batterie, et sélectionnez **"Non restreinte"** (ou désactivez l'optimisation).

### 2. Le problème des utilisateurs sous Android (`whoami`)
Android n'a pas d'utilisateur système `postgres` par défaut. Termux s'exécute sous un identifiant utilisateur générique (ex: `u0_a123`).
Si vous rencontrez une erreur de connexion à la base de données :
1. Tapez `whoami` dans Termux pour connaître votre identifiant.
2. Si vous n'utilisez pas l'URL de connexion avec l'utilisateur `postgres`, vous pouvez modifier le fichier `.env` pour utiliser cet utilisateur système Termux :
   ```env
   DATABASE_URL=postgresql://u0_a123@localhost:5432/fabouanes
   ```
   *(Remplacez `u0_a123` par le résultat exact de la commande `whoami`).*

### 3. Connaître l'IP locale de votre smartphone facilement
Si la commande `ifconfig` renvoie trop d'informations, tapez simplement cette commande dans Termux pour voir l'adresse IP à utiliser pour connecter vos autres appareils :
```bash
ip route get 1.1.1.1 | awk '{print $7}'
```

