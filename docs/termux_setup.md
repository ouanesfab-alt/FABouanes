# Guide de Configuration Termux pour FABOuanes

Ce guide explique comment faire fonctionner **FABOuanes** en mode client-serveur directement depuis un smartphone Android en utilisant **Termux**.

Grâce au moteur léger **SQLite**, il n'est plus nécessaire d'installer ou de configurer un serveur de base de données externe.

---

## Mode 1 : Smartphone en tant que Client (Recommandé)

Si votre serveur FABOuanes tourne sur votre PC principal (Windows) :

1. Connectez votre PC et votre smartphone au **même réseau Wi-Fi**.
2. Lancez FABOuanes sur votre PC. La console affichera les adresses d'accès, par exemple :
   - `PC Local : http://127.0.0.1:5000`
   - `Mobile / Réseau local : http://192.168.1.50:5000`
3. Ouvrez le navigateur internet de votre smartphone (Chrome, Safari, Firefox).
4. Saisissez l'adresse mobile (ex. `http://192.168.1.50:5000`).
5. **Astuce PWA** : Dans le menu de votre navigateur sur mobile, cliquez sur **"Ajouter à l'écran d'accueil"** pour installer FABOuanes comme une application native autonome.

---

## Mode 2 : Smartphone en tant que Serveur Autonome (via Termux)

Pour héberger le serveur FABOuanes directement sur votre smartphone :

### 1. Installation de Termux
> [!IMPORTANT]
> Téléchargez et installez **Termux** depuis [F-Droid](https://f-droid.org/packages/com.termux/).

### 2. Mise à jour et Installation des paquets requis
Ouvrez Termux sur votre smartphone et exécutez :

```bash
# Mettre à jour les paquets
pkg update && pkg upgrade -y

# Installer Git, Python et les outils de compilation de base
pkg install git python make clang -y
```

### 3. Récupération et installation de FABOuanes
```bash
# Cloner le projet
git clone https://github.com/ouanesfab-alt/FABouanes.git
cd FABouanes

# Installer les dépendances Python
pip install -r requirements.txt
```

### 4. Configuration
Créez le fichier de configuration `.env` :

```bash
nano .env
```
Exemple de configuration minimale :
```env
FASTAPI_ENV=production
SECRET_KEY=générez_une_clé_secrète_aléatoire_et_forte
FAB_HOST=0.0.0.0
FAB_PORT=5000
FAB_DESKTOP=0
```
*(Remarque : `DATABASE_URL` n'a pas besoin d'être renseignée — SQLite créera automatiquement la base locale `fabouanes.db`).*

### 5. Démarrage
```bash
python launcher.py --server-only
```

### 6. Accès à l'application
- **Depuis le smartphone lui-même** : `http://localhost:5000`
- **Depuis d'autres appareils** sur le même Wi-Fi : `http://<IP_DU_TELEPHONE>:5000`

---

## ⚡ Raccourci de démarrage dans Termux

```bash
nano ~/start_fab.sh
```
Contenu du script :
```bash
#!/data/data/com.termux/files/usr/bin/bash
cd ~/FABouanes
python launcher.py --server-only
```
Rendre le script exécutable :
```bash
chmod +x ~/start_fab.sh
```
Pour lancer l'application à l'avenir :
```bash
./start_fab.sh
```

---

## 🚨 Réglages Batterie Android (Wake Lock)

- **Activer le Wake Lock** : Dans la barre de notifications Android, sur la notification Termux, cliquez sur **"Acquire WakeLock"**.
- **Désactiver l'optimisation batterie** : Dans Paramètres Android -> Applications -> Termux -> Batterie, sélectionnez **"Non restreinte"**.
