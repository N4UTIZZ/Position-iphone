@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Position iPhone — outil local
cd /d "%~dp0"

echo.
echo ============================================
echo   Position iPhone — installation et lancement
echo ============================================
echo.

rem --- Trouver Python 3.11+ ---
set "PY_CMD="
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=py -3"
    )
)

if not defined PY_CMD (
    echo [ERREUR] Python 3.11 ou plus recent est introuvable.
    echo.
    echo 1. Telecharge Python ici : https://www.python.org/downloads/
    echo 2. Pendant l'installation, coche bien la case :
    echo    "Add python.exe to PATH"
    echo 3. Ferme cette fenetre, puis relance start.bat.
    echo.
    pause
    exit /b 1
)

echo [OK] Interpreteur Python : %PY_CMD%
%PY_CMD% --version
echo.

rem --- Environnement virtuel ---
if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement virtuel .venv ...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement virtuel.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERREUR] Impossible d'activer l'environnement virtuel.
    pause
    exit /b 1
)

echo Installation / mise a jour des dependances ...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] pip n'a pas pu etre mis a jour.
    pause
    exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] L'installation des dependances a echoue.
    echo Verifie ta connexion Internet et relance start.bat.
    pause
    exit /b 1
)
echo.

rem --- tunneld + regle pare-feu (port 5000, reseaux prives) en administrateur ---
echo Lancement de tunneld et ouverture du port 5000 dans le Pare-feu
echo (reseaux prives uniquement). Accepte la demande d'administrateur.
echo.
echo Si cette etape echoue : relance start.bat en tant qu'administrateur,
echo et definis le Wi-Fi du PC comme reseau "Prive"
echo (Parametres ^> Reseau et Internet ^> Wi-Fi ^> ton reseau ^> Prive).
echo.
powershell -NoProfile -Command "Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','%CD%\elevated-setup.ps1' -Verb RunAs -WorkingDirectory '%CD%'"
if errorlevel 1 (
    echo [INFO] La fenetre administrateur n'a pas pu s'ouvrir.
    echo Sur iOS 17.4 ou plus recent, la simulation peut quand meme fonctionner.
    echo Pour ouvrir l'interface depuis l'iPhone, le pare-feu doit autoriser le port 5000
    echo sur un reseau Prive. Relance start.bat et accepte la demande UAC.
    echo.
)

echo.
echo L'interface va s'ouvrir sur ce PC. Le lien et le QR code pour
echo l'iPhone s'affichent ci-dessous (meme Wi-Fi, reseau Prive).
echo Laisse cette fenetre ouverte tant que tu veux garder la fausse position
echo (surtout sur iOS 17 ou plus recent).
echo Pour quitter : ferme cette fenetre, ou appuie sur Ctrl+C.
echo.

python app.py
set "APP_EXIT=%ERRORLEVEL%"

echo.
if not "%APP_EXIT%"=="0" (
    echo [ERREUR] L'application s'est arretee avec le code %APP_EXIT%.
)
echo Tu peux fermer cette fenetre.
pause
endlocal
