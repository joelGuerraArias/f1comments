"""Modo Experto: proxy realtime entre el navegador y xAI (Grok voice).

Eve es una narradora secundaria que conversa con Joel Guerra (el experto humano)
y cada N segundos recibe un resumen automatico del estado de la carrera para
hacer un comentario. Reusa el WebSocket realtime de xAI documentado por el usuario:

    wss://api.x.ai/v1/realtime?model=<modelo>

Eventos que se reenvian (texto JSON) entre navegador y xAI:
- Saliente (browser -> xAI):
    * input_audio_buffer.append   (chunks PCM base64 24kHz mono)
    * response.cancel
    * conversation.item.create / response.create (eventual texto)
- Entrante (xAI -> browser):
    * session.created
    * input_audio_buffer.speech_started
    * response.output_audio.delta            (audio PCM base64)
    * response.output_audio_transcript.delta (texto incremental)
    * response.done
    * error
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Awaitable, Callable, Optional

import websockets
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

XAI_REALTIME_URL = os.environ.get("XAI_REALTIME_URL", "wss://api.x.ai/v1/realtime")
XAI_REALTIME_MODEL = os.environ.get("XAI_REALTIME_MODEL", "grok-voice-latest")
INJECT_INTERVAL_S = int(os.environ.get("EXPERT_INJECT_INTERVAL_S", "180"))

EVE_INSTRUCTIONS = (
    "Eres Eve, narradora secundaria de Formula 1 con conocimientos generales de la "
    "categoria. Tu rol es interactuar de forma natural y fluida con el narrador experto "
    "Joel Guerra, complementando sus explicaciones con datos generales, contexto historico "
    "y anecdotas accesibles para el publico. Habla en espanol con tono entusiasta, claro "
    "y narrativo, como si estuvieras en una transmision en vivo. Manten las respuestas "
    "concisas y conversacionales (2 a 4 frases). Nunca simules acciones ni herramientas. "
    "Si surge un tema muy tecnico o actual que exceda tus conocimientos generales, reconoce "
    "amablemente que Joel puede profundizar. Evita contenido ofensivo, especulaciones sobre "
    "lesiones o temas sensibles."
)

SESSION_UPDATE = {
    "type": "session.update",
    "session": {
        "voice": "Eve",
        "instructions": EVE_INSTRUCTIONS,
        "turn_detection": {"type": "server_vad"},
        "tools": [],
        "input_audio_transcription": {"model": "grok-2-audio"},
        "audio": {
            "input": {"format": {"type": "audio/pcm", "rate": 24000}},
            "output": {"format": {"type": "audio/pcm", "rate": 24000}},
        },
    },
}


def _summarize_state(state: dict, latest_narration: Optional[dict], race_name: str = "") -> str:
    """Resumen textual corto del estado actual del API + ultimos comentarios de Mark/Maria."""
    sinfo = state.get("session_info") or {}
    session_name = sinfo.get("sessionName") or sinfo.get("sessionType") or "sesion"
    gp = race_name or sinfo.get("meetingOfficialName") or ""
    gp = gp.replace("FORMULA 1 ", "").replace("FORMULA1 ", "").strip()
    clock = (sinfo.get("clockRemaining") or "").strip()
    lap = state.get("lap")
    total = state.get("total_laps")

    positions = state.get("positions") or []

    def _key(p):
        try:
            return int(p.get("position") or 99)
        except (TypeError, ValueError):
            return 99

    positions = sorted(positions, key=_key)
    top = positions[:5]
    top_str = ", ".join(
        f"{p.get('position')}. {p.get('name') or p.get('tla')} ({p.get('team')})"
        for p in top
    ) or "sin datos en vivo"

    rc = state.get("race_control") or []
    rc_recent = rc[-3:] if isinstance(rc, list) else []
    rc_str = "; ".join(
        ((m.get("message") or m.get("text") or "") if isinstance(m, dict) else str(m))[:80]
        for m in rc_recent
    )

    last_comments = []
    if latest_narration:
        for seg in (latest_narration.get("comments") or [])[-4:]:
            who = seg.get("narrator") or "Mark"
            txt = (seg.get("text") or "").strip()
            if txt:
                last_comments.append(f"{who}: {txt}")
    last_block = "\n".join(last_comments) if last_comments else "(aun no hay comentarios de Mark)"

    weather = state.get("weather") or {}
    wx = ""
    if isinstance(weather, dict) and weather:
        ta = weather.get("airTemp")
        tt = weather.get("trackTemp")
        rain = weather.get("rainfall")
        wx = f"Tiempo: aire {ta}C, pista {tt}C, lluvia {rain}."

    parts = [f"Sesion actual: {session_name}."]
    if gp:
        parts.append(f"Gran Premio: {gp}.")
    if clock:
        parts.append(f"Tiempo restante: {clock}.")
    if lap:
        parts.append(f"Vuelta {lap}{f'/{total}' if total else ''}.")
    parts.append(f"Top 5 en pista: {top_str}.")
    if rc_str:
        parts.append(f"Race control reciente: {rc_str}.")
    if wx:
        parts.append(wx)
    parts.append("Ultimos comentarios del equipo principal:\n" + last_block)
    return "\n".join(parts)


async def _connect_upstream(url: str, headers: dict):
    """Conecta a xAI realtime con compatibilidad para websockets 12.x y 13.x."""
    try:
        return await websockets.connect(url, additional_headers=headers, max_size=20_000_000)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers, max_size=20_000_000)


async def run_expert_session(
    client_ws: WebSocket,
    api_key: str,
    get_state: Callable[[], dict],
    get_latest_narration: Callable[[], Optional[dict]],
    get_race_name: Callable[[], str],
    inject_interval_s: int = INJECT_INTERVAL_S,
) -> None:
    """Maneja una sesion completa de modo Experto con un solo cliente."""
    url = f"{XAI_REALTIME_URL}?model={XAI_REALTIME_MODEL}"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        upstream = await _connect_upstream(url, headers)
    except Exception as e:
        logger.warning("expert: no se pudo conectar a xAI: %s", e)
        try:
            await client_ws.send_text(json.dumps({
                "type": "error",
                "message": f"No pude conectar con xAI realtime: {e}",
            }))
            await client_ws.close()
        except Exception:
            pass
        return

    try:
        await upstream.send(json.dumps(SESSION_UPDATE))
        await client_ws.send_text(json.dumps({
            "type": "expert.proxy.connected",
            "model": XAI_REALTIME_MODEL,
            "inject_interval_s": inject_interval_s,
        }))

        async def browser_to_xai():
            try:
                while True:
                    msg = await client_ws.receive_text()
                    await upstream.send(msg)
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.warning("expert browser->xai: %s", e)

        async def xai_to_browser():
            try:
                async for raw in upstream:
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8", "ignore")
                    await client_ws.send_text(raw)
            except Exception as e:
                logger.warning("expert xai->browser: %s", e)

        async def periodic_inject():
            await asyncio.sleep(inject_interval_s)
            while True:
                try:
                    state = get_state() or {}
                    latest = get_latest_narration() or {}
                    race_name = get_race_name() or ""
                    summary = _summarize_state(state, latest, race_name)
                    item = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [{
                                "type": "input_text",
                                "text": (
                                    "ACTUALIZACION AUTOMATICA (cada ~3 min). Comenta "
                                    "brevemente lo mas interesante en 2 o 3 frases, "
                                    "complementando lo que ha dicho el equipo principal "
                                    "sin repetirlo. Si la sesion esta en pausa o "
                                    "terminada, hazlo notar.\n\n" + summary
                                ),
                            }],
                        },
                    }
                    await upstream.send(json.dumps(item))
                    await upstream.send(json.dumps({"type": "response.create"}))
                    await client_ws.send_text(json.dumps({
                        "type": "expert.injection",
                        "summary": summary,
                    }))
                except Exception as e:
                    logger.warning("expert inject: %s", e)
                await asyncio.sleep(inject_interval_s)

        tasks = [
            asyncio.create_task(browser_to_xai()),
            asyncio.create_task(xai_to_browser()),
            asyncio.create_task(periodic_inject()),
        ]
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in pending:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        except Exception as e:
            logger.warning("expert tasks error: %s", e)
    finally:
        try:
            await upstream.close()
        except Exception:
            pass
        try:
            await client_ws.close()
        except Exception:
            pass
