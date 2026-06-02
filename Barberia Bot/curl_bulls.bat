@echo off
curl -v -X POST "https://evolution-api-production-75a8.up.railway.app/instance/create" ^
  -H "apikey: barberia123" ^
  -H "Content-Type: application/json" ^
  -d "{\"instanceName\":\"BullsBarberClub\",\"qrcode\":true,\"integration\":\"WHATSAPP-BAILEYS\"}" ^
  > "%~dp0bulls_curl.txt" 2>&1
echo.
echo Resultado en bulls_curl.txt
pause
