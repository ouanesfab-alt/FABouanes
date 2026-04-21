# Guide d'installation et push sur GitHub

## 1. INSTALLER GIT

Téléchargez et installez Git depuis: https://git-scm.com/download/win

**Options recommandées lors de l'installation:**
- Default editor: Use Visual Studio Code
- Git credential manager: Enable Git Credential Manager
- Line endings: Checkout as-is, commit as-is
- Terminal emulator: Use Windows' default console window

## 2. CONFIGURER GIT (première fois uniquement)

Ouvrez PowerShell et exécutez:
```powershell
git config --global user.name "Ouanes FAB"
git config --global user.email "votre-email@example.com"
```

## 3. GÉNÉRER UN TOKEN GITHUB (pour authentification HTTPS)

1. Allez sur: https://github.com/settings/tokens
2. Cliquez "Generate new token (classic)"
3. Donner un nom: "FABouanes Push"
4. Sélectionner les scopes: `repo` (accès complet aux repos privés/publics)
5. Générer et **COPIER LE TOKEN** (vous ne pourrez pas le voir après!)

## 4. LANCER LE PUSH

Double-cliquez sur `PUSH_GITHUB.bat` ou exécutez dans PowerShell:
```powershell
cd "c:\Users\ouane\Documents\FABOuanes_v1"
.\PUSH_GITHUB.bat
```

Quand demandé:
- URL du dépôt: `https://github.com/ouanesfab-alt/FABouanes.git`
- Username: `ouanesfab-alt`
- Password/Token: **Collez votre token GitHub** (pas votre mot de passe!)

---

**Le dépôt GitHub existe déjà? Vérifiez:** https://github.com/ouanesfab-alt/FABouanes
