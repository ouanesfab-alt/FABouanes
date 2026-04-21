# 🔐 Guide d'Authentification GitHub

## Vos identifiants

**Username:** `ouanesfab-alt`

**URL du dépôt:** `https://github.com/ouanesfab-alt/FABouanes.git`

---

## ✅ Étape 1: Générer un Token GitHub

1. **Ouvrez le lien:** https://github.com/settings/tokens

2. **Cliquez:** "Generate new token" → "Generate new token (classic)"

3. **Remplissez les informations:**
   ```
   Note: FABouanes Push
   Expiration: 90 days (ou Plus selon votre préférence)
   ```

4. **Cochez le scope:**
   - ☑️ `repo` (accès complet aux dépôts)

5. **Cliquez:** "Generate token"

6. **⚠️ COPIER LE TOKEN IMMÉDIATEMENT**
   - Vous ne pourrez PAS le voir après!
   - Gardez-le dans un endroit sûr

---

## ✅ Étape 2: Utiliser le Token avec Git

Quand vous exécutez `PUSH_GITHUB.bat` ou `git push`, vous serez demandé:

```
Username: ouanesfab-alt
Password: [Collez votre token ici]
```

**NE PAS entrer votre mot de passe GitHub - entrer le TOKEN!**

---

## 📝 Exemple complet

```powershell
# Dans PowerShell
cd "c:\Users\ouane\Documents\FABOuanes_v1"

# Exécuter le script
.\PUSH_GITHUB.bat

# Quand demandé:
# Username: ouanesfab-alt
# Password: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (votre token)
```

---

## 🔧 Alternative: Configurer Git Credential Manager

Pour éviter d'entrer le token à chaque fois:

```powershell
# Dans PowerShell (admin)
git config --global credential.helper manager-core
```

Cela gardera votre token en sécurité.

---

## ❌ Dépannage

**Erreur: "Authentication failed"**
- Vérifiez que le token est valide
- Le token a peut-être expiré → générez-en un nouveau
- Assurez-vous que le scope `repo` est coché

**Erreur: "Repository not found"**
- Vérifiez l'URL: `https://github.com/ouanesfab-alt/FABouanes.git`
- Assurez-vous que le dépôt existe sur GitHub

**Erreur: "Permission denied"**
- Le token n'a pas les bonnes permissions
- Générez un nouveau token avec le scope `repo` complet

---

## ✨ Une fois le push réussi

Votre dépôt sera visible ici: **https://github.com/ouanesfab-alt/FABouanes**

Vous pouvez alors:
- Voir votre code en ligne
- Cloner le projet sur d'autres machines
- Collaborer avec d'autres développeurs
- Utiliser les outils GitHub (Issues, Actions, etc.)
