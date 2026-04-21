# FABOuanes Android

Le wrapper Android est maintenant un client **leger et dedie** a trois actions:

1. enregistrer l'URL du serveur FABOuanes
2. scanner un QR qui contient cette URL
3. ouvrir l'application web complete dans la WebView mobile

## Principe

- le telephone ne garde qu'une petite configuration locale
- toute la logique metier reste sur le serveur FABOuanes
- l'interface Android ouvre ensuite l'application complete avec `mobile_shell=1`
- les donnees restent synchronisees avec le serveur en temps reel

## URL acceptees

Le QR peut contenir:

```text
http://192.168.1.50:5000
```

ou:

```text
fabouanes://server?url=http%3A%2F%2F192.168.1.50%3A5000
```

## Checklist reseau

- le PC et le telephone doivent etre sur le meme Wi-Fi
- le serveur FABOuanes doit etre demarre sur le PC
- le pare-feu Windows doit autoriser l'application, Python ou Waitress
- si besoin, reviens sur l'ecran de configuration avec `http://localhost/?setup=1`

## Build APK debug

Depuis la racine du projet:

```bat
deploy\android\BUILD_APK_DEBUG.bat
```

APK attendu:

```text
android_wrapper\android\app\build\outputs\apk\debug\app-debug.apk
```
