@echo off
setlocal
cd /d "%~dp0"

title FABOuanes - Generer ZIP livrable

echo.
echo ========================================
echo   FABOuanes - ZIP livrable propre
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$root=(Get-Location).Path;" ^
  "$stamp=Get-Date -Format 'yyyyMMdd_HHmmss';" ^
  "$zip=Join-Path $root ('FABOuanes_v2_livrable_' + $stamp + '.zip');" ^
  "$stage=Join-Path $root '_zip_stage';" ^
  "if(Test-Path $stage){Remove-Item $stage -Recurse -Force};" ^
  "New-Item -Path $stage -ItemType Directory | Out-Null;" ^
  "$files=Get-ChildItem -Path $root -Recurse -File | Where-Object {" ^
  "  $full=$_.FullName;" ^
  "  $rel=$full.Substring($root.Length+1);" ^
  "  $norm=$rel -replace '\\\\','/';" ^
  "  $isEnvFile=($norm -match '(^|/)\\.env$') -or (($norm -match '(^|/)\\.env\\.') -and ($norm -ne '.env.example'));" ^
  "  if($norm -match '^\\.git/' -or $norm -match '^\\.venv/' -or $norm -match '^__pycache__/' -or $norm -match '/__pycache__/' -or $norm -match '^\\.pytest_cache/' -or $norm -match '/\\.pytest_cache/' -or $norm -match '^dist/' -or $norm -match '/dist/' -or $norm -match '^build/' -or $norm -match '/build/' -or $norm -match '^\\.mypy_cache/' -or $norm -match '^\\.ruff_cache/' -or $norm -match '^\\.idea/' -or $norm -match '^\\.vscode/' -or $norm -match '^android_wrapper/node_modules/' -or $norm -match '^android_wrapper/android/.gradle/' -or $norm -match '^android_wrapper/android/build/' -or $norm -match '^android_wrapper/android/app/build/' -or $norm -match '^android_wrapper/android/gradle/wrapper/gradle-wrapper\\.jar$' -or $norm -match '^tests/_runtime/' -or $norm -match '^tests/_runtime_debug/' -or $norm -match '^_zip_stage/' -or $norm -match '^server_stdout\\.log$' -or $norm -match '^server_stderr\\.log$' -or $norm -match '^FABOuanes_v2_livrable_.*\\.zip$' -or $isEnvFile){ return $false }" ^
  "  return $true" ^
  "};" ^
  "foreach($f in $files){$rel=$f.FullName.Substring($root.Length+1);$dest=Join-Path $stage $rel;$dir=Split-Path $dest -Parent;if(!(Test-Path $dir)){New-Item -Path $dir -ItemType Directory | Out-Null};Copy-Item -Path $f.FullName -Destination $dest -Force};" ^
  "if(Test-Path $zip){Remove-Item $zip -Force};" ^
  "Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force;" ^
  "Remove-Item $stage -Recurse -Force;" ^
  "Write-Host ('ZIP cree: ' + $zip);"

if errorlevel 1 (
  echo.
  echo ERREUR: generation ZIP echouee.
  pause
  exit /b 1
)

echo.
echo ZIP livrable genere avec succes.
echo.
pause
exit /b 0
