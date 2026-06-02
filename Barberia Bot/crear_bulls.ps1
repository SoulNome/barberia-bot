# Crear instancia WhatsApp para BullsBarberClub
$url = "https://evolution-api-production-75a8.up.railway.app/instance/create"
$apikey = "barberia123"
$body = '{"instanceName":"BullsBarberClub","qrcode":true,"integration":"WHATSAPP-BAILEYS"}'

$log = @()
$log += "URL: $url"
$log += "APIKEY: $apikey"
$log += "BODY: $body"

try {
    $resp = Invoke-WebRequest -Uri $url -Method POST `
        -Headers @{"apikey" = $apikey; "Content-Type" = "application/json"} `
        -Body $body -UseBasicParsing -ErrorAction Stop

    $log += "STATUS: $($resp.StatusCode)"
    $log += "RESPONSE: $($resp.Content)"
    Write-Host "OK: $($resp.Content)" -ForegroundColor Green
} catch [System.Net.WebException] {
    $response = $_.Exception.Response
    if ($response) {
        $stream = $response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $errBody = $reader.ReadToEnd()
        $log += "HTTP ERROR $($response.StatusCode): $errBody"
        Write-Host "HTTP ERROR: $errBody" -ForegroundColor Red
    } else {
        $log += "CONNECTION ERROR: $($_.Exception.Message)"
        Write-Host "CONNECTION ERROR: $($_.Exception.Message)" -ForegroundColor Red
    }
} catch {
    $log += "GENERIC ERROR: $($_.Exception.GetType().Name): $($_.Exception.Message)"
    Write-Host "GENERIC ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

$log | Out-File "$PSScriptRoot\bulls_result.txt" -Encoding UTF8
Write-Host ""
Write-Host "Presiona Enter para salir..."
Read-Host
