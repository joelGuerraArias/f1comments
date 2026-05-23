import os
import time
import requests
import logging
from typing import Dict, List, Optional
from threading import Thread

logger = logging.getLogger(__name__)

class F1LivePulseClient:
    """
    Client for f1-live-pulse RapidAPI. 
    Maintains the current race state by polling endpoints every 30 seconds.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://f1-live-pulse.p.rapidapi.com"
        self.headers = {
            "x-rapidapi-host": "f1-live-pulse.p.rapidapi.com",
            "x-rapidapi-key": self.api_key
        }
        
        # State Data
        self.driver_list = {} # Tla -> Driver Info
        self.current_state = {
            "lap": 1,
            "positions": [],
            "race_control": [],
            "live_commentary": "",
            "team_radio": "",
            "session_info": {},
            "grid_context": [],
            "pit_stops": [],      # lista de paradas (lap, tla, duration, etc.)
            "tyre_stints": [],    # lista de stints por piloto
            "weather": {},        # airTemp, trackTemp, rainfall, windSpeed, etc.
        }
        self.last_commentary_seen = ""
        self.last_radio_seen = ""
        self.is_running: bool = False
        self._thread: Optional[Thread] = None
        self.poll_interval = 5   # Verificar posiciones cada 5 s para datos más frescos
        self.api_calls_count = 0  # Total de llamadas al API F1 (ciclos de actualización × endpoints)

        # Load initial driver list
        self._fetch_driver_list()

    def start(self):
        if self.is_running: return
        self.is_running = True
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"F1 Live Pulse API Client started (Polling every {self.poll_interval}s)")

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("F1 Live Pulse API Client stopped")

    def get_state(self) -> Dict:
        return self.current_state

    def refresh_now(self):
        """
        Fuerza una actualización inmediata del estado desde el API,
        ignorando el intervalo de polling en background.
        Pensado para usarse justo antes de generar comentarios.
        """
        try:
            self._update_state()
        except Exception as e:
            logger.error(f"F1LivePulse forced refresh error: {e}")

    def _loop(self):
        while self.is_running:
            try:
                self._update_state()
            except Exception as e:
                logger.error(f"F1LivePulse polling error: {e}")
            time.sleep(self.poll_interval)

    def _fetch_driver_list(self):
        """Fetches the static list of drivers once."""
        try:
            res = requests.get(f"{self.base_url}/driverList", headers=self.headers, timeout=10)
            res.raise_for_status()
            drivers = res.json()
            # Format as Tla -> Info
            self.driver_list = {d["Tla"]: d for d in drivers}
        except Exception as e:
            logger.error(f"Error fetching driver list: {e}")

    def _update_state(self):
        """Fetches position and timing data, and merges it into our state dictionary."""
        # 10 endpoints por ciclo (driverPositions, timingData, liveCommentary, sessionInfo, timingStats, raceControl, teamRadio, pitStops, tyreStints, weatherData)
        self.api_calls_count += 10
        positions_data = {}
        timing_data = {}
        commentary = ""
        race_control = []

        # 1. Fetch Driver Positions
        try:
            res = requests.get(f"{self.base_url}/driverPositions", headers=self.headers, timeout=10)
            if res.status_code == 200:
                positions_data = res.json()
        except Exception as e:
            logger.error(f"driverPositions fetch error: {e}")

        # 2. Fetch Timing Data
        try:
            res = requests.get(f"{self.base_url}/timingData", headers=self.headers, timeout=10)
            if res.status_code == 200:
                timing_data = res.json()
        except Exception as e:
            logger.error(f"timingData fetch error: {e}")

        # 3. Fetch Official Commentary (Last message)
        try:
            res = requests.get(f"{self.base_url}/liveCommentary", headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, list) and len(data) > 0:
                    fetched_text = data[0].get("text", "")
                    
                    # Only send it if it's new, otherwise send empty so we don't repeat endlessly
                    if fetched_text != self.last_commentary_seen:
                        commentary = fetched_text
                        self.last_commentary_seen = fetched_text
                    else:
                        commentary = "" # It's stale
        except Exception as e:
            logger.error(f"liveCommentary fetch error: {e}")

        # 4. Fetch Meta SessionInfo (Orientación de Carrera)
        session_info = {}
        try:
            res = requests.get(f"{self.base_url}/sessionInfo", headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict):
                    session_info = data
        except Exception as e:
            logger.error(f"sessionInfo fetch error: {e}")

        # 5. Bring in TimingStats for Speed Traps
        timing_stats = {}
        try:
            res = requests.get(f"{self.base_url}/timingStats", headers=self.headers, timeout=10)
            if res.status_code == 200:
                timing_stats = res.json()
        except Exception as e:
            logger.error(f"timingStats fetch error: {e}")

        # 4. Fetch Race Control Messages
        try:
            res = requests.get(f"{self.base_url}/raceControlMessages?category=Flag", headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if "messages" in data and len(data["messages"]) > 0:
                    last_msg = data["messages"][-1]
                    race_control.append({"lap": last_msg.get("lap", 1), "msg": last_msg.get("message", "Flag")})
        except Exception as e:
            logger.error(f"raceControlMessages fetch error: {e}")

        # 6. Fetch Team Radio
        team_radio = ""
        try:
            res = requests.get(f"{self.base_url}/teamRadio", headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                # data is usually {"Captures": [{"RacingNumber": "1", "Tla": "VER"}]} or similar array depending on race status.
                # Assuming the API returns a list or dict with recent radios. For simplicity, we grab the raw text if possible.
                if data and "Captures" in data and len(data["Captures"]) > 0:
                    last_capture = data["Captures"][-1]
                    radio_tla = last_capture.get("Tla", "Driver")
                    team_radio = f"RADIO RECIENTE ({radio_tla}): Nuevo mensaje por radio detectado."
                    
                    if team_radio == self.last_radio_seen:
                        team_radio = ""
                    else:
                        self.last_radio_seen = team_radio
        except Exception as e:
            logger.error(f"teamRadio fetch error: {e}")

        # 7. Pit stops
        pit_stops = []
        try:
            res = requests.get(f"{self.base_url}/pitStops", headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                pit_stops = data.get("pitStops") or data.get("pit_stops") or []
                if not isinstance(pit_stops, list):
                    pit_stops = []
        except Exception as e:
            logger.error(f"pitStops fetch error: {e}")

        # 8. Tyre stints (puede dar 429 si no hay sesión activa)
        tyre_stints = []
        try:
            res = requests.get(f"{self.base_url}/tyreStints", headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                raw = data.get("tyreStints") or data.get("lines") or data.get("stints") or []
                tyre_stints = raw if isinstance(raw, list) else []
        except Exception as e:
            logger.debug(f"tyreStints fetch: {e}")

        # 9. Weather
        weather = {}
        try:
            res = requests.get(f"{self.base_url}/weatherData", headers=self.headers, timeout=10)
            if res.status_code == 200:
                weather = res.json()
                if not isinstance(weather, dict):
                    weather = {}
        except Exception as e:
            logger.error(f"weatherData fetch error: {e}")

        # Process and merge into current_state
        self._process_data(positions_data, timing_data, commentary, race_control, timing_stats, team_radio, session_info, pit_stops, tyre_stints, weather)

    def _process_data(self, positions_data: Dict, timing_data: Dict, commentary: str, race_control: List[Dict], timing_stats: Dict, team_radio: str, session_info: Dict, pit_stops: List = None, tyre_stints: List = None, weather: Dict = None):
        """Translates the API raw data into the format expected by the frontend and AI Engine."""
        pit_stops = pit_stops or []
        tyre_stints = tyre_stints or []
        weather = weather or {}

        if not positions_data.get("Lines"):
            # Mantener al menos weather y listas vacías para no perder datos entre sesiones
            self.current_state["pit_stops"] = pit_stops
            self.current_state["tyre_stints"] = tyre_stints
            self.current_state["weather"] = weather
            return

        lines = positions_data["Lines"]
        rn_to_tla = {str(line.get("RacingNumber", "")): line.get("Tla") for line in lines if line.get("Tla")}
        # timingData devuelve "lines" como lista; normalizar a dict por racingNumber
        raw_timing = (timing_data or {}).get("lines")
        if isinstance(raw_timing, list):
            timing_lines = {str(item.get("racingNumber", item.get("RacingNumber", ""))): item for item in raw_timing if item.get("racingNumber") is not None or item.get("RacingNumber") is not None}
        elif isinstance(raw_timing, dict):
            timing_lines = raw_timing
        else:
            timing_lines = {}

        parsed_positions = []
        current_lap = 1

        for line in lines:
            tla = line.get("Tla")
            if not tla: continue
            
            # Find driver info
            driver_info = self.driver_list.get(tla, {})
            name = ""
            if isinstance(driver_info, dict):
                name = driver_info.get("FullName", tla)
                team = driver_info.get("TeamName", "Unknown")
            else:
                name = tla
                team = "Unknown"

            # Extract current position from LapPosition array (last element is current lap)
            lap_positions = line.get("LapPosition", [])
            if not lap_positions: continue
            
            # The length of lap_positions array roughly indicates the current lap
            driver_lap = len(lap_positions)
            if driver_lap > current_lap:
                current_lap = driver_lap
                
            current_pos_str = lap_positions[-1]
            try:
                pos = int(current_pos_str)
            except:
                pos = 99
            
            # Fetch timing specifics for this driver
            # The API usually maps timing data by RacingNumber
            racing_number = str(line.get("RacingNumber", ""))
            
            gap = 0.0
            last_lap_time = "--:--"
            sectors = ["--", "--", "--"]
            pit_stops_count = 0
            drs_enabled = False
            tyre_compound = "-"
            
            # If we have timing data matching this car number
            val = timing_lines.get(racing_number) if timing_lines else None
            if val is None and timing_lines:
                for k, v in timing_lines.items():
                    if str(v.get("racingNumber") or v.get("RacingNumber") or "") == racing_number:
                        val = v
                        break
            if val is not None:
                # Position
                timing_pos_str = val.get("position") or val.get("Position")
                if timing_pos_str is not None:
                    try:
                        pos = int(timing_pos_str)
                    except (TypeError, ValueError):
                        pass
                # Gap: intervalToPositionAhead o timeDiffToPositionAhead (API usa camelCase)
                gap_str = val.get("intervalToPositionAhead") or val.get("timeDiffToPositionAhead") or val.get("TimeDiffToPositionAhead") or ""
                if isinstance(gap_str, dict):
                    gap_str = gap_str.get("Value") or gap_str.get("value") or ""
                try:
                    gap = float(str(gap_str).replace("+", "").strip())
                except (TypeError, ValueError):
                    if gap_str == "":
                        gap = 0.0
                # Last lap time: API devuelve lastLapTime (string o objeto con Value)
                lt = val.get("lastLapTime") or val.get("LastLapTime")
                if isinstance(lt, dict):
                    last_lap_time = lt.get("Value") or lt.get("value") or "--:--"
                elif lt is not None and str(lt).strip():
                    last_lap_time = str(lt).strip()
                # Overtake (ex DRS)
                drs_val = val.get("drs") or val.get("DrsState")
                drs_enabled = drs_val in [1, 8, True, "1", "8"]
                # Sectores: Sectors[] con .Value
                val_sectors = val.get("Sectors") or val.get("sectors") or []
                if len(val_sectors) >= 3:
                    sectors = [str(s.get("Value") or s.get("value") or "--") for s in val_sectors[:3]]
                comp = val.get("compound") or val.get("Compound")
                if comp is not None and str(comp).strip():
                    tyre_compound = str(comp).strip()

            parsed_positions.append({
                "position": pos,
                "tla": tla,
                "name": name,
                "team": team,
                "gap": gap,
                "last_lap_time": last_lap_time,
                "photo_url": self._generate_driver_url(name, team, tla),
                "car_url": self._generate_car_url(team),
                "tyre": tyre_compound,
                "pit_stops": pit_stops_count,
                "drs_enabled": drs_enabled,
                "sector_times": sectors,
                "RacingNumber": racing_number,
            })

        # Build grid_context with top_speed from timing_stats (keyed by RacingNumber)
        speed_by_number = {}
        if timing_stats and isinstance(timing_stats, dict) and "Lines" in timing_stats:
            for num, ts_data in timing_stats.get("Lines", {}).items():
                if not isinstance(ts_data, dict):
                    continue
                speed = 0
                if "Speeds" in ts_data:
                    for st in ts_data["Speeds"].values() if isinstance(ts_data["Speeds"], dict) else []:
                        if isinstance(st, dict) and "Value" in st:
                            try:
                                val = float(st["Value"])
                                if val > speed:
                                    speed = val
                            except (TypeError, ValueError):
                                pass
                speed_by_number[str(num)] = speed

        grid_context = []
        for p in parsed_positions:
            rn = str(p.get("RacingNumber", ""))
            grid_context.append({
                "tla": p["tla"],
                "team": p["team"],
                "name": p["name"],
                "top_speed": speed_by_number.get(rn, 0),
            })

        # Sort by position
        parsed_positions.sort(key=lambda x: x["position"])

        # Conteo de paradas por piloto (Tla o racingNumber) desde pit_stops
        pit_count_by_tla = {}
        for ps in pit_stops:
            if not isinstance(ps, dict):
                continue
            tla = ps.get("tla") or ps.get("Tla")
            if not tla:
                rn = str(ps.get("racingNumber") or ps.get("RacingNumber") or "")
                tla = rn_to_tla.get(rn)
            if tla:
                pit_count_by_tla[tla] = pit_count_by_tla.get(tla, 0) + 1
        for p in parsed_positions:
            p["pit_stops"] = pit_count_by_tla.get(p["tla"], 0)

        # Sobrescribir compuesto desde tyre_stints si viene más actualizado
        for ts in tyre_stints:
            if not isinstance(ts, dict):
                continue
            rn = str(ts.get("racingNumber") or ts.get("RacingNumber") or "")
            comp = ts.get("compound") or ts.get("Compound") or ts.get("tyre")
            if rn and comp:
                for p in parsed_positions:
                    if str(p.get("RacingNumber", "")) == rn:
                        p["tyre"] = str(comp)
                        break

        # Update state
        self.current_state = {
            "lap": current_lap,
            "positions": parsed_positions,
            "race_control": race_control,
            "live_commentary": commentary,
            "team_radio": team_radio,
            "session_info": session_info,
            "grid_context": grid_context,
            "pit_stops": pit_stops,
            "tyre_stints": tyre_stints,
            "weather": weather,
        }

    def _generate_driver_url(self, name: str, team: str, tla: str) -> str:
        first_name = name.split(" ")[0] if " " in name else name
        last_name = name.split(" ")[-1] if " " in name else name
        
        if tla == "VER": return "https://media.formula1.com/image/upload/c_fill,w_720/q_auto/v1740000000/common/f1/2025/redbullracing/maxver01/2025redbullracingmaxver01right.webp"
        if tla == "ANT": return "https://media.formula1.com/image/upload/c_fill,w_720/q_auto/v1740000000/common/f1/2026/mercedes/andant01/2026mercedesandant01right.webp"
        
        team_slug = team.lower().replace(" ", "").replace("racing", "").replace("f1team", "").replace("kick", "")
        if team_slug == "redbull": team_slug = "redbullracing"
        
        name_slug = (first_name[:3] + last_name[:3]).lower()
        return f"https://media.formula1.com/image/upload/c_fill,w_720/q_auto/v1740000000/common/f1/2026/{team_slug}/{name_slug}01/2026{team_slug}{name_slug}01right.webp"

    def _generate_car_url(self, team: str) -> str:
        team_slug = team.lower().replace(" ", "").replace("racing", "").replace("f1team", "").replace("kick", "")
        if team_slug == "audi": team_slug = "audi"
        if team_slug == "cadillac": team_slug = "cadillac"
        if team_slug == "redbull": 
            return "https://media.formula1.com/image/upload/c_lfill,w_3392/q_auto/v1740000000/common/f1/2025/redbullracing/2025redbullracingcarright.webp"
            
        return f"https://media.formula1.com/image/upload/c_lfill,w_512/q_auto/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000000/common/f1/2026/{team_slug}/2026{team_slug}carright.webp"
