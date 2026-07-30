# 📱 Guide d'Installation Android "Zéro IT" pour FABOuanes

Ce guide explique comment installer **FABOuanes** sur le téléphone ou la tablette d'un utilisateur non-technique afin qu'il puisse utiliser l'application **en 1 seul clic**, sans jamais toucher à la ligne de commande Termux.

---

## 🛠️ Étape 1 : Installation de Termux & Termux-Widget (Une seule fois)

Sur le smartphone Android du client :

1. Téléchargez et installez l'APK **Termux** (depuis F-Droid ou GitHub Termux).
2. Téléchargez et installez l'APK **Termux:Widget** (depuis F-Droid).

---

## ⚡ Étape 2 : Installation Automatique de FABOuanes (En 1 ligne)

1. Ouvrez l'application **Termux**.
2. Copiez-collez cette seule commande puis appuyez sur **Entrée** :

```bash
curl -sL https://raw.githubusercontent.com/ouanesfab-alt/FABouanes/main/setup_termux.sh | bash
```

Le script installe automatiquement Python, PostgreSQL, télécharge l'application, configure la base de données et prépare les raccourcis Android.

---

## 🟢 Étape 3 : Ajouter l'icône 1-Clic sur l'écran d'accueil Android

1. Allez sur l'écran d'accueil du téléphone Android.
2. Restez appuyé sur un espace vide de l'écran -> Sélectionnez **Widgets**.
3. Choisissez **Termux:Widget** (ou *Termux Shortcuts*).
4. Placez le bouton **`🟢 DEMARRER FABOUANES`** sur l'écran d'accueil du client.

---

## 🚀 Utilisation au quotidien par le client ("Zéro IT") :

- **Pour utiliser FABOuanes** : Le client appuie simplement sur le bouton **`🟢 DEMARRER FABOUANES`** sur son écran d'accueil.
  - Le serveur s'allume automatiquement en arrière-plan.
  - L'application s'ouvre directement en plein écran.
- **Au démarrage du téléphone (Termux:Boot)** : Si le téléphone est éteint puis rallumé, le serveur démarre **tout seul automatiquement** sans aucune intervention.
