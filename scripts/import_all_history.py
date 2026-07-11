import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

from app.core.async_db import get_async_sessionmaker, close_async_engine
from app.modules.clients.service import ClientService

async def main():
    parser = argparse.ArgumentParser(description="Importation en lot de l'historique complet des clients depuis des fichiers Excel.")
    parser.add_argument("folder", type=str, help="Dossier contenant les fichiers .xlsx des clients.")
    parser.add_argument("--force", action="store_true", help="Force la réimportation même si l'historique existe déjà.")
    args = parser.parse_args()

    # Vérification de DATABASE_URL
    if not os.environ.get("DATABASE_URL"):
        print("Erreur : La variable d'environnement DATABASE_URL doit être définie.", file=sys.stderr)
        sys.exit(1)

    folder_path = Path(args.folder)
    if not folder_path.is_dir():
        print(f"Erreur : Le chemin '{args.folder}' n'est pas un dossier valide.", file=sys.stderr)
        sys.exit(1)

    xlsx_files = list(folder_path.glob("*.xlsx")) + list(folder_path.glob("*.xlsm"))
    # Filtrer les fichiers temporaires Excel (commençant par ~$)
    xlsx_files = [f for f in xlsx_files if not f.name.startswith("~$")]

    if not xlsx_files:
        print(f"Aucun fichier Excel (.xlsx ou .xlsm) trouvé dans '{args.folder}'.")
        return

    print(f"Trouvé {len(xlsx_files)} fichier(s) Excel à traiter.")
    
    session_maker = get_async_sessionmaker()
    
    total_clients_traites = 0
    total_lignes_importees = 0
    erreurs = []

    for index, file_path in enumerate(xlsx_files, start=1):
        print(f"[{index}/{len(xlsx_files)}] Traitement de {file_path.name}...")
        try:
            # On ouvre une session pour chaque client pour bien isoler les transactions
            async with session_maker() as session:
                service = ClientService(session)
                res = await service.import_client_history_from_excel(
                    file_path=str(file_path),
                    client_id=None,
                    force_reimport=args.force or True
                )
                
                client_name = res["client_name"]
                nb_lignes = res["nb_lignes"]
                
                # Le premier solde est l'ouverture
                print(f"  ✅ {client_name} → {nb_lignes} lignes importées (Solde final: {res.get('solde_final', 0.0)})")
                total_clients_traites += 1
                total_lignes_importees += nb_lignes
        except Exception as e:
            print(f"  ❌ Erreur sur {file_path.name} : {e}", file=sys.stderr)
            erreurs.append((file_path.name, str(e)))

    print("\n" + "="*50)
    print("RÉSUMÉ DU TRAITEMENT BATCH")
    print("="*50)
    print(f"Clients traités avec succès : {total_clients_traites}")
    print(f"Total lignes d'historique importées : {total_lignes_importees}")
    print(f"Fichiers en erreur : {len(erreurs)}")
    if erreurs:
        print("\nDétail des erreurs :")
        for filename, err_msg in erreurs:
            print(f" - {filename} : {err_msg}")
    print("="*50)

    # Fermer proprement le moteur de base de données
    await close_async_engine()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
