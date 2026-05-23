"""
Llama a cada endpoint de F1 Live Pulse API y devuelve descripción + estructura de respuesta.
Sirve para documentar qué hace cada uno y cómo estructurar los datos.
"""
import requests
from typing import Any, Dict, List, Optional, Tuple

BASE_URL = "https://f1-live-pulse.p.rapidapi.com"

# Definición de cada endpoint: nombre, descripción, path y params opcionales
ENDPOINTS = [
    {
        "id": "driverList",
        "path": "/driverList",
        "params": None,
        "description": "Lista estática de todos los pilotos de la temporada. Incluye Tla (ej. VER), FullName, RacingNumber, TeamName. Se usa para mapear número de coche → nombre y equipo.",
        "use_in_app": "Mapeo Tla → nombre/equipo al procesar posiciones y timing.",
    },
    {
        "id": "driverPositions",
        "path": "/driverPositions",
        "params": None,
        "description": "Posición por vuelta de cada coche. 'Lines' es un array por piloto con LapPosition[] (posición en cada vuelta; el último valor es la posición actual) y RacingNumber, Tla.",
        "use_in_app": "Obtener posición actual y estimar vuelta actual (longitud de LapPosition).",
    },
    {
        "id": "timingData",
        "path": "/timingData",
        "params": None,
        "description": "Datos de timing por coche (clave = RacingNumber): Position, TimeDiffToPositionAhead (gap), LastLapTime, Sectors[], DrsState. Complementa driverPositions.",
        "use_in_app": "Gap al líder, última vuelta, sectores S1/S2/S3, estado Overtake.",
    },
    {
        "id": "timingStats",
        "path": "/timingStats",
        "params": None,
        "description": "Estadísticas de timing por coche (clave = RacingNumber). Incluye 'Speeds' con valores de tramo de velocidad (speed trap). Sirve para velocidad máxima en recta.",
        "use_in_app": "Velocidad máxima en tramo para el análisis (María) en comentarios.",
    },
    {
        "id": "sessionInfo",
        "path": "/sessionInfo",
        "params": None,
        "description": "Metadatos de la sesión: meetingOfficialName (ej. Australian Grand Prix), sessionName (Race/Qualifying...), trackStatus (AllClear, Yellow, etc.).",
        "use_in_app": "Contexto de carrera para Mark (nombre GP, estado pista).",
    },
    {
        "id": "liveCommentary",
        "path": "/liveCommentary",
        "params": None,
        "description": "Comentario oficial en vivo. Array de mensajes con 'text', 'title', 'subtitle'. Suele usarse el más reciente (índice 0) como reporte oficial.",
        "use_in_app": "Reporte oficial para María en el análisis (incidentes, estado pista).",
    },
    {
        "id": "raceControlMessages",
        "path": "/raceControlMessages",
        "params": {"category": "Flag"},
        "description": "Mensajes de dirección de carrera. Con category=Flag devuelve banderas (Green, Yellow, Red, VSC, etc.). Estructura: messages[] con lap, message.",
        "use_in_app": "Banderas y avisos para Mark en el relato (vuelta + posiciones + banderas).",
    },
    {
        "id": "teamRadio",
        "path": "/teamRadio",
        "params": None,
        "description": "Capturas de radio equipo. Suele ser un objeto con 'Captures' (array de mensajes recientes con RacingNumber, Tla, etc.). No siempre incluye texto transcrito.",
        "use_in_app": "Aviso de 'radio reciente' para María si hay actividad.",
    },
]


def _truncate_for_sample(obj: Any, max_list: int = 3, max_str: int = 120) -> Any:
    """Recorta listas largas y strings para mostrar estructura sin saturar."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_truncate_for_sample(x, max_list, max_str) for x in obj[:max_list]]
    if isinstance(obj, dict):
        return {k: _truncate_for_sample(v, max_list, max_str) for k, v in obj.items()}
    if isinstance(obj, str) and len(obj) > max_str:
        return obj[:max_str] + "..."
    return obj


def _describe_structure(obj: Any) -> Any:
    """Describe solo las claves/estructura (tipos) sin datos sensibles."""
    if obj is None:
        return None
    if isinstance(obj, list):
        if len(obj) == 0:
            return []
        return [_describe_structure(obj[0])] if obj else []
    if isinstance(obj, dict):
        return {k: _describe_structure(v) for k, v in obj.items()}
    t = type(obj).__name__
    if t == "str":
        return "<string>"
    if t in ("int", "float", "bool"):
        return f"<{t}>"
    return obj


def fetch_one(base_url: str, headers: dict, path: str, params: Optional[dict]) -> Tuple[Optional[dict], Optional[str]]:
    """Hace GET a un endpoint; devuelve (data, error)."""
    url = base_url.rstrip("/") + path
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=10)
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)


def explore_all_endpoints(api_key: str) -> List[Dict]:
    """Llama a cada endpoint y devuelve lista con descripción, estructura y muestra."""
    headers = {
        "x-rapidapi-host": "f1-live-pulse.p.rapidapi.com",
        "x-rapidapi-key": api_key,
    }
    results = []
    for ep in ENDPOINTS:
        data, err = fetch_one(BASE_URL, headers, ep["path"], ep["params"])
        entry = {
            "endpoint": ep["id"],
            "path": ep["path"],
            "params": ep["params"],
            "description": ep["description"],
            "use_in_app": ep["use_in_app"],
            "status": "ok" if err is None else "error",
            "error": err,
        }
        if data is not None:
            entry["structure"] = _describe_structure(data)
            entry["sample"] = _truncate_for_sample(data, max_list=2, max_str=200)
            if isinstance(data, dict) and "Lines" in data and isinstance(data["Lines"], list):
                # Para driverPositions/timingData mostrar un elemento de Lines
                entry["sample_lines_item"] = _truncate_for_sample(data["Lines"][0], max_list=5, max_str=80) if data["Lines"] else None
            if isinstance(data, list) and len(data) > 0:
                entry["sample_first_item"] = _truncate_for_sample(data[0], max_list=5, max_str=150)
        results.append(entry)
    return results
