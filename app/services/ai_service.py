"""
services/ai_service.py — Integración con el LLM (guiones) y TTS (voz).

Ninguna de las dos funciones explota si falta la API key correspondiente:
devuelven un resultado placeholder bien marcado como tal (`[SIMULADO]`) y
lo loguean como warning. Esto permite levantar y probar el resto del
servicio (streaming, playlist) sin tener todavía las cuentas de Anthropic/
OpenAI/ElevenLabs dadas de alta — algo útil en la Fase 1/2 del plan de
implementación del documento, antes de tener los costos variables
aprobados.

FIX 2026-09-06: se agregó Anthropic como proveedor de guiones porque la
cuenta de OpenAI se quedó sin crédito (`openai.RateLimitError:
credit_balance_exhausted`) en medio de una prueba — esa excepción no estaba
contemplada (a diferencia de "falta la key", que sí tiene el fallback
[SIMULADO]) y tiraba un 500 sin controlar en /api/v1/ai/clip.
`generar_guion()` ahora prueba Anthropic primero si ANTHROPIC_API_KEY está
seteada, y solo cae a OpenAI si no lo está — así no dependemos de una sola
cuenta con crédito.
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger("ai_service")

PROMPT_SISTEMA = (
    "Sos el redactor institucional del canal de streaming 24/7 de la UMSA "
    "(Universidad del Museo Social Argentino). Escribís guiones breves, en "
    "español rioplatense institucional, para locución en vivo: agenda del "
    "día, convocatorias, becas, novedades académicas, presentación de "
    "carreras y respuestas de FAQ de admisión. Tono cálido pero profesional, "
    "oraciones cortas pensadas para ser leídas en voz alta por una síntesis "
    "de voz, sin emojis ni markdown."
)


def generar_guion(tema: str, contexto: str | None = None) -> str:
    """Genera un guion corto con el LLM configurado.

    `contexto` es para pasar info puntual (ej. una fecha de inscripción,
    un fragmento del catálogo de carreras) que el guion tiene que
    mencionar con precisión — el modelo no tiene acceso propio al
    repositorio de carreras de la UMSA, hay que dárselo acá.

    Orden de proveedores: Anthropic primero (si ANTHROPIC_API_KEY está
    seteada), después OpenAI, y si no hay ninguna de las dos, un guion
    [SIMULADO]. Poder elegir cuál usar sirve para no quedar bloqueados si
    a una de las dos cuentas se le acaba el crédito (ver docstring del
    módulo).
    """
    if settings.anthropic_api_key:
        return _generar_guion_anthropic(tema, contexto)
    if settings.openai_api_key:
        return _generar_guion_openai(tema, contexto)

    logger.warning("Ni ANTHROPIC_API_KEY ni OPENAI_API_KEY están seteadas — devolviendo guion simulado")
    return f"[SIMULADO] Guion sobre «{tema}» — configurá ANTHROPIC_API_KEY (o OPENAI_API_KEY) para generar el real."


def _generar_guion_anthropic(tema: str, contexto: str | None = None) -> str:
    from anthropic import Anthropic  # import perezoso: evita el costo de import si no se usa

    client = Anthropic(api_key=settings.anthropic_api_key)
    contenido_usuario = f"Tema: {tema}"
    if contexto:
        contenido_usuario += f"\n\nContexto puntual a incluir:\n{contexto}"

    respuesta = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=800,
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": contenido_usuario}],
    )
    return "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")


def _generar_guion_openai(tema: str, contexto: str | None = None) -> str:
    from openai import OpenAI  # import perezoso: evita el costo de import si no se usa

    client = OpenAI(api_key=settings.openai_api_key)
    mensajes = [{"role": "system", "content": PROMPT_SISTEMA}]
    contenido_usuario = f"Tema: {tema}"
    if contexto:
        contenido_usuario += f"\n\nContexto puntual a incluir:\n{contexto}"
    mensajes.append({"role": "user", "content": contenido_usuario})

    respuesta = client.chat.completions.create(model=settings.openai_model, messages=mensajes)
    return respuesta.choices[0].message.content or ""


def generar_voz(texto: str, nombre_archivo: str, voice_id: str | None = None) -> Path:
    """Convierte `texto` a audio con ElevenLabs y lo guarda en
    settings.audio_dir / nombre_archivo (con extensión .mp3).

    `voice_id` permite pisar puntualmente el ELEVENLABS_VOICE_ID del .env.
    Pensado para cuando cada bloque de la grilla de programación tenga su
    propia voz asignada (ej. una voz para "UMSA Despierta" y otra para
    "Espacio Posgrados y Negocios") sin tener que reconfigurar el .env en
    cada llamada — ver plan de contenido del canal.

    Devuelve el Path del archivo generado. Si falta la API key o el
    voice_id (ni el del .env ni el pasado acá), genera igual un archivo
    (silencio corto vía ffmpeg) para que el resto del pipeline (armar el
    clip final) no tenga que manejar un caso especial de "sin audio" —
    solo hay que acordarse de que ese archivo es un placeholder, se
    loguea como warning.
    """
    destino = settings.audio_dir / f"{nombre_archivo}.mp3"
    destino.parent.mkdir(parents=True, exist_ok=True)

    voice_id_efectivo = voice_id or settings.elevenlabs_voice_id

    if not settings.elevenlabs_api_key or not voice_id_efectivo:
        logger.warning(
            "ELEVENLABS_API_KEY o el voice_id (ni el del .env ni el pasado a "
            f"generar_voz) están seteados — generando un mp3 de silencio "
            f"como placeholder en {destino}"
        )
        import subprocess

        subprocess.run(
            [settings.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-t", "3", str(destino)],
            capture_output=True,
        )
        return destino

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id_efectivo}"
    headers = {"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"}
    payload = {"text": texto, "model_id": settings.elevenlabs_model_id}

    with httpx.Client(timeout=60.0) as client:
        respuesta = client.post(url, headers=headers, json=payload)
    respuesta.raise_for_status()
    destino.write_bytes(respuesta.content)
    return destino
