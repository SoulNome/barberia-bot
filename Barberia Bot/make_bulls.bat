@echo off
echo === Creando instancia BullsBarberClub ===

curl -s -X POST "https://evolution-api-production-75a8.up.railway.app/instance/create" ^
  -H "apikey: B6D711FCDE4D4FD5936544120E713976" ^
  -H "Content-Type: application/json" ^
  -d "{\"instanceName\":\"BullsBarberClub\",\"qrcode\":true,\"integration\":\"WHATSAPP-BAILEYS\"}" ^
  -o "%~dp0bulls_result2.txt"

echo Resultado:
type "%~dp0bulls_result2.txt"
echo.

:: Git push del cambio de codigo
echo === Git push ===
copy /y "%~dp0conversation_service.py" "C:\Users\user\Documents\barberIA\app\services\conversation_service.py"
cd /d "C:\Users\user\Documents\barberIA"
git add app\services\conversation_service.py
git commit -m "Saltar seleccion de barbero cuando la barberia tiene uno solo"
git push origin main

pause
