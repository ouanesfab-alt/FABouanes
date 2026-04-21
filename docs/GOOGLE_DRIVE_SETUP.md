# Sauvegarde Google Drive simple

FABOuanes n'utilise plus la connexion OAuth Google Cloud.

## Principe

1. Installe `Google Drive Desktop` sur le PC.
2. Choisis ou cree un dossier synchronise par Google Drive.
3. Dans `Parametres` > `Sauvegarde Google Drive`, colle le chemin local de ce dossier.
4. Enregistre la configuration.

Ensuite, FABOuanes copie automatiquement chaque sauvegarde dans ce dossier local. Google Drive Desktop se charge d'envoyer les fichiers dans le cloud.

## Exemple de dossier

- `C:\Users\massi\Google Drive\FABOuanes`
- `C:\Users\massi\Desktop\FAB\Backups`

## Verification

1. Clique sur `Creer une sauvegarde maintenant`.
2. Verifie qu'un fichier apparait dans `Jobs de sauvegarde`.
3. Verifie que le meme fichier existe dans ton dossier Google Drive local.

## Remarques

- Si aucun dossier n'est configure, les sauvegardes restent seulement en local.
- Aucune configuration `Client ID`, `Client Secret`, `callback` ou `Test users` n'est necessaire.
