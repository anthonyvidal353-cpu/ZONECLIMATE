@echo off
title Mise a jour ZoneClimate
cd /d "%~dp0"

echo ==========================================
echo    Mise a jour de ZoneClimate
echo ==========================================
echo.

rem --- Localiser git (systeme, sinon celui de GitHub Desktop) ---
set "GIT=git"
where git >nul 2>nul
if errorlevel 1 (
  for /d %%D in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do set "GIT=%%D\resources\app\git\cmd\git.exe"
)

echo [1/2] Recuperation de la derniere version...
"%GIT%" pull
if errorlevel 1 (
  echo.
  echo !! Impossible de recuperer la mise a jour.
  echo    Ouvrez GitHub Desktop et cliquez "Pull origin", puis relancez ce fichier.
  echo.
  pause
  exit /b 1
)

echo.
echo [2/2] Reconstruction et redemarrage de l'application...
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo !! Erreur au demarrage. Verifiez que Docker Desktop est bien lance (baleine).
  echo.
  pause
  exit /b 1
)

echo.
echo ==========================================
echo    Mise a jour terminee !
echo    Ouvrez : http://localhost:3000
echo ==========================================
echo.
pause
