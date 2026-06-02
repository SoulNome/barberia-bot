@echo off
echo === Creando nueva instancia WhatsApp ===
powershell -command ^
  "$body = '{\"instanceName\":\"barberia2\",\"qrcode\":true,\"integration\":\"WHATSAPP-BAILEYS\"}'; " ^
  "$r = Invoke-WebRequest -Uri 'https://evolution-api-production-75a8.up.railway.app/instance/create' " ^
  "-Method POST -Headers @{'apikey'='barberia123';'Content-Type'='application/json'} -Body $body -UseBasicParsing; " ^
  "$r.Content | Out-File 'C:\Users\user\Documents\barberIA\Barberia Bot\nueva_instancia.txt' -Encoding UTF8"
echo.
echo Resultado guardado en nueva_instancia.txt
pause
