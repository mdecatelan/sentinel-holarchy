@echo off
chcp 65001 >nul
title Jumeau Numerique v2.0 - Bioraffinerie Urbaine de Clamart
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
echo ============================================================================
echo   Demarrage du Jumeau Numerique v2.0 (Bioraffinerie Holarchique de Clamart)
echo   Ouverture automatique sur : http://127.0.0.1:8080
echo   (Gardez cette fenetre ouverte tant que vous utilisez le site)
echo ============================================================================
start "" "http://127.0.0.1:8080"
python -m sentinel_holarchy.webapp.server
pause
