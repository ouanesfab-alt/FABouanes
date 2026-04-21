@echo off
setlocal
cd /d %~dp0\..\..

echo.
echo  Preparation du wrapper Android FABOuanes...
echo.

if not exist android_wrapper\node_modules (
  echo  Installation des dependances npm...
  cd /d android_wrapper
  call npm install
  if errorlevel 1 exit /b 1
  cd /d ..
)

cd /d android_wrapper

if not exist android (
  echo  Creation du projet Android Capacitor...
  call npx cap add android
  if errorlevel 1 exit /b 1
)

if not exist android\local.properties (
  for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('LocalApplicationData')"`) do set "FAB_LOCALAPPDATA=%%I"
  set "FAB_ANDROID_SDK=%FAB_LOCALAPPDATA%\Android\Sdk"
  if exist "%FAB_ANDROID_SDK%" (
    echo  Configuration du SDK Android...
    powershell -NoProfile -Command "$sdk = '%FAB_ANDROID_SDK%'; Set-Content -Path 'android\\local.properties' -Value ('sdk.dir=' + $sdk.Replace('\\','\\\\'))"
  )
)

echo  Synchronisation Android...
call npx cap sync android
if errorlevel 1 exit /b 1

echo  Build de l'APK debug...
cd /d android
call gradlew.bat assembleDebug
if errorlevel 1 exit /b 1

echo.
echo  APK genere :
echo  %cd%\app\build\outputs\apk\debug\app-debug.apk
echo.
endlocal
