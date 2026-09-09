"""
services/ai_service.py — Integración con el LLM (guiones) y TTS (voz).

Ninguna de las dos funciones explota si falta lo necesario para generar el
resultado real: devuelven un resultado placeholder bien marcado como tal
(`[SIMULADO]` para el guion, un wav de silencio para la voz) y lo loguean
como warning. Esto permite levantar y probar el resto del servicio
(streaming, playlist) sin tener todavía las cuentas/modelos dados de
alta — algo útil en la Fase 1/2 del plan de implementación del documento,
antes de tener los costos variables aprobados.

FIX 2026-09-06: se agregó Anthropic como proveedor de guiones porque la
cuenta de OpenAI se quedó sin crédito (`openai.RateLimitError:
credit_balance_exhausted`) en medio de una prueba — esa excepción no estaba
contemplada (a diferencia de "falta la key", que sí tiene el fallback
[SIMULADO]) y tiraba un 500 sin controlar en /api/v1/ai/clip.
`generar_guion()` ahora prueba Anthropic primero si ANTHROPIC_API_KEY está
seteada, y solo cae a OpenAI si no lo está — así no dependemos de una sola
cuenta con crédito.

FIX 2026-09-09: se sacó ElevenLabs como proveedor de voz — con la cuota de
caracteres del plan agotada a mitad de la carga de bloques, `generar_voz()`
tiraba `httpx.HTTPStatusError: 401 Unauthorized` sin controlar (mismo tipo
de problema que el fix anterior con OpenAI, pero acá no había fallback:
401 no es "falta la key", así que no caía al placeholder). En su lugar,
`generar_voz()` ahora usa Piper (`piper-tts`, ver requirements.txt): un
motor de TTS neuronal que corre 100% local, sin key ni cuota — no hay
límite que se pueda agotar a mitad de una tanda. El modelo de voz (.onnx +
.onnx.json) se descarga una sola vez a mano a `tts_models_dir` (ver
README, sección "Generar guion + voz con IA"); si no está, cae al mismo
placeholder de silencio que antes.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

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
    """Convierte `texto` a audio con Piper (TTS neuronal local, sin key ni
    cuota) y lo guarda en settings.audio_dir / nombre_archivo (extensión
    .wav — da igual para el resto del pipeline, armar_clip_narrado() se lo
    pasa a ffmpeg como entrada de audio y ffmpeg detecta el formato solo).

    `voice_id`, si se pasa, es el nombre de un modelo de voz Piper ya
    descargado en tts_models_dir (ej. "es_AR-daniela-high", sin extensión)
    que pisa puntualmente PIPER_VOICE_DEFAULT del .env — pensado para
    cuando cada bloque de la grilla tenga su propia voz asignada (ej. una
    voz para "UMSA Despierta" y otra para "Espacio Posgrados y Negocios")
    sin tener que reconfigurar el .env en cada llamada, igual que antes
    con ELEVENLABS_VOICE_ID — ver plan de contenido del canal.

    Devuelve el Path del archivo generado. Si el modelo (<voz>.onnx) no
    está descargado en tts_models_dir, genera igual un archivo (silencio
    corto vía ffmpeg) para que el resto del pipeline (armar el clip final)
    no tenga que manejar un caso especial de "sin audio" — solo hay que
    acordarse de que ese archivo es un placeholder, se loguea como warning.
    """
    destino = settings.audio_dir / f"{nombre_archivo}.wav"
    destino.parent.mkdir(parents=True, exist_ok=True)

    voz = voice_id or settings.piper_voice_default
    modelo = settings.tts_models_dir / f"{voz}.onnx"

    if not modelo.exists():
        logger.warning(
            f"Modelo Piper '{voz}' no encontrado en {settings.tts_models_dir} "
            f"(esperaba {modelo.name} + {modelo.name}.json) — generando un wav "
            f"de silencio como placeholder en {destino}. Ver README para "
            f"descargar el modelo."
        )
        subprocess.run(
            [settings.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-t", "3", str(destino)],
            capture_output=True,
        )
        return destino

    comando = [settings.piper_bin, "-m", str(modelo), "-f", str(destino)]
    resultado = subprocess.run(comando, input=texto, capture_output=True, text=True, encoding="utf-8")
    if resultado.returncode != 0:
        raise RuntimeError(f"piper no pudo generar la voz para {nombre_archivo}: {resultado.stderr[-800:]}")
    return destino
