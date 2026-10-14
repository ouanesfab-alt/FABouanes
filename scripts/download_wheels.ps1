# FABOuanes ERP — Script de téléchargement des dépendances hors-ligne
param(
    [string]$RequirementsFile = "requirements.txt",
    [string]$OutputDir = "wheels"
)

Write-Host "Téléchargement des wheels depuis $RequirementsFile vers $OutputDir..." -ForegroundColor Cyan
if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

python -m pip download -r $RequirementsFile -d $OutputDir --prefer-binary
Write-Host "Téléchargement terminé avec succès dans $OutputDir." -ForegroundColor Green
