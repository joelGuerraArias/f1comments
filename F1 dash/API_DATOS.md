# Cómo sacar los datos – API y fuentes del proyecto

Este documento describe **qué APIs usa el proyecto** y **cómo obtener los datos** (calendario y tiempo real).

---

## 1. Resumen de fuentes de datos

| Dato | Fuente | Uso en el proyecto |
|------|--------|----------------------|
| **Calendario / Schedule** | iCal (ecal.com) + **fallback Ergast** | API (`/api/schedule`, `/api/schedule/next`) |
| **Datos en vivo (telemetría)** | **livetiming.formula1.com** (SignalR) | Servicio `realtime` → WebSocket/SSE |

---

## 2. Calendario (schedule)

### API del proyecto (puerto 4001)

El servicio **api** expone:

- **GET** `http://localhost:4001/api/schedule`  
  Devuelve el calendario del año en curso (rondas y sesiones).

- **GET** `http://localhost:4001/api/schedule/next`  
  Devuelve la próxima carrera (o 204 No Content si no hay más).

### Fuentes que usa la API por dentro

1. **Principal:** iCal de ecal.com  
   - URL: `https://ics.ecal.com/ecal-sub/660897ca63f9ca0008bcbea6/Formula%201.ics`  
   - Si falla o viene vacío…

2. **Fallback:** Ergast API (gratis, sin API key)  
   - URL: `https://ergast.com/api/f1/{year}.json`  
   - Ejemplo: `https://ergast.com/api/f1/2025.json`

Para **sacar los datos de calendario** puedes:

- Levantar la API y llamar a los endpoints anteriores, o  
- Llamar directamente a Ergast:  
  `GET https://ergast.com/api/f1/2025.json`

---

## 3. Datos en vivo (SignalR F1)

### Origen oficial

- **Base:** `livetiming.formula1.com/signalr`
- **Hub:** `Streaming`

### Negociación (negotiate)

Para obtener un token de conexión (sin WebSocket):

```
GET https://livetiming.formula1.com/signalr/negotiate?clientProtocol=1.5&connectionData=%5B%7B%22name%22%3A%22Streaming%22%7D%5D
```

`connectionData` es: `[{"name":"Streaming"}]` en URL-encoded.

La respuesta incluye `ConnectionToken` y `ConnectionId` para abrir el WebSocket.

### Conexión WebSocket

URL de conexión (sustituir `{token}` por el `ConnectionToken` de negotiate):

```
wss://livetiming.formula1.com/signalr/connect?clientProtocol=1.5&transport=webSockets&connectionToken={token}
```

Cabeceras recomendadas:

- `User-Agent: BestHTTP`
- `Cookie: <la que devuelva negotiate>`

### Topics (canales) a los que se suscribe el proyecto

El servicio **realtime** se suscribe a estos temas:

- Heartbeat  
- CarData.z  
- Position.z  
- ExtrapolatedClock  
- TimingStats  
- TimingAppData  
- WeatherData  
- TrackStatus  
- SessionStatus  
- DriverList  
- RaceControlMessages  
- SessionInfo  
- SessionData  
- LapCount  
- TimingData  
- TeamRadio  
- ChampionshipPrediction  

Para **sacar los datos en vivo** tienes dos opciones:

1. **Usar el servicio realtime del proyecto**  
   - Conectar el dashboard (o cualquier cliente) al SSE que expone el realtime (por ejemplo `/api/realtime` según la configuración del dashboard).

2. **Conectar tu propio cliente** al SignalR de F1 (negotiate + connect con el token y suscribirte a los temas anteriores).

---

## 4. Cómo probar que “sale” data

### Calendario (sin levantar nada)

Desde PowerShell (o navegador):

```powershell
# Ergast (calendario 2025)
Invoke-RestMethod -Uri "https://ergast.com/api/f1/2025.json" -Method Get
```

Si la **API del proyecto** está corriendo en el puerto 4001:

```powershell
Invoke-RestMethod -Uri "http://localhost:4001/api/schedule" -Method Get
Invoke-RestMethod -Uri "http://localhost:4001/api/schedule/next" -Method Get
```

### SignalR (negotiate)

```powershell
Invoke-RestMethod -Uri "https://livetiming.formula1.com/signalr/negotiate?clientProtocol=1.5&connectionData=%5B%7B%22name%22%3A%22Streaming%22%7D%5D" -Method Get
```

Deberías ver JSON con `ConnectionToken`, `ConnectionId`, etc.

### Realtime (flujo completo)

1. Levantar el servicio **realtime** (Rust) para que se conecte a F1 SignalR y reenvíe los datos.
2. Conectar el **dashboard** al realtime (por ejemplo por SSE).
3. Durante una sesión en vivo, los datos aparecerán en el dashboard (y en cualquier cliente que consuma el mismo SSE/API).

---

## 5. Cómo levantar la API

### Con Docker (recomendado)

Desde la raíz del proyecto:

```bash
docker compose up api
```

La API quedará en **http://localhost:4001** (usa `compose.override.yaml`).  
También puedes levantar solo la API con el script:

```powershell
.\scripts\run-api.ps1
```

### Sin Docker (Rust instalado)

```bash
cd "c:\ruta\al\F1 dash"
cargo run -p api
```

Variables opcionales (o crea `api/.env` a partir de `api/.env.example`):

- `ADDRESS=0.0.0.0:4001` – Puerto por defecto 4001.
- `ORIGIN=http://localhost:3000` – CORS para el dashboard.

### Probar que responde

```powershell
Invoke-RestMethod -Uri "http://localhost:4001/api/health" -Method Get
Invoke-RestMethod -Uri "http://localhost:4001/api/schedule" -Method Get
```

---

## 6. Cambios hechos en el código

- **API – `api/src/endpoints/schedule.rs`**  
  - Si el iCal de ecal falla o viene vacío, la API usa **Ergast** como fallback para seguir sacando el calendario.  
  - Así los endpoints `/api/schedule` y `/api/schedule/next` pueden devolver datos aunque ecal no responda.

Con esto, la API del proyecto puede **sacar los datos** de calendario (y, con el servicio realtime, los datos en vivo de F1).
