# Endpoints JSON para otras apps

Todos los endpoints devuelven **JSON**. Puedes consumirlos desde otra aplicación.

**Listado dinámico:** `GET http://localhost:4001/api/endpoints` devuelve todas las URLs con descripción.

---

## API (puerto 4001)

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/schedule` | Calendario completo del año |
| GET | `/api/schedule/next` | Próxima carrera |
| GET | `/api/endpoints` | Listado de todos los endpoints (URLs listas para usar) |

**Base URL por defecto:** `http://localhost:4001`

---

## Realtime – datos en vivo (puerto 4000)

Cada endpoint devuelve el dato indicado en JSON. Si no hay sesión en vivo, algunos devolverán `null` o `{}`.

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/api/current` | Estado completo (todo el estado en vivo) |
| GET | `/api/drivers` | Lista de pilotos |
| GET | `/api/connections` | Número de clientes conectados al stream |
| GET | `/api/data/heartbeat` | Heartbeat |
| GET | `/api/data/car-data` | Datos del coche (RPM, velocidad, etc.) |
| GET | `/api/data/position` | Posiciones en pista |
| GET | `/api/data/extrapolated-clock` | Reloj extrapolado de sesión |
| GET | `/api/data/timing-stats` | Estadísticas de tiempos |
| GET | `/api/data/timing-app-data` | Datos de timing (app) |
| GET | `/api/data/weather` | Datos meteorológicos |
| GET | `/api/data/track-status` | Estado del circuito (banderas) |
| GET | `/api/data/session-status` | Estado de la sesión |
| GET | `/api/data/race-control` | Mensajes de control de carrera |
| GET | `/api/data/session-info` | Información de la sesión |
| GET | `/api/data/session-data` | Datos de la sesión |
| GET | `/api/data/lap-count` | Conteo de vueltas |
| GET | `/api/data/timing` | Tiempos por piloto/vuelta |
| GET | `/api/data/team-radio` | Radios de equipo |
| GET | `/api/data/championship-prediction` | Predicción de campeonato |

**Base URL por defecto:** `http://localhost:4000`

---

## Ejemplo desde otra app

```bash
# Calendario
curl http://localhost:4001/api/schedule

# Próxima carrera
curl http://localhost:4001/api/schedule/next

# Listado de todos los endpoints (con URLs completas)
curl http://localhost:4001/api/endpoints

# Datos en vivo (cuando hay sesión)
curl http://localhost:4000/api/data/weather
curl http://localhost:4000/api/data/timing
curl http://localhost:4000/api/drivers
```

Variables de entorno opcionales (API):

- `API_BASE_URL`: base URL del API en la respuesta de `/api/endpoints` (ej. `https://tu-dominio.com/api`)
- `REALTIME_URL`: base URL del servicio realtime en la respuesta (ej. `https://tu-dominio.com/live`)

---

## Guardar datos en .md para consulta posterior

Script que obtiene todos los datos (API + realtime) y los guarda en un archivo Markdown:

```powershell
.\scripts\guardar-datos-consulta.ps1
```

Salida: `data/datos-consulta-YYYY-MM-DD_HHmmss.md` (tablas + JSON por sección). Ver `data/README.md`.
