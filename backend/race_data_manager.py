"""Gestor del archivo `race_data.md` (datos del Admin para narracion).

Este modulo es la unica fuente de verdad de los datos que se inyectan a los
comentaristas. Hay DOS pools independientes, ambos como listas numeradas con
tracking de "ya usados":

- INFORMACION DE LA CARRERA (race_info)  -> se inyecta cada N bloques (5 por defecto).
- CONTEXTO (context)                      -> se inyecta en cada bloque.

Reglas:
- Solo Maria los usa (ver `ai_engine.py`).
- Maria nunca repite un item ya usado.
- Cuando un pool se agota, deja de inyectarse y la narracion sigue solo con API.
- `race_data.md` se crea al arrancar la app si no existe (sembrado desde
  `admin_config.json` o template por defecto).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
MD_PATH = BASE_DIR / "race_data.md"
STATE_PATH = BASE_DIR / "race_data_state.json"

DEFAULT_MD = """# Datos de la carrera para Mark y Maria

Este archivo lo gestiona F1COMMENTS. Puedes editarlo a mano: las dos secciones
son las que se inyectan a Maria (Mark solo narra lo que pasa en pista).

- Si vacias una lista, ese bloque deja de inyectarse.
- Cuando un item se "usa", se marca y no vuelve a salir.
- Si quieres reiniciar el contador de usados, llama a POST /api/race-data/reset.

**Carrera:** (sin definir)

## Información de la carrera (lista numerada)

> Parrafos extendidos / contexto historico. Maria usa UNO cada 5 comentarios sin repetir.

(sin datos)

## Contexto (lista numerada)

> Datos curiosos / hitos puntuales. Maria usa UNO en cada bloque sin repetir.

(sin datos)
"""


def _split_paragraph_to_items(text: str) -> List[str]:
    """Divide un parrafo continuo en oraciones-item para una lista numerada.

    - Corta por `. `, `! `, `? ` (al final de oracion).
    - Filtra fragmentos muy cortos o que sean solo notas tipo `[ 1 ]`.
    - Limpia espacios y citas tipo `[ 1 ]`.
    """
    if not text or not text.strip():
        return []
    cleaned = re.sub(r"\[\s*\d+\s*\]", "", text)
    raw_parts = re.split(r"(?<=[.!?])\s+", cleaned.strip())
    items: List[str] = []
    for part in raw_parts:
        s = part.strip()
        if len(s) < 25:
            continue
        if not s.endswith(('.', '!', '?')):
            s = s + '.'
        items.append(s)
    return items


def _items_to_markdown(items: List[str]) -> str:
    if not items:
        return "(sin datos)"
    return "\n".join(f"{i + 1}. {it}" for i, it in enumerate(items))


def ensure_md_exists(seed_admin_config: dict | None = None) -> None:
    """Crea `race_data.md` si no existe; lo siembra desde admin_config.json si tiene contenido."""
    if MD_PATH.exists():
        return
    if seed_admin_config and (
        (seed_admin_config.get("race_info") or "").strip()
        or (seed_admin_config.get("context") or "").strip()
    ):
        write_md_from_admin(seed_admin_config)
        logger.info("race_data.md creado desde admin_config.json")
    else:
        MD_PATH.write_text(DEFAULT_MD, encoding="utf-8")
        logger.info("race_data.md creado con plantilla por defecto")


def write_md_from_admin(config: dict) -> None:
    """Sobrescribe `race_data.md` desde un dict tipo admin_config.json.

    `race_info` se acepta como parrafo libre o como lista numerada;
    si es parrafo se divide automaticamente en oraciones.
    """
    race_info_raw = (config.get("race_info") or "").strip()
    context_raw = (config.get("context") or "").strip()
    race_name = (config.get("race_name") or "").strip()

    info_items = _extract_numbered_items(race_info_raw)
    if not info_items and race_info_raw:
        info_items = _split_paragraph_to_items(race_info_raw)

    context_items = _extract_numbered_items(context_raw)
    if not context_items and context_raw:
        context_items = _split_paragraph_to_items(context_raw)

    md = "# Datos de la carrera para Mark y Maria\n\n"
    md += "Este archivo lo gestiona F1COMMENTS. Puedes editarlo a mano: las dos secciones "
    md += "son las que se inyectan a Maria (Mark solo narra lo que pasa en pista).\n\n"
    md += "- Si vacias una lista, ese bloque deja de inyectarse.\n"
    md += "- Cuando un item se \"usa\", se marca y no vuelve a salir.\n"
    md += "- Si quieres reiniciar el contador de usados, llama a POST /api/race-data/reset.\n\n"
    md += f"**Carrera:** {race_name or '(sin definir)'}\n\n"
    md += "## Información de la carrera (lista numerada)\n\n"
    md += "> Parrafos extendidos / contexto historico. Maria usa UNO cada 5 comentarios sin repetir.\n\n"
    md += _items_to_markdown(info_items) + "\n\n"
    md += "## Contexto (lista numerada)\n\n"
    md += "> Datos curiosos / hitos puntuales. Maria usa UNO en cada bloque sin repetir.\n\n"
    md += _items_to_markdown(context_items) + "\n"
    MD_PATH.write_text(md, encoding="utf-8")


def _extract_numbered_items(body: str) -> List[str]:
    """Devuelve los items numerados (`N. texto`) presentes en `body`.

    Util para detectar si el usuario ya pego una lista numerada lista.
    """
    items: List[str] = []
    for fm in re.finditer(r"^\s*(\d+)\.\s+(.+?)$", body or "", re.MULTILINE):
        content = fm.group(2).strip()
        if content and not content.startswith("(") and content.lower() != "(sin datos)":
            items.append(content)
    return items


def _parse_section(text: str, header_regex: str) -> List[Tuple[int, str]]:
    """Saca los items numerados de la seccion cuyo header matchea `header_regex`."""
    m = re.search(header_regex + r".*?\n(.*?)(?=\n##|\Z)", text, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    facts: List[Tuple[int, str]] = []
    for fm in re.finditer(r"^\s*(\d+)\.\s+(.+?)$", m.group(1), re.MULTILINE):
        num = int(fm.group(1))
        content = fm.group(2).strip()
        if content and not content.startswith("(") and content.lower() != "(sin datos)":
            facts.append((num, content))
    return facts


def parse_md() -> Tuple[str, List[Tuple[int, str]], List[Tuple[int, str]]]:
    """Lee `race_data.md` y devuelve (race_name, info_items, context_items)."""
    if not MD_PATH.exists():
        return "", [], []
    text = MD_PATH.read_text(encoding="utf-8")

    race_name = ""
    m_name = re.search(r"\*\*Carrera:\*\*\s*(.+)", text)
    if m_name:
        rn = m_name.group(1).strip()
        if rn and rn.lower() != "(sin definir)":
            race_name = rn

    info_items = _parse_section(text, r"##\s*Informaci[óo]n de la carrera")
    context_items = _parse_section(text, r"##\s*Contexto")
    return race_name, info_items, context_items


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"used_facts": [], "used_info": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _mark_helper(key: str, used_nums: list[int]) -> None:
    if not used_nums:
        return
    state = load_state()
    used = set(int(n) for n in state.get(key, []))
    for n in used_nums:
        try:
            used.add(int(n))
        except (TypeError, ValueError):
            continue
    state[key] = sorted(used)
    save_state(state)


def mark_facts_used(used_nums: list[int]) -> None:
    """Marca items del CONTEXTO como usados."""
    _mark_helper("used_facts", used_nums)


def mark_info_used(used_nums: list[int]) -> None:
    """Marca items de INFORMACION DE LA CARRERA (race_info) como usados."""
    _mark_helper("used_info", used_nums)


def reset_state() -> None:
    save_state({"used_facts": [], "used_info": []})


def get_data_for_prompt() -> dict:
    """Devuelve los datos a inyectar al prompt: solo items NO usados.

    Returns dict con dos pools (`context` y `race_info`) ya formateados
    como `1. ...\\n2. ...` y sus respectivos contadores.
    """
    race_name, info_items, context_items = parse_md()
    state = load_state()
    used_facts = set(int(n) for n in state.get("used_facts", []))
    used_info = set(int(n) for n in state.get("used_info", []))

    unused_ctx = [(n, t) for n, t in context_items if n not in used_facts]
    unused_info = [(n, t) for n, t in info_items if n not in used_info]

    return {
        "race_name": race_name,
        # CONTEXTO
        "context": "\n".join(f"{n}. {t}" for n, t in unused_ctx) if unused_ctx else "",
        "facts_total": len(context_items),
        "facts_used": len([n for n, _ in context_items if n in used_facts]),
        "facts_remaining": len(unused_ctx),
        "exhausted": len(context_items) > 0 and not unused_ctx,
        "available_numbers": [n for n, _ in unused_ctx],
        # RACE_INFO
        "race_info": "\n".join(f"{n}. {t}" for n, t in unused_info) if unused_info else "",
        "info_total": len(info_items),
        "info_used": len([n for n, _ in info_items if n in used_info]),
        "info_remaining": len(unused_info),
        "info_exhausted": len(info_items) > 0 and not unused_info,
        "available_info_numbers": [n for n, _ in unused_info],
    }
