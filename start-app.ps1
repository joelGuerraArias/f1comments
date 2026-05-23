# Arranca el motor de API (f1-dash) y luego F1 Comments.
# Uso: .\start-app.ps1
# Requisitos: Rust (cargo) en PATH para f1-dash; Python/uvicorn para F1 Comments.

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$F1DashDir = Join-Path $ProjectRoot "F1 dash"
$BackendDir = Join-Path $ProjectRoot "backend"

if (-not (Test-Path $F1DashDir)) {
    Write-Host "No se encuentra la carpeta 'F1 dash'. Colocala en la raiz del proyecto." -ForegroundColor Red
    exit 1
}

Write-Host "1/3 Iniciando f1-dash API (puerto 4001)..." -ForegroundColor Cyan
$apiJob = Start-Process -FilePath "cargo" -ArgumentList "run", "-p", "api" -WorkingDirectory $F1DashDir -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 2

Write-Host "2/3 Iniciando f1-dash Realtime (puerto 4000)..." -ForegroundColor Cyan
$realtimeJob = Start-Process -FilePath "cargo" -ArgumentList "run", "-p", "realtime" -WorkingDirectory $F1DashDir -PassThru -WindowStyle Minimized
Start-Sleep -Seconds 5

Write-Host "3/3 Iniciando F1 Comments (puerto 3006)..." -ForegroundColor Cyan
$commentsJob = Start-Process -FilePath "uvicorn" -ArgumentList "main:app", "--host", "0.0.0.0", "--port", "3006" -WorkingDirectory $BackendDir -PassThru -WindowStyle Minimized

Write-Host ""
Write-Host "Listo. Servicios en marcha:" -ForegroundColor Green
Write-Host "  - f1-dash API:      http://127.0.0.1:4001"
Write-Host "  - f1-dash Realtime: http://127.0.0.1:4000"
Write-Host "  - F1 Comments:      http://127.0.0.1:3006  <- Abre este en el navegador"
Write-Host ""
Write-Host "Para detener: cierra las ventanas minimizadas o mata los procesos (api/realtime/uvicorn)." -ForegroundColor Yellow
