# F1 Comments – Dashboard y narración en vivo

Aplicación web que muestra **datos en vivo de F1** y genera **comentarios de carrera con IA** en dos voces (Mark y María), con **síntesis de voz** (OpenAI Speech API, modelo **GPT Realtime 2** por defecto). Incluye dashboard de estado de carrera, podium, comentarios narrados y panel de administración.

> Inicio rápido recomendado: ver `README_START.md`

---

## Stack

| Capa      | Tecnología                          |
| --------- | ----------------------------------- |
| Backend   | Python, FastAPI, Uvicorn            |
| Frontend  | React 18 (CDN), JSX/Babel, Tailwind |
| APIs      | f1-dash (Realtime 4000, API 4001), DeepSeek, OpenAI Speech (gpt-realtime-2 por defecto) |

---

## Estructura del proyecto

```
F1COMMENTS/
├── backend/
│   ├── main.py           # API FastAPI, rutas y startup
│   ├── f1_dash_client.py # Cliente f1-dash (Realtime 4000)
│   ├── core_loop.py      # Loop de narración (cada vuelta / 10 s)
│   ├── ai_engine.py      # Generación de comentarios (DeepSeek)
│   ├── audio_engine.py   # Speech API (gpt-realtime-2 por defecto)
│   ├── endpoint_explorer.py
│   ├── race_simulator.py # Simulador (no usado en producción)
│   ├── admin_config.json # Config Admin persistida (carrera + info)
│   ├── .env              # Claves (no subir a repo)
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.jsx
│   └── styles.css
└── README.md
```

---

## Requisitos y variables de entorno

En `backend/` crea un archivo `.env` con:

| Variable               | Uso                                                |
| ---------------------- | --------------------------------------------------- |
| `F1_DASH_REALTIME_URL` | URL del Realtime f1-dash (por defecto `http://localhost:4000`). |
| `F1_DASH_API_URL`      | Opcional. URL del API f1-dash (por defecto `http://localhost:4001`) para listado de endpoints. |
| `DEEPSEEK_API_KEY`     | Comentarios con IA (Mark y María).                  |
| `OPENAI_API_KEY`       | Síntesis de voz (Speech API).                        |
| `OPENAI_SPEECH_MODEL` | Opcional. Por defecto `gpt-realtime-2`. Alternativa si no tienes acceso: `gpt-4o-mini-tts`. |

**Fuente de datos:** La app usa solo el **API de f1-dash** (Realtime en 4000). Sin f1-dash en marcha no hay datos en vivo. Sin `DEEPSEEK_API_KEY` no se generan comentarios.

---

## Instalación y ejecución

### Arrancar la app (con f1-dash como motor de API)

El motor de datos en vivo es **f1-dash** (API en 4001, Realtime en 4000). Hay que arrancarlo **antes** que F1 Comments:

1. **Arrancar f1-dash** (desde la carpeta `F1 dash/`, requiere [Rust](https://rustup.rs)):
   ```bash
   cd "F1 dash"
   cargo run -p api        # Terminal 1: API en http://localhost:4001
   cargo run -p realtime   # Terminal 2: Realtime en http://localhost:4000
   ```
2. **Arrancar F1 Comments** (desde la raíz del proyecto):
   ```bash
   cd backend
   pip install -r requirements.txt
   # .env con F1_DASH_REALTIME_URL=http://localhost:4000, DEEPSEEK_API_KEY, OPENAI_API_KEY
   uvicorn main:app --host 0.0.0.0 --port 3006
   ```

**Script todo-en-uno (Windows PowerShell):** desde la raíz del proyecto:
```powershell
.\start-app.ps1
```
Arranca en orden: f1-dash API → f1-dash Realtime → F1 Comments.

Abrir en el navegador: **http://127.0.0.1:3006**

---

## Funcionalidades

### Dashboard
- **Podium Live**: Top 4 con fotos y gaps.
- **Race State**: Lista de pilotos con posición, equipo, última vuelta, sectores S1/S2/S3, neumático, paradas, gap. Temperatura real (aire) en el header cuando el API la envía.
- **Comentarios**: Pestañas “Narrados” y “Próximos”; cola de audio con precarga para reducir huecos entre comentarios.
- **API Debug**: Explorar endpoints F1, generar “2 comentarios” o “comentario con datos actuales”.
- **Admin**: Configurar carrera a narrar e información de la carrera (persistida en `admin_config.json` hasta que se cambie).

### Switch Pista / API (barra lateral)
- **API**: Los comentarios se basan en **datos en vivo** del API (posiciones, timing, paradas, tiempo, etc.).
- **Pista**: Los comentarios se basan solo en la **información de la carrera** configurada en Admin (nombre + texto). No se usa telemetría en vivo.

### Admin
- **Carrera que se va a narrar**: nombre que aparece en el header y en el contexto de la IA (ej. “Gran Premio de China”). Se muestra “Gran Premio” en blanco y “DE CHINA” en rojo.
- **Información de la carrera**: texto que los comentaristas pueden usar. En modo API se inyecta en el prompt **cada 5 comentarios**; en modo Pista es la **única** base del comentario.
- Al guardar se muestra el indicador “Guardado” y la config se persiste en disco.

### Datos del API utilizados
- Driver list, posiciones, timing (LAST, S1/S2/S3, Overtake), tiempo (weather: aire, pista, lluvia), pit stops, tyre stints (cuando el API responde), session info, live commentary, race control, team radio.
- Se usa el término **Overtake** en lugar de DRS en prompts y textos visibles.

### Narración
- Loop automático: cada vuelta nueva o cada 10 s se genera un bloque Mark + María.
- Botón **NARRACION**: activa/desactiva la recepción de comentarios automáticos y la cola de audio.
- **Hablar (tap ×2)** (barra lateral, morado): 1.er pulso empieza a grabarte; 2.º pulso envía tu voz. OpenAI Whisper transcribe; Mark y María contestan usando el **estado actual** (API/Pista igual que la narración). Sus frases pasan **al frente de la cola** para contestarte pronto sin cancelar los comentarios automáticos (siguen después). Si la narración está en pausa, igual podés hacer una consulta puntual solo con el micrófono.
- Precarga del siguiente audio para que no se oigan huecos grandes entre comentarios.

---

## API (resumen)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET    | `/` | Frontend (index.html) |
| GET    | `/api/state` | Estado actual (vuelta, posiciones, weather, etc.) |
| GET    | `/api/narration/latest` | Último bloque de comentarios generado |
| GET    | `/api/narration/audio?text=...&voice=...` | MP3 (Mark/María), Speech API |
| GET    | `/api/narration/source` | Fuente de comentarios: `api` o `pista` |
| PUT    | `/api/narration/source` | Cambiar fuente (body: `{ "source": "api" \| "pista" }`) |
| POST   | `/api/interaction/voice` | Oyente graba (`multipart/form-data`: campo `audio`) → Whisper + DeepSeek Mark/María usando estado actual |
| GET    | `/api/admin/config` | Config Admin (race_name, race_info) |
| PUT    | `/api/admin/config` | Guardar Admin (body: race_name, race_info) |
| GET    | `/api/commentary/now` | Generar un comentario con el estado actual (según source) |
| GET    | `/api/debug/endpoints` | Listar endpoints del API f1-dash |
| GET    | `/api/debug/two-commentaries` | Generar dos bloques de comentarios (modo API) |

---

## Parrilla 2026

La IA usa una parrilla fija 2026 (pilotos y equipos) para evitar alucinaciones. Está definida en `backend/ai_engine.py` (GRID_2026) y en `backend/race_simulator.py` (DRIVERS_2026) para el simulador.

---

## Integración con f1-dash

Si usas el proyecto **f1-dash** (carpeta `F1 dash/` o servidor aparte), arranca su Realtime en el puerto 4000 y opcionalmente el API en 4001. En F1 Comments define en `.env`:

- `F1_DASH_REALTIME_URL=http://localhost:4000`
- `F1_DASH_API_URL=http://localhost:4001` (opcional)

La guía de consumo del API de f1-dash está en `F1 dash/CONSUMIR_API.md`.

---

## Notas

- Sin carrera en vivo, posiciones y sectores pueden aparecer vacíos o por defecto; el tiempo (weather) y el resto de datos se muestran cuando el API los envía.
- La config de Admin se guarda en `backend/admin_config.json` y se mantiene entre reinicios.
- El switch **Pista / API** solo afecta a la **fuente de datos** con la que se generan los comentarios; el resto del dashboard sigue mostrando datos del API cuando está disponible.
