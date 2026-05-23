import os
import io
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# Voces coherentes con modelos GPT / Speech actuales (ver OpenAI Speech API «voice options»)
VOICE_MAP = {
    "mark": "cedar",   # Tono cargado para relato deportivo masculino
    "maria": "coral",   # Clara, profesional estilo radial / análisis
}

# GPT Realtime 2 vía API de síntesis (/v1/audio/speech): voz multimodal tiempo real oficial.
DEFAULT_SPEECH_MODEL = "gpt-realtime-2"

SPEAKER_INSTRUCTIONS = {
    "mark": "Spanish Latin American male sports broadcaster: short punchy phrases, energetic F1 commentary, stadium intensity without shouting.",
    "maria": "Spanish Latin American female analyst: concise, warm professional tone — quick insight between corners, calm confidence.",
}


def generate_audio(text: str, voice_name: str) -> io.BytesIO:
    """
    Gira la narración por OpenAI Speech API usando GPT Realtime 2 como modelo por defecto
    (audio generado igual que realtime 2.o; modo petición REST, ya que el servidor solo encola texto).
    Voces narrator: «mark», «maria».
    Override: OPENAI_SPEECH_MODEL (p. ej. gpt-4o-mini-tts si Realtime Speech no está en tu proyecto).
    """
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable is not set.")
        return io.BytesIO(b"")

    try:
        client = OpenAI(api_key=openai_api_key)

        clean_voice = voice_name.strip().lower()
        oai_voice = VOICE_MAP.get(clean_voice, "alloy")
        instructions = SPEAKER_INSTRUCTIONS.get(clean_voice, "Concise bilingual sports broadcast Spanish; clear and fast-paced.")
        speech_model = (os.environ.get("OPENAI_SPEECH_MODEL") or DEFAULT_SPEECH_MODEL).strip()

        logger.info(
            "Generating Speech | speaker=%s voice=%s model=%s",
            voice_name,
            oai_voice,
            speech_model,
        )

        create_kwargs = {
            "model": speech_model,
            "voice": oai_voice,
            "input": text,
            "instructions": instructions,
            "speed": 1.15,
        }

        try:
            response = client.audio.speech.create(**create_kwargs)
        except Exception as first_exc:
            logger.warning(
                "Speech create failed (%s), retry minimal args: %s",
                speech_model,
                first_exc,
            )
            try:
                response = client.audio.speech.create(
                    model=speech_model,
                    voice=oai_voice,
                    input=text,
                )
            except Exception as second_exc:
                if speech_model != "gpt-4o-mini-tts":
                    logger.warning(
                        "Falling back to gpt-4o-mini-tts after error: %s",
                        second_exc,
                    )
                    response = client.audio.speech.create(
                        model="gpt-4o-mini-tts",
                        voice=oai_voice,
                        input=text,
                        instructions=instructions,
                        speed=1.15,
                    )
                else:
                    raise second_exc from first_exc

        audio_stream = io.BytesIO(response.content)
        return audio_stream

    except Exception as e:
        logger.error("OpenAI Speech API Error: %s", e)
        return io.BytesIO(b"")
