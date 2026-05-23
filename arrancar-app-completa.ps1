# Arranca la app de F1COMMENTS de forma robusta:
# 1) f1-dash (api 4001, realtime 4000) -> via Docker si disponible, sino via cargo.
# 2) backend F1COMMENTS (puerto 3006) -> SIEMPRE intenta arrancarse.
#
# Uso:
#   .\arrancar-app-completa.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$F1DashDir = Join-Path $ProjectRoot "F1 dash"
$BackendDir = Join-Path $ProjectRoot "backend"

function Resolve-Executable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName,
        [string[]]$FallbackPaths = @()
    )

    $cmd = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    foreach ($path in $FallbackPaths) {
        if ($path -and (Test-Path $path)) {
            return $path
        }
    }

    return $null
}

function Test-TcpPortOpen {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetHost,
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [int]$TimeoutMs = 800
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect($TargetHost, $Port, $null, $null)
        $ok = $result.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) {
            return $false
        }
        $client.EndConnect($result) | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-Port {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [int]$Retries = 20,
        [int]$SleepSeconds = 1
    )

    for ($i = 0; $i -lt $Retries; $i++) {
        if (Test-TcpPortOpen -TargetHost "127.0.0.1" -Port $Port) {
            Write-Host "OK: $Name en puerto $Port" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds $SleepSeconds
    }

    Write-Host "No responde $Name en puerto $Port." -ForegroundColor Yellow
    return $false
}

function Stop-PortListener {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    try {
        $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        if ($pids) {
            foreach ($processId in $pids) {
                try { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue } catch { }
            }
            Write-Host "Proceso(s) previo(s) en puerto $Port detenido(s): $($pids -join ',')" -ForegroundColor DarkYellow
        }
    } catch { }
}

function Test-DockerRunning {
    $dockerExe = Resolve-Executable -CommandName "docker"
    if (-not $dockerExe) { return $false }
    try {
        & $dockerExe info --format "{{.ServerVersion}}" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

if (-not (Test-Path $BackendDir)) {
    Write-Host "No se encuentra la carpeta 'backend' en la raiz del proyecto." -ForegroundColor Red
    exit 1
}

$pythonExe = Resolve-Executable -CommandName "python" -FallbackPaths @("py.exe")
if (-not $pythonExe) {
    Write-Host "No se encontro 'python' en PATH. Instala Python 3.10+ y vuelve a correr este script." -ForegroundColor Red
    exit 1
}

# Decidir como arrancar f1-dash: Docker > cargo > nada
$apiUp = $false
$realtimeUp = $false
$f1DashMethod = "none"

if (Test-DockerRunning -and (Test-Path (Join-Path $F1DashDir "compose.yaml"))) {
    $f1DashMethod = "docker"
} else {
    $cargoFallback = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
    $cargoExe = Resolve-Executable -CommandName "cargo" -FallbackPaths @($cargoFallback)
    if ($cargoExe -and (Test-Path $F1DashDir)) {
        $f1DashMethod = "cargo"
    }
}

switch ($f1DashMethod) {
    "docker" {
        Write-Host "f1-dash: usando Docker (api + realtime, sin web)" -ForegroundColor Cyan
        $dockerExe = Resolve-Executable -CommandName "docker"
        Push-Location $F1DashDir
        try {
            & $dockerExe compose up -d api realtime | Out-Null
        } finally {
            Pop-Location
        }
        Write-Host "Esperando containers de f1-dash..." -ForegroundColor DarkCyan
        $apiUp = Wait-Port -Name "f1-dash API" -Port 4001 -Retries 30 -SleepSeconds 2
        $realtimeUp = Wait-Port -Name "f1-dash Realtime" -Port 4000 -Retries 30 -SleepSeconds 2
        if (-not $apiUp -or -not $realtimeUp) {
            Write-Host "Docker arranco pero los puertos no responden. Revisa 'docker compose logs' en la carpeta 'F1 dash'." -ForegroundColor Yellow
        }
    }
    "cargo" {
        Write-Host "f1-dash: usando cargo (Docker no disponible)" -ForegroundColor Cyan
        $cargoFallback = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
        $cargoExe = Resolve-Executable -CommandName "cargo" -FallbackPaths @($cargoFallback)

        Write-Host "1/3 Iniciando f1-dash API (4001)..." -ForegroundColor Cyan
        Stop-PortListener -Port 4001
        $apiJob = Start-Process -FilePath $cargoExe -ArgumentList "run", "-p", "api" `
            -WorkingDirectory $F1DashDir -PassThru -WindowStyle Minimized

        Write-Host "2/3 Iniciando f1-dash Realtime (4000)..." -ForegroundColor Cyan
        Stop-PortListener -Port 4000
        $realtimeJob = Start-Process -FilePath $cargoExe -ArgumentList "run", "-p", "realtime" `
            -WorkingDirectory $F1DashDir -PassThru -WindowStyle Minimized

        Write-Host "Esperando servicios de f1-dash (primera compilacion puede tardar minutos)..." -ForegroundColor DarkCyan
        $apiUp = Wait-Port -Name "f1-dash API" -Port 4001 -Retries 60 -SleepSeconds 2
        $realtimeUp = Wait-Port -Name "f1-dash Realtime" -Port 4000 -Retries 60 -SleepSeconds 2

        if (-not $apiUp -or -not $realtimeUp) {
            Write-Host "f1-dash no arranco. Continuamos sin datos en vivo." -ForegroundColor Yellow
            Write-Host "Probablemente falta el linker MSVC (link.exe). Considera usar Docker o instalar Build Tools for Visual Studio." -ForegroundColor DarkYellow
        }
    }
    default {
        Write-Host "Aviso: no se encontro Docker ni cargo. f1-dash queda apagado." -ForegroundColor Yellow
        Write-Host "       El backend arrancara y mostrara el simulador de pilotos 2026 como fallback." -ForegroundColor DarkYellow
        Write-Host "       Para datos en vivo, instala Docker Desktop o Rust + Build Tools for Visual Studio." -ForegroundColor DarkYellow
    }
}

Write-Host "3/3 Iniciando F1COMMENTS backend (3006)..." -ForegroundColor Cyan
Stop-PortListener -Port 3006
$commentsJob = Start-Process -FilePath $pythonExe -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3006" `
    -WorkingDirectory $BackendDir -PassThru -WindowStyle Minimized

$commentsUp = Wait-Port -Name "F1COMMENTS" -Port 3006 -Retries 30 -SleepSeconds 1
if (-not $commentsUp) {
    Write-Host "F1COMMENTS no arranco correctamente. Revisa la ventana minimizada de Python/Uvicorn." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Listo. Estado de la app:" -ForegroundColor Green
if ($apiUp)      { Write-Host "  OK   f1-dash API:      http://127.0.0.1:4001" -ForegroundColor Green }
else             { Write-Host "  OFF  f1-dash API:      (usando simulador como fallback)" -ForegroundColor DarkYellow }
if ($realtimeUp) { Write-Host "  OK   f1-dash Realtime: http://127.0.0.1:4000" -ForegroundColor Green }
else             { Write-Host "  OFF  f1-dash Realtime: (usando simulador como fallback)" -ForegroundColor DarkYellow }
Write-Host       "  OK   F1COMMENTS:       http://127.0.0.1:3006/" -ForegroundColor Green
Write-Host ""
Write-Host "Abre en el navegador: http://127.0.0.1:3006/" -ForegroundColor Yellow

$pidParts = @()
if ($apiJob)      { $pidParts += "api=$($apiJob.Id)" }
if ($realtimeJob) { $pidParts += "realtime=$($realtimeJob.Id)" }
if ($commentsJob) { $pidParts += "comments=$($commentsJob.Id)" }
if ($pidParts.Count -gt 0) {
    Write-Host "PIDs: $($pidParts -join ', ')" -ForegroundColor DarkGray
}
