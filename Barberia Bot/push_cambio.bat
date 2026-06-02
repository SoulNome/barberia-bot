@echo off
echo === Subiendo cambio a GitHub ===
echo.

:: Clonar el repo en temp
set TMPDIR=C:\Users\user\AppData\Local\Temp\barberia-push
if exist "%TMPDIR%" rmdir /s /q "%TMPDIR%"
git clone https://github.com/SoulNome/barberia-bot.git "%TMPDIR%"
if %ERRORLEVEL% neq 0 (
    echo ERROR: No se pudo clonar. Verifica tu conexion y credenciales de GitHub.
    pause
    exit /b 1
)

:: Copiar el archivo modificado desde la carpeta del proyecto
copy /y "C:\Users\user\Documents\barberIA\Barberia Bot\conversation_service.py" "%TMPDIR%\app\services\conversation_service.py"

cd /d "%TMPDIR%"
git add app/services/conversation_service.py
git commit -m "Saltar seleccion de barbero cuando la barberia tiene uno solo"
git push origin main

if %ERRORLEVEL% == 0 (
    echo.
    echo Listo! Cambio subido. Railway lo deployara automaticamente.
) else (
    echo ERROR en el push.
)

rmdir /s /q "%TMPDIR%"
pause
