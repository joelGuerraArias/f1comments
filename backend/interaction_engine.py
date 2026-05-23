"""
Turno oyente ↔ locutores: Whisper (OpenAI) + respuesta contextual con datos en vivo (DeepSeek).
"""

import io
import logging
import os
from typing import Any, Dict, List

import requests
from openai import OpenAI

from ai_engine import GRID_2026, _clip_radio_phrase, _sorted_by_position, parse_commentary

logger = logging.getLogger(__name__)


def transcribe_voice_clip(file_bytes: bytes, filename: str = "recording.webm") -> str:
    """Transcripción con Whisper — el cliente debe poder enviar webm/mp4/opus habitual del navegador."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.error("OPENAI_API_KEY requerido para Whisper")
        return ""

    buf = io.BytesIO(file_bytes)
    buf.name = filename or "recording.webm"

    client = OpenAI(api_key=api_key)
    transcription = client.audio.transcriptions.create(model="whisper-1", file=buf)
    return (transcription.text or "").strip()


def _format_listener_snapshot(state: Dict[str, Any], admin_note: str) -> str:
    lap = state.get("lap", "?")
    total = state.get("total_laps") or state.get("totalLaps") or "?"
    session = state.get("session_info") or {}
    s_name = session.get("sessionName", "Sesión")
    meeting = session.get("meetingOfficialName", "")
    positions = _sorted_by_position(state.get("positions") or [])[:12]
    lines_pos = []
    for p in positions:
        lines_pos.append(
            f"P{p.get('position','?')} {p.get('name', p.get('tla'))} ({p.get('team')}) gap≈{p.get('gap', 0)}s last={p.get('last_lap_time', '--')} tyre={p.get('tyre', '-')}"
        )
    blk_pos = "\n".join(lines_pos) if lines_pos else "(Sin posiciones en este momento — decilo con honestidad abreviada.)"

    weather = state.get("weather") or {}
    wc = ""
    if weather.get("airTemp") is not None or weather.get("air_temp") is not None:
        at = weather.get("airTemp", weather.get("air_temp"))
        tt = weather.get("trackTemp", weather.get("track_temp"))
        rn = weather.get("rainfall", 0)
        wc = f"Aire≈{at}°C pista≈{tt}°C lluvia={rn}%"

    rc = state.get("race_control") or []
    rc_txt = "; ".join([str(r.get("msg", ""))[:120] for r in rc[-4:] if isinstance(r, dict)])

    lc = (state.get("live_commentary") or "").strip()
    lc_short = lc[:420] + "…" if len(lc) > 420 else lc

    extra = ""
    if admin_note.strip():
        extra = f"\nNOTA ADMIN (solo si cuadra con la pregunta):\n{admin_note.strip()}\n"

    return f"""SNAPSHOT SESIÓN (única fuente de hechos deportivos aquí — no contradecir orden ni gaps):
Nombre evento/sesión: {meeting} | {s_name}
Vuelta aprox.: {lap} / {total}
Clima / pista: {wc or "(no reportado)"}
TOP posiciones ordenadas por P real:
{blk_pos}

Últimos avisos dirección de carrera: {rc_txt or '(ninguno)'}

Fragmento último texto live feed (opcional): {lc_short or '(vacío)'}

{extra}
"""


def generate_listener_turn(
    deepseek_api_key: str,
    user_transcript: str,
    race_state: Dict[str, Any],
    admin_note: str = "",
) -> List[Dict[str, Any]]:
    """
    Respuesta corta Marc + María al oyente, arraigada solo en snapshot + lista 2026.
    """
    if not deepseek_api_key or not user_transcript.strip():
        return []

    endpoint = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {deepseek_api_key}",
    }

    snapshot = _format_listener_snapshot(race_state, admin_note)

    user_block = f"""Un oyente NOS HABLA POR MICRÓFONO — escuchamos su pregunta o comentario al aire:

«{user_transcript.strip()}»

{snapshot}

REFERENCIA EQUIPOS/PILOTO 2026 (no es orden en pista, solo válido para nombres):
{GRID_2026}

TU TAREA
- Respondé como dúo de radio deportiva F1 (Mark después María): tono cercano LATAM español corto tipo radio abierta al oyente — que sientan que los escuchamos.
- Usá información SOLO del SNAPSHOT cuando hables números, posiciones, neumático, tiempo; si ahí falta algo, decilo sincero («no llegó ese timing al tablero aún»).
- María puede DETALLAR algo extra del snapshot que Mark no mencionó (un gap, equipo, último mensaje carrera…) si viene al caso que planteó el oyente — sin monólogo.
- Máximo ~24 palabras por voz esta vez (pregunta interactiva puede ser algo más desarrollado que autopilot).
- FORMATO SALIDA ESTRICTO:
Mark:
[tu texto]
Maria:
[tu texto]
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "Oyente hablando por micrófono a locutores F1. Salida SIEMPRE: Mark línea María línea cortas. Latino estadio radio español.",
            },
            {"role": "user", "content": user_block},
        ],
        "temperature": 0.78,
        "max_tokens": 400,
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=22.0)
        response.raise_for_status()
        raw_text = response.json()["choices"][0]["message"]["content"]
        segments = parse_commentary(raw_text)
        for seg in segments:
            seg["text"] = _clip_radio_phrase(seg.get("text", ""), max_chars=300)
            seg["listener"] = True  # marca turno oyente por si el cliente lo muestra diferente
        return segments
    except Exception as e:
        logger.error("DeepSeek listener turn error: %s", e)
        return []
