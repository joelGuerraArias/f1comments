import time
import asyncio
import logging
from ai_engine import generate_race_commentary

logger = logging.getLogger(__name__)

class NarrationLoop:
    def __init__(self, simulator, get_admin_config=None, get_narration_source=None):
        self.simulator = simulator
        self.get_admin_config = get_admin_config  # () -> {"race_name": "", "race_info": ""}
        self.get_narration_source = get_narration_source  # () -> "api" | "pista"
        self.latest_narration = None
        self.is_running = False
        self._task = None
        self.last_narrated_lap = 0
        self.last_generation_time = 0
        self.generation_count = 0
        self.last_positions_refresh = 0
        self.previous_comments = []  # últimos comentarios generados (para evitar repetición)

    def start(self, deepseek_api_key: str):
        if self.is_running:
            return
            
        self.is_running = True
        self.deepseek_api_key = deepseek_api_key
        logger.info("Narration loop started (Continuous + Per-Lap mode).")
        
        # In a real async framework this might be a native task,
        # but asyncio.create_task is typical in FastAPI startup
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
        logger.info("Narration loop stopped.")

    async def _loop(self):
        while self.is_running:
            try:
                now = time.time()
                source = (self.get_narration_source and self.get_narration_source()) or "api"
                if source == "pista":
                    # Estado solo desde Admin (carrera / info de la pista)
                    if self.get_admin_config:
                        admin = self.get_admin_config()
                        state = {
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
                            "admin_race_name": (admin or {}).get("race_name", ""),
                            "admin_race_info": (admin or {}).get("race_info", ""),
                        }
                    else:
                        state = self.simulator.get_state()
                else:
                    state = self.simulator.get_state()
                    state["admin_race_name"] = ""
                    state["admin_race_info"] = ""
                current_lap = state.get("lap", 1)
                time_elapsed = now - self.last_generation_time

                # Intervalo mínimo un poco mayor que antes: el texto es corto (TTS rápido) y así no se
                # encola audio viejo frente a la UI; siempre refrescamos estado justo antes de generar.
                min_interval_s = 6.0
                if current_lap > self.last_narrated_lap or time_elapsed >= min_interval_s:
                    logger.info(f"Triggering commentary (source={source}). Lap: {current_lap}, Time elapsed: {time_elapsed:.1f}s")

                    # En modo API: refrescar posiciones antes de cada comentario (y al menos cada 15s entre triggers)
                    if source == "api" and hasattr(self.simulator, "refresh_now"):
                        logger.info("Forzando refresh de posiciones desde F1 API antes de generar comentario.")
                        await asyncio.to_thread(self.simulator.refresh_now)
                        self.last_positions_refresh = time.time()
                        state = self.simulator.get_state()
                        state["admin_race_name"] = ""
                        state["admin_race_info"] = ""
                        current_lap = state.get("lap", current_lap)

                    race_name = (state.get("admin_race_name") or "").strip()
                    extra_race_info = ""
                    context = ""
                    if self.get_admin_config:
                        admin = self.get_admin_config()
                        if admin:
                            context = (admin.get("context") or "").strip()
                            extra_race_info = (admin.get("race_info") or "").strip()
                    if source == "pista":
                        extra_race_info = (state.get("admin_race_info") or "").strip()

                    segments = await asyncio.to_thread(
                        generate_race_commentary,
                        self.deepseek_api_key,
                        state,
                        race_name=race_name,
                        extra_race_info=extra_race_info,
                        context=context,
                        previous_comments=self.previous_comments,
                        generation_count=self.generation_count + 1,
                    )
                    self.generation_count += 1
                    if segments:
                        new_texts = [s.get("text", "") for s in segments]
                        self.previous_comments = (self.previous_comments + new_texts)[-6:]
                    # Snapshot sencillo del estado usado para este bloque
                    state_snapshot = {
                        "lap": current_lap,
                        "positions": state.get("positions", []),
                        "session_info": state.get("session_info", {}),
                        "weather": state.get("weather", {}),
                    }
                    self.latest_narration = {
                        "id": int(time.time()),
                        "lap": current_lap,
                        "timestamp": time.time(),
                        "comments": segments,
                        "state": state_snapshot,
                    }
                    self.last_narrated_lap = current_lap
                    self.last_generation_time = time.time()
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in narration loop: {e}")
                await asyncio.sleep(5) # Backoff on error

    def get_latest(self):
        return self.latest_narration
