@echo off
cd /d "C:\Users\user\AppData\Local\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_code\projects\sessions\busy-blissful-goodall\barberia-bot"
git push origin main
if %ERRORLEVEL% == 0 (
    echo Push exitoso!
) else (
    echo Error en el push. Intentando con la carpeta local...
    cd /d "C:\Users\user\Documents\barberIA"
    if exist "barberia-bot" (
        cd barberia-bot
        git push origin main
    ) else (
        echo No se encontro el repositorio local.
    )
)
pause
