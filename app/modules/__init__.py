"""
Feature Modules — Packages métier auto-découverts par le registry.

Chaque sous-dossier ici est un module autonome. Pour créer un nouveau module :

1. Créer un dossier : app/modules/mon_module/
2. Ajouter un __init__.py qui appelle register()
3. Ajouter schema.py, repository.py, service.py, web.py, api.py selon les besoins
4. C'est tout — le module est automatiquement découvert au démarrage.
"""
