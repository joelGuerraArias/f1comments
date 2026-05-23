# Cómo consumir el API de f1-dash desde otra app

Guía para integrar tu aplicación con la API y el servicio realtime de f1-dash. Todo se sirve en **JSON** por **GET**; no hay autenticación.

---

## 1. Servicios y URLs base

Hay **dos orígenes**:

| Servicio   | Puerto por defecto | Uso principal                    |
|-----------|--------------------|-----------------------------------|
| **API**   | 4001               | Calendario, próxima carrera, health |
| **Realtime** | 4000            | Datos en vivo (sesión, tiempos, pilotos) |

En local:

- **API:** `http://localhost:4001`
- **Realtime:** `http://localhost:4000`

En producción sustituye por tus dominios (ej. `https://api.miapp.com`, `https://live.miapp.com`).

---

## 2. CORS

Ambos servicios envían cabeceras CORS. Por defecto se aceptan orígenes como `http://localhost:3000` y `https://f1-dash.com`. Para otro origen configura la variable de entorno `ORIGIN` (varios separados por `;`).

Si tu app corre en el navegador en otro dominio, ese dominio debe estar en `ORIGIN` o la petición puede ser bloqueada por CORS.

---

## 3. Descubrir endpoints (recomendado al empezar)

Un único GET te da todas las URLs listas para usar:

```http
GET http://localhost:4001/api/endpoints
```

Respuesta (resumida):

```json
{
  "api_base": "http://localhost:4001",
  "realtime_base": "http://localhost:4000",
  "endpoints": {
    "api": [
      { "method": "GET", "path": "/api/health", "url": "http://localhost:4001/api/health", "description": "..." },
      { "method": "GET", "path": "/api/schedule", "url": "http://localhost:4001/api/schedule", "description": "..." }
    ],
    "realtime": [
      { "method": "GET", "path": "/api/data/timing", "url": "http://localhost:4000/api/data/timing", "description": "..." }
    ]
  }
}
```

Usa los campos `url` para llamar desde tu app sin hardcodear puertos o hosts.

---

## 4. Formato de las peticiones

- **Método:** siempre **GET**.
- **Cabeceras:** no obligatorias; con `Accept: application/json` queda explícito.
- **Cuerpo:** ninguno.
- **Respuesta:** cuerpo en **JSON**; `Content-Type: application/json`.

---

## 5. Endpoints del API (puerto 4001)

| Path | Descripción | Respuesta típica |
|------|-------------|------------------|
| `GET /api/health` | Estado del servicio | `{ "success": true }` |
| `GET /api/schedule` | Calendario del año | Array de rondas (nombre, país, fechas, sesiones, `over`) |
| `GET /api/schedule/next` | Próxima carrera | Objeto ronda o 204 No Content |
| `GET /api/endpoints` | Listado de endpoints | Objeto con `api_base`, `realtime_base`, `endpoints` |

Estructura de una **ronda** (schedule / next):

- `name`, `countryName`, `start`, `end` (ISO 8601), `sessions[]` (cada una con `kind`, `start`, `end`), `over` (boolean).

---

## 6. Endpoints de realtime (puerto 4000)

Cada uno devuelve **solo ese dato** en JSON. Si no hay sesión en vivo, pueden devolver `null` o `{}`.

| Path | Dato |
|------|------|
| `/api/current` | Estado completo (todo el estado en vivo) |
| `/api/drivers` | Lista de pilotos |
| `/api/connections` | Número de clientes conectados al stream |
| `/api/data/session-info` | Información de la sesión |
| `/api/data/session-status` | Estado de la sesión |
| `/api/data/timing` | Tiempos por piloto/vuelta |
| `/api/data/lap-count` | Conteo de vueltas |
| `/api/data/weather` | Meteorología |
| `/api/data/track-status` | Estado pista (banderas, etc.) |
| `/api/data/position` | Posiciones en pista |
| `/api/data/car-data` | Datos coche (RPM, velocidad, etc.) |
| `/api/data/race-control` | Mensajes de race control |
| Y más (ver `GET /api/endpoints`). | |

---

## 7. Ejemplos de consumo

### JavaScript / TypeScript (fetch)

```javascript
const API_BASE = 'http://localhost:4001';
const REALTIME_BASE = 'http://localhost:4000';

// Listar todos los endpoints
const { endpoints, api_base, realtime_base } = await fetch(`${API_BASE}/api/endpoints`).then(r => r.json());

// Calendario
const schedule = await fetch(`${API_BASE}/api/schedule`).then(r => r.json());

// Próxima carrera (puede devolver 204)
const nextRes = await fetch(`${API_BASE}/api/schedule/next`);
const nextRound = nextRes.status === 204 ? null : await nextRes.json();

// Datos en vivo (cuando hay sesión)
const timing = await fetch(`${REALTIME_BASE}/api/data/timing`).then(r => r.json());
const drivers = await fetch(`${REALTIME_BASE}/api/drivers`).then(r => r.json());
```

### cURL

```bash
curl -s http://localhost:4001/api/endpoints
curl -s http://localhost:4001/api/schedule
curl -s http://localhost:4001/api/schedule/next
curl -s http://localhost:4000/api/data/timing
curl -s http://localhost:4000/api/drivers
```

### Python

```python
import requests

API_BASE = "http://localhost:4001"
REALTIME_BASE = "http://localhost:4000"

# Endpoints
r = requests.get(f"{API_BASE}/api/endpoints")
data = r.json()
# data["endpoints"]["api"], data["endpoints"]["realtime"]

# Calendario
schedule = requests.get(f"{API_BASE}/api/schedule").json()

# Realtime
timing = requests.get(f"{REALTIME_BASE}/api/data/timing").json()
```

---

## 8. Errores y códigos HTTP

- **200:** OK; cuerpo en JSON.
- **204 No Content:** Solo en `/api/schedule/next` cuando no hay próxima carrera; sin cuerpo.
- **404:** Ruta inexistente.
- **500:** Error interno; el cuerpo puede incluir `{ "error": "..." }`.

En tu app comprueba `response.ok` o el código y, si es 204 en `schedule/next`, trata el resultado como “sin próxima carrera”.

---

## 9. Polling vs streaming para datos en vivo

- **Polling:** haz `GET` a los endpoints de realtime (ej. `/api/data/timing`, `/api/drivers`) cada X segundos. Simple y válido para cualquier cliente.
- **Streaming:** el dashboard usa **SSE** en `GET http://localhost:4000/api/realtime` (eventos `initial` y `update`). Úsalo si quieres actualizaciones en tiempo real sin estar haciendo GET a cada endpoint.

Para una app externa que solo quiera “leer datos”, suele bastar con polling a los `/api/data/*` que necesites.

---

## 10. Resumen rápido para tu app

1. Configura dos URLs base: **API** (4001) y **Realtime** (4000), o las que uses en producción.
2. Opcional: llama a `GET /api/endpoints` una vez y usa las `url` para no hardcodear.
3. Calendario y próxima carrera: solo **API** (`/api/schedule`, `/api/schedule/next`).
4. Datos en vivo: solo **Realtime** (`/api/drivers`, `/api/data/timing`, `/api/data/weather`, etc.).
5. Todas las respuestas son **JSON**; no hay auth; ten en cuenta **CORS** si llamas desde el navegador.

Para más detalle de rutas y ejemplos, usa `GET /api/endpoints` y el archivo `ENDPOINTS.md` en este repositorio.
