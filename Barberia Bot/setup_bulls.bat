@echo off
echo === Configurando webhook de BullsBarberClub ===

curl -s -X POST "https://evolution-api-production-75a8.up.railway.app/webhook/set/BullsBarberClub" ^
  -H "apikey: B6D711FCDE4D4FD5936544120E713976" ^
  -H "Content-Type: application/json" ^
  -d "{\"webhook\":{\"url\":\"https://web-production-81c2.up.railway.app/bot/webhook\",\"webhook_by_events\":false,\"webhook_base64\":false,\"events\":[\"MESSAGES_UPSERT\"]}}" ^
  -o "%~dp0webhook_result.txt"

echo Resultado webhook:
type "%~dp0webhook_result.txt"
echo.
pause
