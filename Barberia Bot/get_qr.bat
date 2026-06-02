@echo off
echo Generando QR fresco...
powershell -command "$r = Invoke-RestMethod -Uri 'https://evolution-api-production-75a8.up.railway.app/instance/connect/BullsBarberClub' -Headers @{'apikey'='B6D711FCDE4D4FD5936544120E713976'} -Method GET; $b64 = $r.base64; $bytes = [Convert]::FromBase64String($b64.Split(',')[1]); [IO.File]::WriteAllBytes('%~dp0BullsBarberClub_QR.png', $bytes); Write-Host 'Abriendo QR...'"
start "" "%~dp0BullsBarberClub_QR.png"
