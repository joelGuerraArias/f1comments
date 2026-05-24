import os
import random
import re
import requests
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def _sorted_by_position(entries: list) -> list:
    """P1 primero para TOP N; valores no numéricos van al final (orden estable)."""

    def _key(p):
        if not isinstance(p, dict):
            return (999, "")
        try:
            pos = int(p.get("position", 999))
        except (TypeError, ValueError):
            pos = 999
        tla = str(p.get("tla", "") or "")
        return (pos, tla)

    return sorted(entries, key=_key)


def _clip_radio_phrase(text: str, max_chars: int = 240) -> str:
    """Evita TTS largo si el modelo se pasa de largo; corta en último espacio."""
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def session_label(session_info: dict) -> str:
    """Devuelve etiqueta de sesion en espanol (Practica 1, Clasificacion, Sprint, Carrera, etc.).

    Combina sessionType + sessionName del API y mapea variantes comunes.
    Si no detecta nada, devuelve "Sesion".
    """
    si = session_info or {}
    name = str(si.get("sessionName") or "").strip().lower()
    stype = str(si.get("sessionType") or "").strip().lower()
    blob = f"{name} {stype}"

    if any(k in blob for k in ["fp1", "practice 1", "practica 1", "free practice 1"]):
        return "Practica 1"
    if any(k in blob for k in ["fp2", "practice 2", "practica 2", "free practice 2"]):
        return "Practica 2"
    if any(k in blob for k in ["fp3", "practice 3", "practica 3", "free practice 3"]):
        return "Practica 3"
    if "sprint qualifying" in blob or "sprint shootout" in blob:
        return "Clasificacion al Sprint"
    if "sprint" in blob:
        return "Sprint"
    if any(k in blob for k in ["qualifying", "clasificacion", "qualy", "qualifier"]):
        return "Clasificacion"
    if any(k in blob for k in ["race", "carrera"]):
        return "Carrera"
    if any(k in blob for k in ["practice", "practica", "entrenamiento"]):
        return "Practica"
    return "Sesion"

# === PARRILLA OFICIAL F1 2026 (Anti-Alucinaciones) ===
# Fuente de verdad: DeepSeek DEBE usar esta lista. Nada de temporadas anteriores.
# Lista de pilotos 2026: Albon, Alonso, Antonelli, Bearman, Bortoleto, Bottas, Colapinto, Gasly, Hadjar, Hamilton, Hulkenberg, Lawson, Leclerc, Lindblad, Norris, Ocon, Perez, Piastri, Russell, Sainz, Stroll, Verstappen.
GRID_2026 = """
REFERENCIA PILOTOS/EQUIPOS TEMPORADA 2026 — NO ES ORDEN EN PISTA NI PARRILLA DE SALIDA; solo fichas válidas (OBLIGATORIO):
- Max Verstappen        → Red Bull Racing    (Países Bajos)
- Liam Lawson           → Red Bull Racing    (Nueva Zelanda)
- Lando Norris          → McLaren            (Reino Unido)
- Oscar Piastri         → McLaren            (Australia)
- George Russell        → Mercedes           (Reino Unido)
- Kimi Antonelli        → Mercedes           (Italia)
- Charles Leclerc       → Ferrari            (Mónaco)
- Lewis Hamilton        → Ferrari            (Reino Unido)
- Alexander Albon       → Williams           (Tailandia)
- Carlos Sainz          → Williams           (España)
- Isack Hadjar          → Racing Bulls       (Francia)
- Arvid Lindblad        → Racing Bulls       (Reino Unido)
- Fernando Alonso       → Aston Martin       (España)
- Lance Stroll          → Aston Martin       (Canadá)
- Pierre Gasly          → Alpine             (Francia)
- Franco Colapinto      → Alpine             (Argentina)
- Esteban Ocon          → Haas  (¡NO Alpine!) (Francia)
- Oliver Bearman        → Haas               (Reino Unido)
- Nico Hülkenberg       → Audi  (¡NO Haas!) (Alemania)
- Gabriel Bortoleto     → Audi               (Brasil)
- Sergio Pérez          → Cadillac           (México)
- Valtteri Bottas       → Cadillac           (Finlandia)
"""

SESSION_REMINDER_EVERY = 5  # cada N comentarios se obliga a mencionar GP + sesion
STANDINGS_RECAP_EVERY = 4   # cada N comentarios Mark hace recap de vuelta + TOP 10


def _parse_used_indices(raw_text: str) -> tuple[str, list[int], list[int]]:
    """Extrae las lineas USED:[...] y USED_INFO:[...] del texto del AI.

    Devuelve (texto_limpio, ctx_nums, info_nums).
    """
    ctx_nums: list[int] = []
    info_nums: list[int] = []
    cleaned_lines: list[str] = []
    pat_info = re.compile(r"USED_INFO\s*:\s*\[([^\]]*)\]", re.IGNORECASE)
    pat_ctx = re.compile(r"USED\s*:\s*\[([^\]]*)\]", re.IGNORECASE)
    for line in raw_text.splitlines():
        m_info = pat_info.search(line)
        if m_info:
            for token in re.split(r"[\s,;]+", m_info.group(1).strip()):
                if token.isdigit():
                    info_nums.append(int(token))
            continue
        m_ctx = pat_ctx.search(line)
        if m_ctx:
            for token in re.split(r"[\s,;]+", m_ctx.group(1).strip()):
                if token.isdigit():
                    ctx_nums.append(int(token))
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip(), ctx_nums, info_nums


def generate_race_commentary(deepseek_api_key: str, race_state: dict, race_name: str = "", extra_race_info: str = "", context: str = "", previous_comments: list = None, generation_count: int = 0, return_used: bool = False) -> list:
    """
    Calls DeepSeek API to generate an analytical, dynamic commentary block 
    structured exactly as Mark: ... Maria: ...
    race_name: carrera que se está narrando (se incluye en cada prompt).
    extra_race_info: texto que los comentaristas pueden usar; se inyecta en el prompt (el caller lo pasa cada 5 comentarios).
    context: nacionalidad de pilotos, datos interesantes; se inyecta SIEMPRE en cada prompt.
    generation_count: contador de bloques generados; cada SESSION_REMINDER_EVERY se obliga a mencionar GP + sesion.
    return_used: si True, devuelve dict {segments, used_facts} en lugar de solo la lista.
    """
    if not deepseek_api_key:
        logger.warning("No DeepSeek API key provided. No fallback; returning empty commentary.")
        return []

    endpoint = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {deepseek_api_key}"
    }

    # Modo Pista: comentarios basados solo en la información de la carrera (Admin) — datos de interés, NO relato en vivo
    admin_race_info = (race_state.get("admin_race_info") or "").strip()
    if admin_race_info and not race_state.get("positions"):
        gp_name = (race_name or race_state.get("admin_race_name") or "").strip() or "Gran Premio"
        pista_opening = random.choice([
            "Empieza con un dato histórico del circuito.",
            "Abre mencionando a un piloto y su nacionalidad.",
            "Arranca con una curiosidad sobre el diseño de la pista.",
            "Comienza con una referencia al clima esperado para la sesión.",
            "Empieza hablando de un duelo entre dos pilotos o equipos.",
            "Abre con una anécdota del último ganador de este GP.",
            "Arranca con energía hablando de lo que se espera de un rookie.",
            "Comienza mencionando un récord o hito que podría romperse.",
            "Empieza con un dato sobre la ciudad o país sede del GP.",
            "Abre destacando un cambio de equipo de algún piloto esta temporada.",
        ])
        pista_prompt = f"""Eres un dúo de comentaristas de F1 (Mark y Maria). Hay DOS voces.

ESTILO DE APERTURA PARA ESTE COMENTARIO (varía siempre):
→ {pista_opening}

CARRERA: {gp_name}

TEXTO CON DATOS DE LA CARRERA (Mark y Maria pueden usarlo, pero sin repetir el mismo dato):
{admin_race_info}

=== REFERENCIA PILOTOS 2026 (solo si nombráis pilotos válidos — no es orden en pista) ===
{GRID_2026}

PROHIBIDO (nunca menciones esto):
- Que el circuito estuvo ausente, ni "ausencia forzada" del circuito de China (o de cualquier GP). No hables de ausencias del calendario.
- Repetir muchas veces "bienvenidos al GP de...". Máximo una mención natural, sin insistir.
- Tiempos de vuelta o récords en minutos/segundos (se suelen citar mal; no los des).
- Que Piastri es el vigente campeón del mundo. Piastri es el último ganador del GP de China, no el campeón.
- Que este circuito es el más caro ni comparativas de coste de circuitos.
- "Analizando la telemetría" o variaciones. María NO empieza con "Analizando..." ni "Si miramos..." ni "La telemetría...".
- "La pista con forma de ocho" o "el icónico circuito en forma de ocho" o cualquier referencia a "forma de ocho".
- "Sí Mark" como inicio de María.

REGLAS ESTRICTAS:
1. NO narres que la carrera se ha iniciado ni que está en vivo. Este bloque es solo DATOS INTERESANTES para la carrera: historia del circuito, cuándo se creó, últimos ganadores, anécdotas, condiciones de pista, etc.
2. USA ÚNICAMENTE datos que aparezcan en los textos de arriba. Si no está escrito, NO lo inventes. Si repites ideas, reformula con otros datos concretos.
3. AMBOS narradores pueden usar tanto el TEXTO CON DATOS como el CONTEXTO (datos numerados de abajo) para enriquecer su frase. PERO: NUNCA pueden usar el mismo dato en el mismo bloque. Si Mark elige un año/nombre, Maria toma OTRO distinto. Tampoco repitan datos de bloques anteriores.
4. MARK (siempre primero): UNA sola frase corta (máximo ~22 palabras), tono apasionado. Sin tiempos de vuelta.
5. MARÍA (siempre segundo): UNA sola frase corta distinta a Mark (máximo ~22 palabras). Sin tiempos de vuelta.
6. NÚMEROS CLAROS: Si mencionas cualquier número decimal, simplifícalo: solo primer dígito, punto, y dos dígitos más. Ej: "1.31" en vez de "1:31.755", "3.84" en vez de "3.847". NUNCA números largos.
7. Formato de salida exactamente:
Mark:
[tu texto]
Maria:
[tu texto]

GENERA el comentario usando solo datos del texto de arriba y respetando la lista PROHIBIDO."""
        if context and context.strip():
            pista_prompt += f"""

=== CONTEXTO — DATOS INTERESANTES (cualquiera de los dos narradores puede usarlo) ===
Lista numerada de datos curiosos / hitos / anecdotas del GP. Mark y Maria pueden tomar de aqui o del TEXTO CON DATOS de arriba, pero nunca el mismo dato en el mismo bloque.

{context.strip()}"""

        # Cada N comentarios, recordar GP y tipo de sesion (en pista el tipo no llega del API; usamos texto Admin si lo dice)
        if generation_count > 0 and (generation_count % SESSION_REMINDER_EVERY) == 0 and gp_name:
            pista_prompt += f"""

=== RECORDATORIO DE CONTEXTO (OBLIGATORIO en este bloque) ===
Mark debe mencionar NATURALMENTE el {gp_name} en una sola frase corta (si el texto de arriba indica si es practica, clasificacion o carrera, ubicalo asi; si no, solo el nombre del GP). Sin sonar a anuncio."""

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Eres un motor de narración de IA para F1. Respondes SIEMPRE solo en este formato:\nMark:\n[texto]\n\nMaria:\n[texto]"},
                {"role": "user", "content": pista_prompt}
            ],
            "temperature": 0.85,
            "max_tokens": 380
        }
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=18.0)
            response.raise_for_status()
            raw_text = response.json()["choices"][0]["message"]["content"]
            segments = parse_commentary(raw_text)
            for seg in segments:
                seg["text"] = _clip_radio_phrase(seg.get("text", ""), 300)
            return segments
        except Exception as e:
            logger.error(f"DeepSeek API Error (pista): {e}")
            return []

    lap = race_state.get("lap", 1)
    total_laps = int(race_state.get("total_laps") or 0) or 70
    positions = _sorted_by_position(race_state.get("positions") or [])
    top_3 = positions[:3]
    grid_context = race_state.get("grid_context", [])[:6]
    session_info = race_state.get("session_info", {})
    meeting_name = session_info.get("meetingOfficialName", "F1 Grand Prix")
    session_name = session_info.get("sessionName", "Race")
    track_status = session_info.get("trackStatus", "AllClear")
    race_control = race_state.get("race_control", [])
    rc_tail = race_control[-2:] if isinstance(race_control, list) and len(race_control) > 2 else race_control
    rc_msgs = " | ".join([rc.get("msg", "") for rc in rc_tail]) if rc_tail else "Ningún incidente reciente"
    live_commentary = race_state.get("live_commentary", "")
    team_radio = race_state.get("team_radio", "")
    has_fresh_radio = bool(team_radio and team_radio.strip())
    has_fresh_commentary = bool(live_commentary and live_commentary.strip())
    weather = race_state.get("weather") or {}
    pit_stops_list = race_state.get("pit_stops") or []
    tyre_stints_list = race_state.get("tyre_stints") or []

    # Detectar si es sesión de práctica (no queremos que se mencionen números de vuelta)
    session_name_lower = str(session_name or "").lower()
    is_practice = any(
        key in session_name_lower
        for key in ["practice", "práctica", "fp1", "fp2", "fp3", "entrenamiento"]
    )

    # --- BLOQUE 1: DATOS PARA MARK (snapshot mínimo = menos latencia y más alineado con la UI) ---
    positions_for_mark = "\n".join([
        f"P{p.get('position', 0)} - {p.get('name', p.get('tla', ''))} ({p.get('team', '')}) | Gap +{p.get('gap', 0)}s | Últ: {p.get('last_lap_time', '--')} | Comp: {p.get('tyre', '-')}"
        for p in top_3
    ])
    air_temp = weather.get("airTemp") or weather.get("air_temp")
    track_temp = weather.get("trackTemp") or weather.get("track_temp")
    rainfall = weather.get("rainfall", 0)
    weather_str = f"Temperatura aire: {air_temp}°C | Pista: {track_temp}°C | Lluvia: {rainfall}%" if (air_temp is not None or track_temp is not None) else "Sin datos de tiempo"
    gp_display = (race_name and race_name.strip()) or meeting_name

    clock_remaining = str(session_info.get("clockRemaining") or "").strip()
    clock_is_finished = (clock_remaining == "00:00:00") or any(
        s in str(session_info.get("sessionStatusStarted") or "").lower() for s in ["finish", "finalis"]
    )

    if is_practice:
        if clock_remaining and not clock_is_finished:
            first_line = f"SESIÓN DE PRÁCTICA en curso (faltan {clock_remaining}) – no cites vueltas; menciona TOP 3 actual y, si encaja natural, lo que queda de sesión."
        elif clock_is_finished:
            first_line = "SESIÓN DE PRÁCTICA FINALIZADA – no cites vueltas; resume el TOP 3 final."
        else:
            first_line = "SESIÓN DE PRÁCTICA – no cites número de vuelta; solo situación actual TOP 3."
    else:
        # Para qualy/sprint usamos vuelta + reloj cuando esté
        clock_note = f" | Tiempo restante de sesión: {clock_remaining}" if (clock_remaining and not clock_is_finished) else ""
        first_line = f"VUELTA ACTUAL: {lap} de {total_laps} (si total_laps es desconocido, di solo la vuelta actual).{clock_note}"

    leader_line = ""
    if top_3:
        p1 = top_3[0]
        leader_line = (
            f"\nLÍDER EN ESTE SNAPSHOT (único P1 en pista; no inventes otro): "
            f"{p1.get('name') or p1.get('tla')} ({p1.get('tla')}) — {p1.get('team', '')}. "
            f"El orden alfabético o en la lista REFERENCIA 2026 arriba NO indica clasificación.\n"
        )

    mark_context = f"""{first_line}{leader_line}
CARRERA / SESIÓN: {gp_display}
Sesión: {session_name} | Pista: {track_status}
TIEMPO: {weather_str}
ÚLTIMO AVISO DIRECCIÓN DE CARRERA (priorízalo si es relevante):
{rc_msgs}

TOP 3 AHORA (datos exactos; no inventes otros pilotos):
{positions_for_mark}"""

    # --- BLOQUE 2: DATOS PARA MARÍA (análisis: sectores, velocidades, Overtake, reporte oficial, radio) ---
    def _sector(p, i):
        s = p.get("sector_times") or ["-", "-", "-"]
        return s[i] if i < len(s) else "-"
    telemetry_detail = "\n".join([
        f"P{p.get('position', 0)} {p.get('tla', '')} | Comp {p.get('tyre', '-')} | S1={_sector(p,0)} S2={_sector(p,1)} S3={_sector(p,2)} | Overtake={p.get('drs_enabled', False)}"
        for p in top_3
    ])
    speeds_str = "\n".join([
        f"{g.get('tla', '')} ({g.get('team', '')}): {g.get('top_speed', 0)} km/h en tramo de velocidad"
        for g in grid_context if g.get("top_speed")
    ]) or "Sin datos de velocidad tramo en este momento."
    pit_stops_str = ""
    if pit_stops_list:
        pit_stops_str = "PARADAS EN BOXES (recientes): " + "; ".join([
            f"{ps.get('tla', ps.get('Tla', ''))} vuelta {ps.get('lap', ps.get('Lap', '?'))} ({ps.get('duration', ps.get('Duration', ''))})"
            for ps in (pit_stops_list[-5:] if len(pit_stops_list) > 5 else pit_stops_list)
            if isinstance(ps, dict)
        ][:5]) + "\n"
    tyre_stints_str = ""
    if tyre_stints_list and isinstance(tyre_stints_list[0], dict):
        tyre_stints_str = "STINTS DE NEUMÁTICOS (estrategia): " + "; ".join([
            f"#{ts.get('racingNumber', ts.get('RacingNumber', ''))} {ts.get('compound', ts.get('Compound', '-'))}"
            for ts in tyre_stints_list[:10]
        ]) + "\n"
    # Decide qué fuente narrativa usar cuando el commentary oficial está vacío
    if has_fresh_commentary:
        narration_source = f"REPORTE OFICIAL (live commentary): {live_commentary}"
    elif has_fresh_radio:
        narration_source = f"TEMA ESPECIAL – usa esto como eje de tu análisis:\n{team_radio}\n(El commentary oficial está quieto, así que María debe comentar este radio y explicar qué revela sobre el estado del coche o la estrategia.)"
    else:
        narration_source = "Sin commentary oficial ni radio fresco. María: una frase con sectores o velocidad del TOP 3, sin decir 'telemetría'."

    maria_context = f"""TELEMETRÍA (TOP 3):
{telemetry_detail}

{pit_stops_str}{tyre_stints_str}
VELOCIDADES MÁXIMAS EN TRAMO (usa en tu análisis):
{speeds_str}

{narration_source}"""

    opening_style = random.choice([
        "Una interjección de una sola palabra y al líder.",
        "Nombre del P2 y la brecha con el líder.",
        "Estado de pista o mensaje de dirección de carrera.",
        "Neumático del líder y si aguanta.",
        "Un piloto del TOP 3 por nacionalidad (breve).",
        "'¡Atención!' + quien lidera.",
    ])

    prompt = f"""
Eres un dúo de comentaristas de F1 en vivo (Mark y Maria). Ritmo de RADIO: frases MUY breves, nada de monólogos.

IMPORTANTE: Los datos de abajo son un snapshot ÚNICO en el instante actual. No inventes posiciones ni pilotos fuera del TOP 3 mostrado salvo que aparezcan en race control o radio.

=== DATOS PARA MARK (PRIMERA VOZ – RELATO) — ORDEN EN PISTA AQUÍ ===
{mark_context}

=== DATOS PARA MARÍA (SEGUNDA VOZ – ANÁLISIS) ===
{maria_context}

=== REFERENCIA PILOTOS 2026 (equipos; NO es clasificación en pista) ===
{GRID_2026}
REGLA ABSOLUTA: BAJO NINGÚN CONCEPTO uses equipos de temporadas anteriores.
Quién va primero/segundo/tercero EN CARRERA ya está fijado arriba en TOP 3 / líder; este listado solo valida qué pilotos existen en 2026.
Si un piloto no aparece en la lista de referencia, NO lo inventes. Usa solo los datos que se te dan.

=== VARIEDAD (sin alargar el texto) ===
Para ESTE bloque, guía de apertura (solo una frase corta en total por voz):
→ {opening_style}

- No repitas muletillas en cada corte. Nacionalidad solo si cabe en la misma frase breve.

=== FRASES PROHIBIDAS (NUNCA las uses) ===
- "Analizando la telemetría" o cualquier variación ("la telemetría no miente", "la telemetría muestra", "si miramos la telemetría")
- "La pista de Suzuka con forma de ocho" o "el icónico circuito en forma de ocho" o cualquier referencia a "forma de ocho"
- "Sí Mark" como inicio de frase de María
- "¡Esto está al rojo vivo!"
- María NUNCA debe empezar diciendo "Analizando..." ni "Si miramos..." ni "La telemetría...". Debe ir directo al dato o al piloto.

=== REGLAS ESTRICTAS (BREVES SIEMPRE) ===
1. MARK (primero): UNA sola frase corta (máximo ~22 palabras). Tono vivo estilo Latino.
   - Carrera/sprint: menciona la vuelta en esa única frase si aplica.
   - Qualifying: menciona al líder o un tiempo de forma muy breve (sin extenderte).
   - Práctica: solo situación TOP 3.
   No repitas datos que dará María (sectores, velocidades punta).
2. MARÍA (segundo): UNA sola frase corta (máximo ~22 palabras), distinta a Mark. Un dato: sector, velocidad tramo, estrategia/neumático u Overtake. Nada de "telemetría" ni "si analizamos".
3. LONGITUD: Prohibido pasar de una frase por voz. Si los datos son pobres, dilo en pocas palabras sin inventar.
4. EQUIPOS / CLASIFICACIÓN: La referencia 2026 abajo solo valida nombres y equipos. El orden en pista es EXACTAMENTE P1, P2, P3 del bloque TOP 3 en DATOS PARA MARK y la línea LÍDER; no asumas otro orden aunque un piloto aparezca antes en la referencia.
5. NÚMEROS: Evita leer tiempos largos; si citas gap, di "tres segundos" o "nueve décimas", redondea natural. Velocidades en entero ("trescientos diez por hora").
6. Salida exactamente:
Mark:
[una frase corta]
Maria:
[una frase corta]

"""
    # Ambos narradores tienen acceso a contexto y race_info como ENRIQUECIMIENTO sobre los datos
    # del API. Ninguno reemplaza al otro: la accion en pista sigue siendo la base y los datos del
    # Admin son la "pincelada" historica/curiosa para tejer en la frase. race_info se inyecta cada
    # SESSION_REMINDER_EVERY bloques porque suele ser un parrafo largo.
    inject_race_info = (
        bool(extra_race_info and extra_race_info.strip())
        and generation_count > 0
        and (generation_count % SESSION_REMINDER_EVERY) == 0
    )
    has_admin_data = bool((context and context.strip()) or inject_race_info)
    if has_admin_data:
        prompt += "\n=== DATOS DEL ADMIN (USO EXCLUSIVO DE MARIA) ===\n"
        prompt += (
            "Estos son datos curiosos / historicos del GP cargados por el Admin.\n\n"
            "REGLA DE REPARTO ESTRICTA:\n"
            "- MARK NO usa NUNCA estos datos. Mark narra UNICAMENTE lo que esta sucediendo en pista "
            "ahora mismo segun el API: posiciones, gaps, sectores, velocidades, banderas, radio, neumaticos, "
            "pit stops, incidentes. Su frase NO debe contener años historicos, nombres de pilotos antiguos, "
            "anecdotas del circuito, ni referencias del Admin. Si lo intenta, ROMPE LA REGLA.\n"
            "- MARIA es la UNICA que aporta UN dato del Admin en su frase, COMBINADO con un detalle tecnico "
            "del API (sector, neumatico, velocidad, gap, posicion). Estructura tipica de Maria: "
            "[detalle tecnico API] + [UN dato del Admin]. Ejemplo: 'Antonelli con un sector 1 de 23.3, "
            "y aqui en 2007 Hamilton consiguio su primera victoria en F1.'\n"
            "- Maria NO repite un dato ya usado en COMENTARIOS ANTERIORES.\n"
            "- UNICA excepcion donde Maria puede saltar el dato del Admin: incidente o mensaje de race "
            "control prioritario que ocupa toda su frase.\n"
        )
        if inject_race_info:
            prompt += (
                "- ESTE BLOQUE TIENE PRIORIDAD ESPECIAL: cada " + str(SESSION_REMINDER_EVERY) + " comentarios se "
                "inyecta INFORMACION DE LA CARRERA. Cuando aparezca, MARIA DEBE elegir su dato de la lista "
                "INFORMACION DE LA CARRERA (no del CONTEXTO). En este bloque la fuente OBLIGATORIA para Maria "
                "es INFORMACION DE LA CARRERA. El CONTEXTO se ignora SOLO en este bloque.\n"
            )
        prompt += "\n"
        if context and context.strip():
            prompt += f"""--- CONTEXTO (lista numerada; SOLO Maria cita UNO; nunca repetir) ---
{context.strip()}

"""
        if inject_race_info:
            prompt += f"""--- INFORMACION ADICIONAL DE LA CARRERA (lista numerada; SOLO Maria cita UNO en este bloque cada {SESSION_REMINDER_EVERY} comentarios; nunca repetir) ---
{extra_race_info.strip()}

"""
    if previous_comments:
        prev_text = "\n".join([f"- {c[:80]}" for c in previous_comments[-3:]])
        prompt += f"""
=== COMENTARIOS ANTERIORES (NO repitas; otra imagen de carrera) ===
{prev_text}

"""

    # Cada N comentarios obligar a contextualizar la sesion (Practica 1, Clasificacion, Sprint, Carrera).
    session_lbl = session_label(session_info)
    gp_raw = (race_name and race_name.strip()) or meeting_name or ""
    # Limpiar prefijos largos tipo "FORMULA 1 ... GRAND PRIX ..." para que el AI lo diga natural.
    gp_for_reminder = (
        gp_raw.replace("FORMULA 1 ", "")
              .replace("Formula 1 ", "")
              .replace("FORMULA1 ", "")
              .strip()
    )
    if generation_count > 0 and (generation_count % SESSION_REMINDER_EVERY) == 0 and gp_for_reminder:
        prompt += f"""
=== RECORDATORIO DE CONTEXTO (OBLIGATORIO en este bloque) ===
Mark debe abrir mencionando NATURALMENTE que estamos en la {session_lbl} del {gp_for_reminder} (variando la forma exacta, sin sonar a anuncio). Mark sigue solo con la accion en pista, NO inserta dato historico. Maria sigue con su analisis breve y aporta UN dato historico del Admin.

"""

    # Cada STANDINGS_RECAP_EVERY bloques Mark da un recap del TOP 10 + vuelta/tiempo de sesion.
    is_recap_block = generation_count > 0 and (generation_count % STANDINGS_RECAP_EVERY) == 0
    if is_recap_block:
        top_10 = positions[:10]
        top_10_str = ", ".join([
            f"P{p.get('position', '?')} {(p.get('name') or p.get('tla') or '').split()[-1].upper()}"
            for p in top_10
        ]) or "sin datos suficientes"
        if is_practice:
            time_line = (
                f"quedan {clock_remaining} de la {session_lbl.lower()}"
                if clock_remaining and not clock_is_finished
                else f"{session_lbl} finalizada"
            )
        else:
            time_line = f"vuelta {lap}{f' de {total_laps}' if total_laps else ''}"
            if clock_remaining and not clock_is_finished:
                time_line += f", quedan {clock_remaining}"

        prompt += f"""
=== RECAP DE POSICIONES (cada {STANDINGS_RECAP_EVERY} comentarios — REGLA QUE SUSTITUYE LAS REGLAS DE MARK) ===
ESTE bloque NO sigue el formato "una frase corta de Mark". En su lugar Mark hace un RECAP COMPLETO obligatorio.

INSTRUCCIONES PARA MARK (este bloque):
1. ABRE con la situacion temporal exactamente: "{time_line}".
2. ENUMERA LOS DIEZ pilotos del TOP 10 en orden, mencionando el APELLIDO de cada uno. Es OBLIGATORIO nombrar a los DIEZ; no resumir, no agrupar diciendo "los Mercedes uno-dos" sin nombres, no decir "y atras los demas".
3. Tono de comentarista de TV haciendo un recap fluido (puedes usar "primero X, segundo Y, tercero Z..." o "lidera X, le sigue Y, completa el podio Z, despues vienen W, V, U...").
4. Mark puede usar HASTA 70 palabras este bloque (excepcion al limite habitual). Mark NO inserta dato del Admin en este bloque para no saturar.

ORDEN EXACTO DEL TOP 10 (apellidos en mayuscula; usalos tal cual):
{top_10_str}

INSTRUCCIONES PARA MARIA (este bloque):
- UNA sola frase corta como siempre (max ~22 palabras).
- AÑADE UN dato del Admin (CONTEXTO o INFORMACION ADICIONAL) que NO haya mencionado Mark + opcionalmente un detalle tecnico (sector / velocidad / neumatico del lider o del piloto que se mueve).

"""

    if has_admin_data:
        prompt += """GENERA AHORA el comentario. Debe ser DIFERENTE a los anteriores.
ESTRUCTURA POR VOZ:
- MARK: solo accion en pista del API (posiciones, gaps, sectores, velocidades, banderas, radio, neumaticos, incidentes). PROHIBIDO citar años, pilotos antiguos o anecdotas del Admin.
- MARIA: [detalle tecnico del API] + [UN dato del Admin distinto a los ya usados antes].
"""
        if inject_race_info:
            prompt += (
                "PRIORIDAD EN ESTE BLOQUE: Maria toma su dato de INFORMACION DE LA CARRERA "
                "(no del CONTEXTO). Despues escribe USED_INFO:[<numero>] con el item de "
                "INFORMACION DE LA CARRERA que cito, y USED:[] vacio.\n"
            )
    else:
        prompt += """GENERA AHORA el comentario para los datos actuales. Debe ser DIFERENTE a los anteriores.
"""

    if (context and context.strip()) or inject_race_info:
        traceability = "\n=== TRACEABILIDAD DE DATOS (OBLIGATORIO al final) ===\n"
        traceability += "Despues de Mark y Maria, en LINEAS NUEVAS al final, escribe EXACTAMENTE:\n"
        if context and context.strip():
            traceability += "USED:[<numeros del CONTEXTO que MARIA cito; vacio si ninguno>]\n"
        if inject_race_info:
            traceability += "USED_INFO:[<numeros de INFORMACION DE LA CARRERA que MARIA cito; vacio si ninguno>]\n"
        traceability += (
            "Ejemplo si Maria uso CONTEXTO 7 e INFORMACION 3:\n"
            "  USED:[7]\n"
            "  USED_INFO:[3]\n"
            "Solo Maria puede citar datos del Admin. Mark NO cita datos numerados. "
            "Si por incidente/race control no se uso ningun dato, escribe la(s) linea(s) con corchetes vacios.\n"
        )
        prompt += traceability

    if is_recap_block:
        system_msg = (
            "Eres narración F1 en vivo. Formato:\nMark:\n[recap del TOP 10 con los DIEZ apellidos en orden, hasta 70 palabras]\n\nMaria:\n[una frase corta de enriquecimiento]\n\nUSED:[numeros]\nUSED_INFO:[numeros]"
        )
        max_tokens_use = 520
    else:
        system_msg = (
            "Eres narración F1 en vivo. SOLO formato:\nMark:\n[una frase corta]\n\nMaria:\n[una frase corta]\n\nUSED:[numeros]\nUSED_INFO:[numeros]\nSin párrafos largos."
        )
        max_tokens_use = 320

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.82,
        "max_tokens": max_tokens_use
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=18.0)
        response.raise_for_status()
        result = response.json()
        raw_text = result["choices"][0]["message"]["content"]
        logger.info(f"DeepSeek raw response:\n{raw_text}")
        cleaned_text, used_facts, used_info = _parse_used_indices(raw_text)
        if used_facts or used_info:
            logger.info(f"AI declaro USED:{used_facts} USED_INFO:{used_info}")
        segments = parse_commentary(cleaned_text)
        for seg in segments:
            # En bloques recap Mark puede ser largo (TOP 10); permitimos hasta 600 chars solo a Mark.
            if is_recap_block and seg.get("narrator") == "Mark":
                seg["text"] = _clip_radio_phrase(seg.get("text", ""), 600)
            else:
                seg["text"] = _clip_radio_phrase(seg.get("text", ""))
        logger.info(f"Parsed {len(segments)} segments: {[s['narrator'] for s in segments]}")
        if return_used:
            return {"segments": segments, "used_facts": used_facts, "used_info_facts": used_info}
        return segments
    except Exception as e:
        logger.error(f"DeepSeek API Error: {e}")
        if return_used:
            return {"segments": [], "used_facts": [], "used_info_facts": []}
        return []


def parse_commentary(text: str) -> list:
    """
    Parses the 'Mark: ... Maria: ...' text into structured segments.
    Handles various formats DeepSeek might return:
    - 'Mark:' on its own line followed by text
    - 'Mark: text all on the same line'
    - With or without ** bold markers
    """
    segments = []
    current_narrator = None
    current_text = []

    for line in text.split('\n'):
        # Strip markdown bold/italic markers and whitespace
        clean = line.strip().lstrip('*').rstrip('*').strip()
        if not clean:
            continue

        # Match narrator labels, case-insensitive, with optional ** bold
        lower = clean.lower()

        if lower.startswith("mark:"):
            # Save previous segment
            if current_narrator and current_text:
                segments.append({"narrator": current_narrator, "text": " ".join(current_text).strip()})
            current_narrator = "Mark"
            rest = clean[5:].strip().lstrip('*').strip()
            current_text = [rest] if rest else []

        elif lower.startswith("maria:"):
            # Save previous segment
            if current_narrator and current_text:
                segments.append({"narrator": current_narrator, "text": " ".join(current_text).strip()})
            current_narrator = "Maria"
            rest = clean[6:].strip().lstrip('*').strip()
            current_text = [rest] if rest else []

        else:
            if current_narrator:
                current_text.append(clean)

    # Save final segment
    if current_narrator and current_text:
        segments.append({"narrator": current_narrator, "text": " ".join(current_text).strip()})

    # If parsing found fewer than 2 narrators, log warning (segments may be incomplete)
    narrators_found = {s["narrator"] for s in segments}
    if len(narrators_found) < 2:
        logger.warning(f"Parser only found narrators: {narrators_found}. Raw text may not have both speakers.")

    return segments
