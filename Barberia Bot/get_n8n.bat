@echo off
curl -L "https://raw.githubusercontent.com/Gergash/Master-Data-Pipeline---TecnoLabs/Gero/scripts/n8n_setup.md" -o "%~dp0n8n_setup.md"
if exist "%~dp0n8n_setup.md" (
    notepad "%~dp0n8n_setup.md"
) else (
    echo Error: no se pudo descargar el archivo
    pause
)
