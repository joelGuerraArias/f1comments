import os
import json
import pathlib
from contextlib import asynccontextmanager
from typing import Dict
from dotenv import load_dotenv

BASE_DIR = pathlib.Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, Response, Query, Body, UploadFile, File
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from f1_dash_client import F1DashClient
from core_loop import NarrationLoop
from audio_engine import generate_audio
from interaction_engine import generate_listener_turn, transcribe_voice_clip
from ai_engine import generate_race_commentary, _sorted_by_position
from race_simulator import RaceSimulator

# Rutas absolutas respecto a este archivo (funcionan desde cualquier cwd)
FRONTEND_DIR = BASE_DIR.parent / "frontend"
ADMIN_CONFIG_FILE = BASE_DIR / "admin_config.json"


def _load_admin_config() -> dict:
    """Carga la config de admin desde disco; se mantiene hasta que se cambie en otra carrera."""
    if ADMIN_CONFIG_FILE.exists():
        try:
            with open(ADMIN_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"race_name": data.get("race_name", ""), "race_info": data.get("race_info", ""), "context": data.get("context", "")}
        except Exception:
            pass
    return {"race_name": "", "race_info": "", "context": ""}


def _save_admin_config(config: dict) -> None:
    """Guarda la config de admin en disco."""
    with open(ADMIN_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# Admin config: carrera a narrar + información que se inyecta cada 5 comentarios (persistida en admin_config.json)
admin_config = _load_admin_config()

# Fuente de comentarios: "api" = datos en vivo del API, "pista" = datos de Admin (race_info)
narration_source = "api"

# API client: f1-dash (Realtime 4000). start(), stop(), get_state(), refresh_now().
api_client = None
narration_loop = None

# Simulador de respaldo: se usa cuando f1-dash no responde (no live data).
# Permite ver el dashboard con los 22 pilotos 2026 aunque f1-dash este apagado.
_simulator = RaceSimulator()


class AdminConfigBody(BaseModel):
    race_name: str = ""
    race_info: str = ""
    context: str = ""


class NarrationSourceBody(BaseModel):
    source: str = "api"  # "api" | "pista"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global api_client, narration_loop, admin_config
    admin_config = _load_admin_config()

    f1_dash_realtime = os.environ.get("F1_DASH_REALTIME_URL", "").strip() or os.environ.get("REALTIME_URL", "http://localhost:4000").strip()
    f1_dash_api = os.environ.get("F1_DASH_API_URL", "").strip() or os.environ.get("API_BASE_URL", "").strip()
    api_client = F1DashClient(realtime_base=f1_dash_realtime, api_base=f1_dash_api or None)
    api_client.start()

    def get_admin_config():
        return admin_config

    def get_narration_source():
        return narration_source

    narration_loop = NarrationLoop(api_client, get_admin_config=get_admin_config, get_narration_source=get_narration_source) if api_client else None
    if narration_loop:
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
        narration_loop.start(deepseek_key)

    try:
        yield
    finally:
        if api_client:
            api_client.stop()
        if narration_loop:
            narration_loop.stop()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/admin/config")
async def get_admin_config():
    """Devuelve la config de admin: carrera a narrar e información para comentaristas."""
    return admin_config


@app.put("/api/admin/config")
async def put_admin_config(body: AdminConfigBody = Body(...)):
    """Actualiza carrera a narrar e información de la carrera. Se guarda en disco hasta que se cambie en otra carrera."""
    global admin_config
    admin_config = {"race_name": body.race_name or "", "race_info": body.race_info or "", "context": body.context or ""}
    _save_admin_config(admin_config)
    return admin_config


@app.get("/api/narration/source")
async def get_narration_source():
    """Devuelve la fuente actual de comentarios: 'api' (en vivo) o 'pista' (datos de Admin)."""
    return {"source": narration_source}


@app.put("/api/narration/source")
async def put_narration_source(body: NarrationSourceBody = Body(...)):
    """Cambia la fuente de comentarios: 'api' = datos en vivo del API, 'pista' = datos de la carrera en Admin."""
    global narration_source
    s = (body.source or "api").strip().lower()
    narration_source = "pista" if s == "pista" else "api"
    return {"source": narration_source}


@app.get("/api/debug/endpoints")
async def debug_endpoints():
    """Lista endpoints del API f1-dash (GET /api/endpoints en puerto 4001)."""
    import requests
    f1_dash_api = os.environ.get("F1_DASH_API_URL", "").strip() or os.environ.get("API_BASE_URL", "http://localhost:4001").strip()
    try:
        r = requests.get(f"{f1_dash_api.rstrip('/')}/api/endpoints", timeout=8)
        if r.status_code == 200:
            data = r.json()
            return {"endpoints": data.get("endpoints", data), "api_base": data.get("api_base"), "realtime_base": data.get("realtime_base")}
        return {"error": f"f1-dash API returned {r.status_code}", "endpoints": []}
    except Exception as e:
        return {"error": str(e), "endpoints": []}


@app.get("/api/debug/two-commentaries")
async def debug_two_commentaries():
    """Genera dos bloques de comentarios (Mark + Maria) usando el estado actual del API."""
    if not api_client:
        return {"error": "API client no inicializado", "state_used": None, "commentary_1": [], "commentary_2": []}
    state = api_client.get_state()
    pos_sorted = _sorted_by_position(state.get("positions") or [])
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    race_name = admin_config.get("race_name", "")
    commentary_1 = await asyncio.to_thread(generate_race_commentary, deepseek_key, state, race_name=race_name)
    commentary_2 = await asyncio.to_thread(generate_race_commentary, deepseek_key, state, race_name=race_name)
    return {
        "state_used": {
            "lap": state.get("lap"),
            "positions_count": len(state.get("positions", [])),
            "top_3": [{"position": p.get("position"), "name": p.get("name"), "team": p.get("team"), "gap": p.get("gap")} for p in pos_sorted[:3]],
            "race_control": state.get("race_control", []),
            "session_info": state.get("session_info", {}),
        },
        "commentary_1": commentary_1,
        "commentary_2": commentary_2,
    }


def _state_for_narration():
    """Estado a usar para generar comentarios: API en vivo o solo datos de Admin según narration_source."""
    global narration_source, admin_config
    if narration_source == "pista":
        return {
            "lap": 1,
            "positions": [],
            "race_control": [],
            "live_commentary": "",
            "team_radio": "",
            "session_info": {},
            "grid_context": [],
            "pit_stops": [],
            "tyre_stints": [],
            "weather": {},
            "admin_race_name": admin_config.get("race_name", ""),
            "admin_race_info": admin_config.get("race_info", ""),
        }
    if api_client:
        state = api_client.get_state()
        state["admin_race_name"] = ""
        state["admin_race_info"] = ""
        return state
    return {"lap": 1, "positions": [], "race_control": [], "admin_race_name": "", "admin_race_info": ""}


@app.get("/api/commentary/now")
async def get_commentary_now():
    """Genera un único comentario (Mark + María) a partir del estado actual (API o Admin según el switch)."""
    state = _state_for_narration()
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not deepseek_key:
        return {"error": "DEEPSEEK_API_KEY no configurada en .env", "state_used": state, "commentary": []}
    race_name = state.get("admin_race_name") or admin_config.get("race_name", "")
    commentary = await asyncio.to_thread(generate_race_commentary, deepseek_key, state, race_name=race_name)
    pos_sorted = _sorted_by_position(state.get("positions") or [])
    return {
        "state_used": {
            "source": narration_source,
            "lap": state.get("lap"),
            "positions_count": len(state.get("positions", [])),
            "top_5": [{"position": p.get("position"), "name": p.get("name"), "team": p.get("team"), "gap": p.get("gap")} for p in pos_sorted[:5]],
            "race_control": state.get("race_control", []),
            "session_info": state.get("session_info", {}),
        },
        "commentary": commentary,
    }


@app.get("/api/stats")
async def get_stats():
    """Devuelve estadísticas de uso: contador de llamadas al API F1."""
    if not api_client:
        return {"api_calls": 0}
    return {"api_calls": getattr(api_client, "api_calls_count", 0)}


@app.get("/api/state")
async def get_state():
    """Devuelve el estado actual de la carrera.

    Prioridad:
    1. f1-dash si esta disponible y trae posiciones.
    2. Simulador (RaceSimulator con parrilla 2026) como fallback para que
       el dashboard nunca se vea vacio aunque f1-dash este apagado.
    """
    state: Dict = {}
    if api_client:
        state = api_client.get_state() or {}

    if not state.get("positions"):
        sim_state = _simulator.get_state()
        state = {
            "lap": sim_state.get("lap", 1),
            "total_laps": 57,
            "positions": sim_state.get("positions", []),
            "race_control": list(getattr(_simulator, "race_control_messages", [])),
            "session_info": {
                "meetingOfficialName": "FORMULA 1 SIMULADOR 2026",
                "sessionName": "Race",
                "sessionType": "Race",
                "trackStatus": "AllClear",
            },
            "weather": {"airTemp": 24, "trackTemp": 31, "rainfall": 0},
            "live_commentary": "",
            "team_radio": "",
            "grid_context": [],
            "pit_stops": [],
            "tyre_stints": [],
            "is_simulated": True,
        }

    return state

@app.get("/api/narration/latest")
async def get_latest_narration():
    """Returns the latest generated narration array."""
    if not narration_loop:
        return {"id": 0, "comments": []}
    latest = narration_loop.get_latest()
    if latest:
        return latest
    return {"id": 0, "comments": []}

@app.get("/api/narration/audio")
async def get_narration_audio(text: str = Query(...), voice: str = Query(...)):
    """Speech API (gpt-realtime-2 por defecto, ver OPENAI_SPEECH_MODEL): devuelve MP3."""
    # Ejecuta la petición Speech API en otro hilo (evitar bloquear el event loop)
    audio_stream = await asyncio.to_thread(generate_audio, text, voice)
    
    # Try reading the stream
    try:
        content = audio_stream.read()
    except AttributeError:
        content = b""

    if not content:
        return Response(status_code=500, content="Error generating audio or no API key")
    
    return Response(content=content, media_type="audio/mpeg")


@app.post("/api/interaction/voice")
async def post_interaction_voice(audio: UploadFile = File(...)):
    """
    Oyente graba por micrófono → Whisper (OpenAI) → Mark/María responden usando el estado actual (DeepSeek).
    """
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return {"error": "OPENAI_API_KEY requerida para transcribir el micrófono.", "transcript": "", "comments": []}

    ds = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not ds:
        return {"error": "DEEPSEEK_API_KEY requerida para la respuesta de los locutores.", "transcript": "", "comments": []}

    filename = audio.filename or "recording.webm"
    body = await audio.read()
    if not body:
        return {"error": "Audio vacío.", "transcript": "", "comments": []}

    transcript = await asyncio.to_thread(transcribe_voice_clip, body, filename)
    if not transcript.strip():
        return {"error": "No se entendió nada en el audio; probá más cerca del micrófono.", "transcript": "", "comments": []}

    if api_client:
        await asyncio.to_thread(api_client.refresh_now)

    race_state = _state_for_narration()
    admin_note = (admin_config.get("race_info") or "").strip()
    segments = await asyncio.to_thread(
        generate_listener_turn,
        ds,
        transcript,
        race_state,
        admin_note,
    )

    if not segments:
        return {
            "error": "Los locutores no pudieron responder (intentá más corto).",
            "transcript": transcript,
            "comments": [],
            "lap": race_state.get("lap", 1),
        }

    return {
        "error": "",
        "transcript": transcript,
        "comments": segments,
        "lap": race_state.get("lap", 1),
    }


# Mount Static Files (ruta absoluta para no depender del cwd)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3006)
