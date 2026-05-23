"""
Cliente para el API de f1-dash (Realtime puerto 4000, opcional API 4001).
Obtiene estado en vivo por polling a GET /api/current o a /api/data/*.
Devuelve el mismo formato de estado que esperan main.py, core_loop y ai_engine.
"""
import logging
import time
from threading import Thread
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Formato de estado que consume el resto de la app (igual que F1LivePulseClient)
DEFAULT_STATE = {
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
}


def _get(obj: dict, *keys: str, default: Any = None) -> Any:
    """Obtiene valor de un dict probando varias claves (camelCase / snake_case)."""
    for k in keys:
        if k in obj and obj[k] is not None:
            return obj[k]
    return default


def _float_gap(s: Any) -> float:
    try:
        if s is None:
            return 0.0
        if isinstance(s, dict):
            s = s.get("Value") or s.get("value") or ""
        return float(str(s).replace("+", "").strip() or "0")
    except (TypeError, ValueError):
        return 0.0


def _photo_and_car_urls(driver_info: dict) -> tuple:
    photo_url = ""
    head = _get(driver_info, "HeadshotUrl", "headshotUrl")
    public_id = _get(driver_info, "PublicIdRight", "publicIdRight")
    if head and str(head).strip():
        photo_url = str(head).strip()
        if photo_url.startswith("//"):
            photo_url = "https:" + photo_url
        elif photo_url.startswith("/"):
            photo_url = "https://media.formula1.com" + photo_url
    elif public_id:
        photo_url = f"https://media.formula1.com/image/upload/c_fill,w_720/q_auto/v1740000001/{public_id}.webp"
    car_url = str(_get(driver_info, "CarImageUrl", "carImageUrl") or "").strip()
    return photo_url, car_url


class F1DashClient:
    """
    Cliente para f1-dash Realtime (puerto 4000). Sin API key.
    Mantiene el estado en el mismo formato que F1LivePulseClient para no tocar ai_engine ni frontend.
    """

    def __init__(self, realtime_base: str = "http://localhost:4000", api_base: Optional[str] = None):
        self.realtime_base = realtime_base.rstrip("/")
        self.api_base = (api_base or "http://localhost:4001").rstrip("/")
        self.current_state: Dict = dict(DEFAULT_STATE)
        self.is_running = False
        self._thread: Optional[Thread] = None
        self.poll_interval = 5
        self.api_calls_count = 0

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("F1 Dash API Client started (polling %s every %ss)", self.realtime_base, self.poll_interval)

    def stop(self) -> None:
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("F1 Dash API Client stopped")

    def get_state(self) -> Dict:
        return self.current_state

    def refresh_now(self) -> None:
        try:
            self._update_state()
        except Exception as e:
            logger.error("F1 Dash refresh error: %s", e)

    def _fetch_piecemeal_state(self) -> Dict[str, Any]:
        """Último valor por endpoint (mismo StateService que /api/current)."""
        state_parts: Dict[str, Any] = {}
        endpoints = [
            ("/api/data/timing", "TimingData"),
            ("/api/drivers", "DriverList"),
            ("/api/data/lap-count", "LapCount"),
            ("/api/data/weather", "WeatherData"),
            ("/api/data/race-control", "RaceControlMessages"),
            ("/api/data/session-info", "SessionInfo"),
            ("/api/data/track-status", "TrackStatus"),
            ("/api/data/timing-app-data", "TimingAppData"),
            ("/api/data/timing-stats", "TimingStats"),
        ]
        for path, key in endpoints:
            try:
                r = requests.get(self.realtime_base + path, timeout=6)
                self.api_calls_count += 1
                if r.status_code == 200 and r.text:
                    body = r.json()
                    if body is not None:
                        state_parts[key] = body
            except Exception:
                pass
        return state_parts

    def _merge_state_payload(
        self,
        base: Optional[Dict[str, Any]],
        overlays: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Une el JSON de /api/current con respuestas sueltas: gana el dato más reciente por clave."""
        combined: Dict[str, Any] = {}
        if base:
            combined.update(base)
        for k, v in overlays.items():
            if v is not None:
                combined[k] = v
        return combined

    def _loop(self) -> None:
        while self.is_running:
            try:
                self._update_state()
            except Exception as e:
                logger.error("F1 Dash polling error: %s", e)
            time.sleep(self.poll_interval)

    def _update_state(self) -> None:
        base_data: Optional[Dict[str, Any]] = None
        try:
            r = requests.get(f"{self.realtime_base}/api/current", timeout=10)
            self.api_calls_count += 1
            if r.status_code == 200 and r.text:
                raw = r.json()
                if isinstance(raw, dict) and not raw.get("error"):
                    base_data = raw
        except Exception as e:
            logger.debug("GET /api/current failed: %s", e)

        overlays = self._fetch_piecemeal_state()
        combined = self._merge_state_payload(base_data, overlays)
        self.current_state = self._map_state(combined)

    def _map_state(self, data: Dict[str, Any]) -> Dict:
        """Convierte estado f1-dash (camelCase) al formato interno de F1 Comments."""
        lap = 1
        total_laps = 0
        lap_count = data.get("LapCount") or {}
        if isinstance(lap_count, dict):
            lap = int(lap_count.get("CurrentLap") or lap_count.get("currentLap") or 1)
            total_laps = int(lap_count.get("TotalLaps") or lap_count.get("totalLaps") or 0)

        # DriverList: puede ser dict keyed by RacingNumber o por Tla, o lista
        driver_list_raw = data.get("DriverList") or data.get("driverList")
        drivers_by_number: Dict[str, Dict] = {}
        if isinstance(driver_list_raw, list):
            for d in driver_list_raw:
                if isinstance(d, dict):
                    rn = str(_get(d, "RacingNumber", "racingNumber") or "")
                    if rn:
                        drivers_by_number[rn] = d
        elif isinstance(driver_list_raw, dict):
            for k, d in driver_list_raw.items():
                if isinstance(d, dict):
                    rn = str(_get(d, "RacingNumber", "racingNumber") or k)
                    if rn:
                        drivers_by_number[rn] = d

        timing_data = data.get("TimingData") or data.get("timingData") or {}
        lines = timing_data.get("Lines") or timing_data.get("lines") or {}
        if not isinstance(lines, dict):
            lines = {}

        positions: List[Dict] = []
        for rn, line in lines.items():
            if not isinstance(line, dict):
                continue
            driver_info = drivers_by_number.get(str(rn)) or {}
            tla = _get(line, "Tla", "tla") or _get(driver_info, "Tla", "tla") or str(rn)
            name = _get(driver_info, "FullName", "fullName", "BroadcastName", "broadcastName") or tla
            team = _get(driver_info, "TeamName", "teamName") or "Unknown"

            pos_str = _get(line, "Position", "position")
            try:
                position = int(pos_str) if pos_str is not None else 99
            except (TypeError, ValueError):
                position = 99

            interval = _get(line, "IntervalToPositionAhead", "intervalToPositionAhead", "GapToLeader", "gapToLeader")
            gap = _float_gap(interval)

            last_lap = _get(line, "LastLapTime", "lastLapTime")
            if isinstance(last_lap, dict):
                last_lap_time = str(last_lap.get("Value") or last_lap.get("value") or "--:--")
            else:
                last_lap_time = str(last_lap or "--:--").strip() or "--:--"

            sectors_raw = _get(line, "Sectors", "sectors") or []
            if isinstance(sectors_raw, list):
                sector_times = [str(s.get("Value") or s.get("value") or "--") if isinstance(s, dict) else "--" for s in sectors_raw[:3]]
            else:
                sector_times = ["--", "--", "--"]
            while len(sector_times) < 3:
                sector_times.append("--")

            # Neumático desde TimingAppData.Stints si está disponible
            tyre = "-"
            app_data = data.get("TimingAppData") or data.get("timingAppData") or {}
            app_lines = (app_data.get("Lines") or app_data.get("lines")) or {}
            app_line = app_lines.get(str(rn)) if isinstance(app_lines, dict) else None
            if isinstance(app_line, dict):
                stints = app_line.get("Stints") or app_line.get("stints") or []
                if stints and isinstance(stints[0], dict):
                    tyre = str(stints[0].get("Compound") or stints[0].get("compound") or "-")

            photo_url, car_url = _photo_and_car_urls(driver_info)

            positions.append({
                "position": position,
                "tla": tla,
                "name": name,
                "team": team,
                "gap": gap,
                "last_lap_time": last_lap_time,
                "photo_url": photo_url,
                "car_url": car_url,
                "tyre": tyre,
                "pit_stops": 0,
                "drs_enabled": False,
                "sector_times": sector_times[:3],
                "RacingNumber": str(rn),
            })

        positions.sort(key=lambda x: x["position"])

        if not positions and drivers_by_number:
            app_data = data.get("TimingAppData") or data.get("timingAppData") or {}
            app_lines = (app_data.get("Lines") or app_data.get("lines")) or {}
            ordered = []
            for rn, driver_info in drivers_by_number.items():
                if not isinstance(driver_info, dict):
                    continue
                try:
                    line_ord = int(_get(driver_info, "Line", "line") or 999)
                except (TypeError, ValueError):
                    line_ord = 999
                ordered.append((line_ord, str(rn), driver_info))
            ordered.sort(key=lambda t: (t[0], int(t[1]) if t[1].isdigit() else 999))

            for idx, (_, rn, driver_info) in enumerate(ordered):
                tla = _get(driver_info, "Tla", "tla") or str(rn)
                name = _get(driver_info, "FullName", "fullName", "BroadcastName", "broadcastName") or tla
                team = _get(driver_info, "TeamName", "teamName") or "Unknown"
                photo_url, car_url = _photo_and_car_urls(driver_info)
                tyre = "-"
                app_line = app_lines.get(str(rn)) if isinstance(app_lines, dict) else None
                if isinstance(app_line, dict):
                    stints = app_line.get("Stints") or app_line.get("stints") or []
                    if stints and isinstance(stints[0], dict):
                        tyre = str(stints[0].get("Compound") or stints[0].get("compound") or "-")
                positions.append({
                    "position": idx + 1,
                    "tla": tla,
                    "name": name,
                    "team": team,
                    "gap": 0.0,
                    "last_lap_time": "--:--",
                    "photo_url": photo_url,
                    "car_url": car_url,
                    "tyre": tyre,
                    "pit_stops": 0,
                    "drs_enabled": False,
                    "sector_times": ["--", "--", "--"],
                    "RacingNumber": str(rn),
                })

        # Race control
        race_control: List[Dict] = []
        rc = data.get("RaceControlMessages") or data.get("raceControlMessages") or {}
        messages = rc.get("Messages") or rc.get("messages") or []
        for m in messages[-10:] if isinstance(messages, list) else []:
            if isinstance(m, dict):
                race_control.append({
                    "lap": m.get("Lap") or m.get("lap") or 1,
                    "msg": m.get("Message") or m.get("message") or "",
                })

        # Session info
        session_info = {}
        si = data.get("SessionInfo") or data.get("sessionInfo") or {}
        if isinstance(si, dict):
            meeting = si.get("Meeting") or si.get("meeting") or {}
            if isinstance(meeting, dict):
                session_info["meetingOfficialName"] = meeting.get("OfficialName") or meeting.get("officialName") or ""
            session_info["sessionName"] = si.get("Name") or si.get("name") or ""
            session_info["sessionType"] = si.get("Type") or si.get("type") or ""
            session_info["startDate"] = si.get("StartDate") or si.get("startDate") or ""
            session_info["endDate"] = si.get("EndDate") or si.get("endDate") or ""
        track = data.get("TrackStatus") or data.get("trackStatus") or {}
        if isinstance(track, dict):
            session_info["trackStatus"] = track.get("Status") or track.get("status") or "AllClear"

        # Reloj de sesion (countdown para practicas / qualy). En carrera no aplica; usa total_laps.
        clock = data.get("ExtrapolatedClock") or data.get("extrapolatedClock") or {}
        if isinstance(clock, dict):
            session_info["clockRemaining"] = clock.get("Remaining") or clock.get("remaining") or ""
            session_info["clockUtc"] = clock.get("Utc") or clock.get("utc") or ""
            session_info["clockExtrapolating"] = bool(clock.get("Extrapolating") or clock.get("extrapolating") or False)

        # Estado de la sesion (Started / Finished / Aborted / Inactive)
        sstatus = data.get("SessionStatus") or data.get("sessionStatus") or {}
        if isinstance(sstatus, dict):
            session_info["sessionStatusStarted"] = sstatus.get("Started") or sstatus.get("started") or ""
            session_info["sessionStatusStatus"] = sstatus.get("Status") or sstatus.get("status") or ""

        # Weather
        weather = {}
        w = data.get("WeatherData") or data.get("weatherData") or {}
        if isinstance(w, dict):
            air = w.get("AirTemp") or w.get("airTemp") or w.get("AirTemp")
            track_t = w.get("TrackTemp") or w.get("trackTemp")
            try:
                if air is not None:
                    weather["airTemp"] = float(air)
                if track_t is not None:
                    weather["trackTemp"] = float(track_t)
            except (TypeError, ValueError):
                pass
            weather["rainfall"] = w.get("Rainfall") or w.get("rainfall") or 0
            weather["windSpeed"] = w.get("WindSpeed") or w.get("windSpeed")

        # Grid context (velocidades desde TimingStats si existe)
        grid_context: List[Dict] = []
        stats = data.get("TimingStats") or data.get("timingStats") or {}
        speed_by_number: Dict[str, float] = {}
        if isinstance(stats, dict):
            stats_lines = stats.get("Lines") or stats.get("lines") or {}
            if isinstance(stats_lines, dict):
                for num, sd in stats_lines.items():
                    if not isinstance(sd, dict):
                        continue
                    speeds = sd.get("BestSpeeds") or sd.get("bestSpeeds") or sd.get("Speeds") or sd.get("speeds") or {}
                    if isinstance(speeds, dict):
                        for k, v in list(speeds.items())[:4]:
                            if isinstance(v, dict):
                                val = v.get("Value") or v.get("value")
                                try:
                                    f = float(val)
                                    if f > speed_by_number.get(str(num), 0):
                                        speed_by_number[str(num)] = f
                                except (TypeError, ValueError):
                                    pass
        for p in positions:
            grid_context.append({
                "tla": p["tla"],
                "team": p["team"],
                "name": p["name"],
                "top_speed": speed_by_number.get(p.get("RacingNumber", ""), 0),
            })

        return {
            "lap": lap,
            "total_laps": total_laps,
            "positions": positions,
            "race_control": race_control,
            "live_commentary": "",
            "team_radio": "",
            "session_info": session_info,
            "grid_context": grid_context,
            "pit_stops": [],
            "tyre_stints": [],
            "weather": weather,
        }
