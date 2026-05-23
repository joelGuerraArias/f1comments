# START - F1COMMENTS

Guia para arrancar la app y entender que cambios se aplicaron.

---

## 1. Arranque rapido

### Opcion 1 (recomendada): doble click en `arrancar-app.bat`

Doble click sobre `arrancar-app.bat` en la raiz del proyecto. El bat:
- Verifica que Docker este corriendo (sino, te avisa y para).
- Levanta f1-dash (api + realtime) via Docker.
- Espera a que respondan los puertos 4000/4001.
- Libera el puerto 3006.
- Arranca el backend en una ventana nueva.
- Abre tu navegador en `http://127.0.0.1:3006/`.

Para detener:
- Cierra la ventana "F1COMMENTS backend".
- Detener Docker: `cd "F1 dash"` y luego `docker compose down`.

### Opcion 2: PowerShell

```powershell
.\arrancar-app-completa.ps1
```

Este es **tolerante a fallos**: si Docker o f1-dash no estan, igual levanta el backend y muestra el simulador 2026.

URL final: **http://127.0.0.1:3006/**

> Si ves "Cargando..." haz `Ctrl + F5`.

---

## 2. Como se levanta f1-dash (live data)

`f1-dash` es el proyecto Rust que da datos en vivo. Hay **dos formas** de correrlo:

### Opcion A: Docker (recomendado, mas facil)

Si tienes Docker Desktop, **no necesitas Rust ni Visual C++**:

```powershell
cd "F1 dash"
docker compose up -d api realtime
```

Esto descarga imagenes oficiales de `ghcr.io/slowlydev/f1-dash-*` y expone:
- API en `http://127.0.0.1:4001`
- Realtime en `http://127.0.0.1:4000`

> **Importante:** levantamos solo `api` y `realtime`, no el servicio `web` (Next.js en 3000). Ese `web` no lo necesitamos y suele chocar con otros procesos en el puerto 3000.

Para detenerlo:

```powershell
cd "F1 dash"
docker compose down
```

### Opcion B: Rust nativo (mas pesado)

Si prefieres compilar:

1. Instalar Rust: https://rustup.rs/
2. Instalar **Build Tools for Visual Studio** con "Desktop development with C++" (para tener `link.exe`).
3. Cerrar y abrir terminal nueva.
4. Verificar:
   ```powershell
   cargo --version
   where.exe link
   ```
5. El script `arrancar-app-completa.ps1` detectara `cargo` y lo usara automaticamente.

> La primera compilacion de f1-dash con cargo baja muchas dependencias y tarda varios minutos.

### Sin nada de lo anterior

Si no quieres ni Docker ni Rust, **no pasa nada**: el backend incluye un **simulador con los 22 pilotos 2026** que se activa automaticamente como fallback cuando f1-dash no responde. Asi ves la UI completa para desarrollo.

---

## 3. URLs

- **F1COMMENTS (la app):** `http://127.0.0.1:3006/`
- f1-dash API (opcional): `http://127.0.0.1:4001`
- f1-dash Realtime (opcional): `http://127.0.0.1:4000`

No usar `http://localhost:3000`: ese es el dashboard Next.js de `F1 dash`, no es esta app.

---

## 4. Que hace el script `arrancar-app-completa.ps1`

| Orden | Servicio              | Puerto | Como lo arranca                              | Si falla                   |
|-------|----------------------|--------|----------------------------------------------|----------------------------|
| 1     | f1-dash API           | 4001   | Docker compose si disponible, sino cargo     | Sigue sin live data        |
| 2     | f1-dash Realtime      | 4000   | Docker compose si disponible, sino cargo     | Sigue sin live data        |
| 3     | F1COMMENTS (backend)  | 3006   | `python -m uvicorn`                          | El script aborta           |

Tambien:
- Libera puertos `3006/4000/4001` antes de arrancar (mata procesos previos).
- Detecta Docker primero, luego `cargo`, luego nada.
- Imprime al final el estado de cada servicio con OK/OFF y la URL.

---

## 5. Cambios recientes (registro)

### 5.1 Frontend: bundle precompilado
- Se cambio `frontend/index.html` para no depender de Babel en runtime.
- Se genero `frontend/app.bundle.js` con esbuild.
- **Beneficio:** carga instantanea, no depende de CDN de Babel.

Si editas `frontend/app.jsx`, regenera el bundle:

```powershell
npx --yes esbuild "frontend/app.jsx" --bundle --platform=browser --format=iife --outfile="frontend/app.bundle.js"
```

### 5.2 Backend: simulador como fallback
- `backend/main.py` ahora usa `RaceSimulator` (parrilla 2026) si f1-dash no devuelve datos.
- Asi el dashboard nunca esta vacio.
- Cuando f1-dash vuelve, automaticamente toma sus datos.

### 5.3 Script de arranque tolerante
- `arrancar-app-completa.ps1` ya no aborta si falta `cargo`.
- Detecta Docker o cargo o ninguno y sigue arrancando el backend siempre.

---

## 6. Variables de entorno (`backend/.env`)

```
F1_DASH_REALTIME_URL=http://localhost:4000
F1_DASH_API_URL=http://localhost:4001
DEEPSEEK_API_KEY=...        # Comentarios IA (Mark / Maria)
OPENAI_API_KEY=...          # Speech (TTS) + Whisper (mic)
OPENAI_SPEECH_MODEL=...     # opcional, default gpt-realtime-2
```

**Seguridad:**
- `backend/.env` **no debe subirse al repo** (anadelo a `.gitignore`).
- Si una key se expuso, **rotala** desde el panel del proveedor.

---

## 7. Troubleshooting

| Sintoma                                       | Causa probable                              | Solucion                                                    |
|-----------------------------------------------|---------------------------------------------|-------------------------------------------------------------|
| Pantalla "Cargando..." no avanza               | Bundle viejo cacheado en navegador          | `Ctrl + F5` para forzar recarga sin cache                   |
| Dashboard sin pilotos                          | f1-dash apagado y simulador no se cargo     | Reinicia backend; o `cd "F1 dash" && docker compose up -d api realtime` |
| `Cannot start Docker Compose ... port 3000`    | Otro proceso ocupa 3000 (Next.js, etc.)     | Solo arranca api y realtime: `docker compose up -d api realtime` |
| `cargo: linker 'link.exe' not found`           | Falta Build Tools for Visual Studio (C++)   | Usa **Docker** (opcion A) o instala Build Tools             |
| Puerto 3006 ya en uso                          | Otro proceso ocupandolo                     | El script lo libera, o `Stop-Process -Id <pid> -Force`      |
| Sin audio narrado                              | Falta `OPENAI_API_KEY` o cuota agotada      | Revisar `backend/.env`                                      |
| Sin comentarios IA                             | Falta `DEEPSEEK_API_KEY` o cuota agotada    | Revisar `backend/.env`                                      |

---

## 8. Comandos utiles

```powershell
# Estado de puertos
python -c "import socket; [print(p, 'OPEN' if (lambda s:(s.settimeout(0.5),s.connect_ex(('127.0.0.1',p))==0)[1])(socket.socket()) else 'CLOSED') for p in [3006,4000,4001,3000]]"

# Levantar f1-dash via Docker (sin web service)
cd "F1 dash"; docker compose up -d api realtime

# Bajar f1-dash
cd "F1 dash"; docker compose down

# Detener backend (puerto 3006)
Get-NetTCPConnection -LocalPort 3006 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# Solo backend (sin f1-dash), util para desarrollo
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 3006

# Rebuild del frontend
npx --yes esbuild "frontend/app.jsx" --bundle --platform=browser --format=iife --outfile="frontend/app.bundle.js"
```
