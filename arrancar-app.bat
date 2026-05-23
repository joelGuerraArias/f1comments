@echo off
REM ===========================================================
REM  F1COMMENTS - Arranque automatico via Docker
REM ===========================================================
REM  1) Verifica que Docker este corriendo.
REM  2) Levanta f1-dash (api + realtime) con Docker Compose.
REM  3) Espera a que los puertos 4000 y 4001 esten arriba.
REM  4) Libera el puerto 3006 si esta ocupado.
REM  5) Arranca el backend F1COMMENTS en una ventana nueva.
REM  6) Abre el navegador en http://127.0.0.1:3006/
REM ===========================================================

setlocal EnableDelayedExpansion

REM Trabajar siempre desde la carpeta del .bat (raiz del proyecto)
cd /d "%~dp0"

echo.
echo ===========================================================
echo  F1COMMENTS - arrancando todo via Docker
echo ===========================================================
echo.

REM --- 1) Verificar Docker ----------------------------------
echo [1/5] Verificando Docker...
where docker >NUL 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Docker no esta instalado o no esta en PATH.
    echo Instala Docker Desktop desde https://www.docker.com/products/docker-desktop/
    echo y vuelve a correr este .bat.
    echo.
    pause
    exit /b 1
)

docker info >NUL 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Docker Desktop no esta corriendo.
    echo Abre Docker Desktop, espera a que arranque, y vuelve a correr este .bat.
    echo.
    pause
    exit /b 1
)
echo       OK: Docker activo.

REM --- 2) Verificar Python ----------------------------------
echo [2/5] Verificando Python...
where python >NUL 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python no esta en PATH. Instala Python 3.10+ y vuelve a correr este .bat.
    echo.
    pause
    exit /b 1
)
echo       OK: Python disponible.

REM --- 3) Levantar f1-dash con Docker -----------------------
echo [3/5] Levantando f1-dash (api + realtime) via Docker...
pushd "F1 dash"
docker compose up -d api realtime
if errorlevel 1 (
    echo.
    echo ERROR: Docker Compose fallo al levantar f1-dash.
    popd
    pause
    exit /b 1
)
popd

REM --- 4) Esperar a que f1-dash este listo ------------------
echo       Esperando a que f1-dash responda en puertos 4000 y 4001...
set /a tries=0
:waitdash
set /a tries+=1
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient;try{$r=$c.BeginConnect('127.0.0.1',4001,$null,$null);if(-not $r.AsyncWaitHandle.WaitOne(800,$false)){exit 1};$c.EndConnect($r);exit 0}catch{exit 1}finally{$c.Close()}" >NUL 2>&1
if errorlevel 1 (
    if !tries! geq 30 (
        echo.
        echo AVISO: f1-dash API ^(4001^) no respondio a tiempo. El backend usara el simulador como fallback.
        goto skipwait
    )
    timeout /t 1 /nobreak >NUL
    goto waitdash
)
echo       OK: f1-dash listo.

:skipwait

REM --- 5) Liberar puerto 3006 si esta ocupado ---------------
echo [4/5] Preparando puerto 3006 del backend...
powershell -NoProfile -Command "$pids = Get-NetTCPConnection -LocalPort 3006 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($pids) { $pids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }" >NUL 2>&1

REM --- 6) Arrancar backend en ventana nueva -----------------
echo [5/5] Arrancando backend F1COMMENTS (ventana nueva)...
start "F1COMMENTS backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn main:app --host 0.0.0.0 --port 3006"

REM Esperar a que el backend este arriba antes de abrir el navegador
set /a tries=0
:waitback
set /a tries+=1
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient;try{$r=$c.BeginConnect('127.0.0.1',3006,$null,$null);if(-not $r.AsyncWaitHandle.WaitOne(800,$false)){exit 1};$c.EndConnect($r);exit 0}catch{exit 1}finally{$c.Close()}" >NUL 2>&1
if errorlevel 1 (
    if !tries! geq 20 (
        echo.
        echo AVISO: el backend no respondio a tiempo. Revisa la ventana "F1COMMENTS backend".
        goto opened
    )
    timeout /t 1 /nobreak >NUL
    goto waitback
)

start "" "http://127.0.0.1:3006/"

:opened
echo.
echo ===========================================================
echo  Listo. F1COMMENTS arriba en http://127.0.0.1:3006/
echo.
echo   - f1-dash API:      http://127.0.0.1:4001  (Docker)
echo   - f1-dash Realtime: http://127.0.0.1:4000  (Docker)
echo   - F1COMMENTS:       http://127.0.0.1:3006/
echo.
echo  Para detener:
echo    - Cierra la ventana "F1COMMENTS backend".
echo    - Detener Docker: cd "F1 dash" ^&^& docker compose down
echo ===========================================================
echo.

endlocal
exit /b 0
