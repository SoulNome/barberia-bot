@echo off
echo Buscando repositorio barberia-bot...

:: Buscar el repo en ubicaciones comunes
set REPO=""
for %%d in (
    "C:\Users\user\Documents\barberia-bot"
    "C:\Users\user\Documents\barberIA\barberia-bot"
    "C:\Users\user\Desktop\barberia-bot"
    "C:\barberia-bot"
) do (
    if exist "%%~d\.git" (
        set REPO=%%~d
        goto :found
    )
)

echo No se encontro el repositorio. Por favor abrilo en VS Code y aplica el patch manualmente.
pause
exit /b 1

:found
echo Repositorio encontrado en: %REPO%
cd /d %REPO%

:: Aplicar el patch
git apply "C:\Users\user\Documents\barberIA\Barberia Bot\0001-Saltar-selecci-n-de-barbero-cuando-la-barber-a-tiene.patch" 2>nul
if %ERRORLEVEL% == 0 (
    git add app/services/conversation_service.py
    git commit -m "Saltar seleccion de barbero cuando hay uno solo"
    git push origin main
    echo Listo! Cambio aplicado y subido a GitHub.
) else (
    echo El patch no aplico. Puede que ya este aplicado o hay conflictos.
    echo Revisa el archivo manualmente: app\services\conversation_service.py
)
pause
