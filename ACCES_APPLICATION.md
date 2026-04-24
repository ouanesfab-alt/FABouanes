# Acces Application - FABOuanes v2

## Demarrage standard (Windows)

1. `START_POSTGRES.bat` (si Docker).
2. `DOUBLE_CLIC_LANCER_TOUT.bat`.
3. Ouvre `http://127.0.0.1:5000`.

## Identifiants admin

- Compte admin cree au premier lancement uniquement.
- Pas de reset auto dans le lanceur.
- Reset manuel en secours: `RESET_ADMIN_SECOURS.bat`.

## Mode reseau / mobile

- Serveur lance en `0.0.0.0:5000`.
- Depuis mobile/poste client: `http://IP_DU_PC_SERVEUR:5000` (meme reseau Wi-Fi/LAN).

## API

- Swagger: `/api/docs`
- OpenAPI: `/api/openapi.json`
- API v1: `/api/v1/...`

## Configuration

- `.env` obligatoire (genere automatiquement depuis `.env.example` si absent).
- `DATABASE_URL` doit pointer vers PostgreSQL.

## Documentation complete

Voir [README.md](README.md).
