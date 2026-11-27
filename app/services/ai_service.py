"""
services/ai_service.py — Integración con el LLM (guiones y traducción) y TTS (voz).

En desarrollo, ninguna función explota si falta lo necesario para generar el
resultado real: devuelven un placeholder bien marcado como tal (`[SIMULADO]`
para el guion y la traducción, un wav de silencio para la voz) y lo loguean
como warning, para poder probar el resto del servicio sin cuentas ni modelos.
En producción no hay placeholders: falla con ServicioIAError (→ 503), porque
un placeholder terminaría saliendo AL AIRE.

FIX 2026-09-06: se agregó Anthropic como proveedor porque la cuenta de OpenAI
se quedó sin crédito (`openai.RateLimitError: credit_balance_exhausted`) en
medio de una prueba. Se prueba Anthropic primero si ANTHROPIC_API_KEY está
seteada y, si falla (sin crédito, sobrecarga, red), OpenAI. Ese mismo
mecanismo (`_completar`) lo usan el guion y la traducción de subtítulos.

FIX 2026-09-09: se sacó ElevenLabs como proveedor de voz (cuota agotada a
mitad de una tanda → 401 sin controlar). La voz sale de Piper (`piper-tts`):
TTS neuronal 100% local, sin key ni cuota. El modelo (.onnx + .onnx.json) se
descarga una sola vez a `tts_models_dir` (ver README) o viene horneado en la
imagen Docker.

CAMBIO 2026-11-27 (subtítulos en inglés): Piper ya no se llama como
subproceso sino con su API de Python (`PiperVoice`), en el mismo proceso y con
el modelo cacheado (cargarlo tarda ~7 s). Así se sintetiza ORACIÓN POR
ORACIÓN y se sabe exactamente cuándo empieza y termina cada una en el wav
final — son los tiempos de los subtítulos (ver services/subtitulos.py). De
paso desaparece el problema de encoding del pipe de stdin en Windows (FIX
2026-09-17): el texto ya no cruza ningún pipe.
"""
from __future__ import annotations

import json
import logging
import wave
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.services.subtitulos import dividir_oraciones

logger = logging.getLogger("ai_service")


# Pausa que se inserta entre oraciones en el wav final: Piper sintetiza cada
# oración sin silencio al final, y pegadas una detrás de otra suenan apuradas.
PAUSA_ENTRE_ORACIONES_SEG = 0.35


class ServicioIAError(RuntimeError):
    """No se pudo generar el guion, la traducción o la voz (proveedores
    caídos, sin crédito, o sin configurar en producción). Los endpoints la
    traducen a un 503 con un mensaje claro en vez de un 500 sin controlar."""


PROMPT_SISTEMA = (
    "Sos el redactor institucional del canal de streaming 24/7 de la UMSA "
    "(Universidad del Museo Social Argentino). Escribís guiones breves, en "
    "español rioplatense institucional, para locución en vivo: agenda del "
    "día, convocatorias, becas, novedades académicas, presentación de "
    "carreras y respuestas de FAQ de admisión. Tono cálido pero profesional, "
    "oraciones cortas pensadas para ser leídas en voz alta por una síntesis "
    "de voz, sin emojis ni markdown."
)

PROMPT_TRADUCCION = (
    "You translate on-screen subtitles for the 24/7 institutional channel of UMSA "
    "(Universidad del Museo Social Argentino), from Rioplatense Spanish into clear, "
    "natural English. You receive a JSON array of Spanish sentences. Return ONLY a "
    "JSON array of strings with exactly the same number of elements, in the same "
    "order: element i is the translation of sentence i. Do not merge, split, add or "
    "drop sentences. Keep it concise, as subtitles are read quickly. Keep the name "
    "UMSA as is and translate degree names naturally (e.g. 'Licenciatura en "
    "Negocios Digitales' -> 'Bachelor's degree in Digital Business'). No markdown."
)


# --------------------------------------------------------------------------
# LLM: un solo mecanismo de fallback entre proveedores
# --------------------------------------------------------------------------
def _completar_anthropic(sistema: str, usuario: str, max_tokens: int) -> str:
    from anthropic import Anthropic  # import perezoso: evita el costo de import si no se usa

    client = Anthropic(api_key=settings.anthropic_api_key)
    respuesta = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=sistema,
        messages=[{"role": "user", "content": usuario}],
    )
    # Los modelos actuales razonan por defecto y ese razonamiento descuenta de
    # max_tokens: un guion cortado a mitad de frase saldría al aire tal cual.
    # Cortado o rechazado = falla de este proveedor (se prueba el siguiente).
    if respuesta.stop_reason == "max_tokens":
        raise ValueError(f"respuesta cortada por max_tokens={max_tokens}")
    if respuesta.stop_reason == "refusal":
        raise ValueError("el modelo rechazó la solicitud (stop_reason=refusal)")
    return "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")


def _completar_openai(sistema: str, usuario: str, max_tokens: int) -> str:
    from openai import OpenAI  # import perezoso: evita el costo de import si no se usa

    client = OpenAI(api_key=settings.openai_api_key)
    respuesta = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
    )
    return respuesta.choices[0].message.content or ""


def _completar[T](
    sistema: str,
    usuario: str,
    tarea: str,
    validar: Callable[[str], T],
    max_tokens: int = 8000,  # holgado: incluye el razonamiento del modelo, no solo el texto final
) -> T | None:
    """Prueba los proveedores configurados en orden (Anthropic, OpenAI) y
    devuelve `validar(respuesta)` del primero que funcione. `validar` lanza
    ValueError si la respuesta no sirve (vacía, JSON roto...): eso cuenta como
    fallo de ese proveedor y se prueba el siguiente.

    Devuelve None si no hay NINGÚN proveedor configurado (el que llama decide
    si eso es un placeholder o un error). Lanza ServicioIAError si había
    proveedores y fallaron todos."""
    proveedores = []
    if settings.anthropic_api_key:
        proveedores.append(("Anthropic", _completar_anthropic))
    if settings.openai_api_key:
        proveedores.append(("OpenAI", _completar_openai))
    if not proveedores:
        return None

    errores = []
    for nombre, completar in proveedores:
        try:
            return validar(completar(sistema, usuario, max_tokens).strip())
        except Exception as e:  # noqa: BLE001 — sin crédito, sobrecarga, red, modelo inválido, respuesta inválida...
            logger.warning(f"{nombre} falló generando {tarea} ({type(e).__name__}: {e}) — pruebo el siguiente")
            errores.append(f"{nombre}: {type(e).__name__}: {e}")
    raise ServicioIAError(f"No se pudo generar {tarea} con ningún proveedor — " + " | ".join(errores))


def _no_vacio(texto: str) -> str:
    if not texto:
        raise ValueError("respuesta vacía")
    return texto


# --------------------------------------------------------------------------
# Guion
# --------------------------------------------------------------------------
def generar_guion(tema: str, contexto: str | None = None) -> str:
    """Genera un guion corto con el LLM configurado.

    `contexto` es para pasar info puntual (ej. una fecha de inscripción, un
    fragmento del catálogo de carreras) que el guion tiene que mencionar con
    precisión — el modelo no tiene acceso propio al repositorio de carreras
    de la UMSA, hay que dárselo acá.
    """
    usuario = f"Tema: {tema}"
    if contexto:
        usuario += f"\n\nContexto puntual a incluir:\n{contexto}"

    guion = _completar(PROMPT_SISTEMA, usuario, "el guion", _no_vacio)
    if guion is not None:
        return guion
    if settings.es_produccion:
        # Un guion "[SIMULADO]" se sintetizaría a voz y saldría AL AIRE.
        raise ServicioIAError("Ni ANTHROPIC_API_KEY ni OPENAI_API_KEY están configuradas en producción.")
    logger.warning("Ni ANTHROPIC_API_KEY ni OPENAI_API_KEY están seteadas — devolviendo guion simulado")
    return f"[SIMULADO] Guion sobre «{tema}» — configurá ANTHROPIC_API_KEY (o OPENAI_API_KEY) para generar el real."


# --------------------------------------------------------------------------
# Traducción (subtítulos en inglés)
# --------------------------------------------------------------------------
def _parsear_traduccion(cantidad: int) -> Callable[[str], list[str]]:
    def validar(respuesta: str) -> list[str]:
        texto = respuesta.strip()
        if texto.startswith("```"):  # algunos modelos lo envuelven en un bloque de código igual
            texto = texto.strip("`").removeprefix("json").strip()
        datos = json.loads(texto)
        if not isinstance(datos, list) or not all(isinstance(x, str) and x.strip() for x in datos):
            raise ValueError("la traducción no es una lista de textos no vacíos")
        if len(datos) != cantidad:
            # Sin correspondencia 1 a 1 no hay forma de asignarle los tiempos
            # de cada oración en español: mejor fallar que desincronizar.
            raise ValueError(f"se esperaban {cantidad} oraciones traducidas y llegaron {len(datos)}")
        return [x.strip() for x in datos]

    return validar


def traducir_oraciones(oraciones: list[str], idioma: str = "en") -> list[str]:
    """Traduce cada oración del guion (español) al inglés, una por una y en el
    mismo orden: la traducción i hereda los tiempos de la oración i."""
    if idioma != "en":
        raise ValueError(f"Idioma de subtítulos no soportado: {idioma!r} (por ahora solo 'en')")
    if not oraciones:
        return []
    usuario = json.dumps(oraciones, ensure_ascii=False)
    traduccion = _completar(
        PROMPT_TRADUCCION,
        usuario,
        "la traducción al inglés",
        _parsear_traduccion(len(oraciones)),
        max_tokens=max(8000, 2 * len(usuario)),  # holgado: el razonamiento del modelo también descuenta
    )
    if traduccion is not None:
        return traduccion
    if settings.es_produccion:
        raise ServicioIAError("Ni ANTHROPIC_API_KEY ni OPENAI_API_KEY están configuradas en producción.")
    logger.warning("Sin ANTHROPIC_API_KEY ni OPENAI_API_KEY — devolviendo traducción simulada")
    return [f"[SIMULATED EN] {o}" for o in oraciones]


# --------------------------------------------------------------------------
# Voz (Piper, oración por oración)
# --------------------------------------------------------------------------
@dataclass
class VozGenerada:
    ruta: Path
    oraciones: list[str]
    tiempos: list[tuple[float, float]]  # (inicio, fin) en segundos de cada oración dentro del wav


@lru_cache(maxsize=2)
def _cargar_voz(modelo: str):
    """Carga un modelo Piper una sola vez por proceso (tarda ~7 s y ocupa
    ~100 MB): sin caché, cada clip pagaría la carga de nuevo."""
    from piper import PiperVoice  # import perezoso: onnxruntime es pesado

    logger.info(f"Cargando modelo de voz Piper {Path(modelo).name}")
    return PiperVoice.load(modelo)


def _duracion_simulada(oracion: str) -> float:
    return max(1.0, 0.065 * len(oracion))  # ~15 caracteres por segundo de locución


def sintetizar_oraciones(oraciones: list[str], nombre_archivo: str, voice_id: str | None = None) -> VozGenerada:
    """Sintetiza `oraciones` con Piper, una por una, y las une en
    settings.audio_dir / <nombre_archivo>.wav con una pausa corta entre cada
    una. Devuelve el wav y el (inicio, fin) de cada oración, que son los
    tiempos exactos de los subtítulos.

    `voice_id`, si se pasa, es el nombre de un modelo Piper ya descargado en
    tts_models_dir (ej. "es_AR-daniela-high", sin extensión) que pisa
    PIPER_VOICE_DEFAULT para esta llamada — pensado para que cada bloque de la
    grilla tenga su propia voz.

    Sin el modelo: en desarrollo, wav de silencio con duraciones estimadas
    (para probar el resto del pipeline); en producción, ServicioIAError.
    """
    oraciones = [o for o in (o.strip() for o in oraciones) if o]
    if not oraciones:
        raise ServicioIAError(f"No hay texto para sintetizar en {nombre_archivo}")

    destino = settings.audio_dir / f"{nombre_archivo}.wav"
    destino.parent.mkdir(parents=True, exist_ok=True)
    voz = voice_id or settings.piper_voice_default
    modelo = settings.tts_models_dir / f"{voz}.onnx"

    if modelo.exists():
        try:
            piper = _cargar_voz(str(modelo))
            audios = []
            for oracion in oraciones:
                chunks = list(piper.synthesize(oracion))
                if not chunks:
                    raise ServicioIAError(f"Piper no devolvió audio para: {oracion[:80]!r}")
                audios.append(b"".join(c.audio_int16_bytes for c in chunks))
            formato = (chunks[0].sample_rate, chunks[0].sample_width, chunks[0].sample_channels)
        except ServicioIAError:
            raise
        except Exception as e:  # noqa: BLE001 — modelo corrupto, .onnx.json faltante, onnxruntime...
            raise ServicioIAError(f"Piper no pudo generar la voz para {nombre_archivo}: {type(e).__name__}: {e}") from e
    else:
        if settings.es_produccion:
            # Un wav de silencio armaría un clip mudo que saldría AL AIRE.
            raise ServicioIAError(
                f"Modelo de voz Piper '{voz}' no encontrado en {settings.tts_models_dir} "
                "(¿TTS_MODELS_DIR=/srv/tts_models en Railway?)."
            )
        logger.warning(
            f"Modelo Piper '{voz}' no encontrado en {settings.tts_models_dir} (esperaba {modelo.name} + "
            f"{modelo.name}.json) — generando un wav de silencio como placeholder en {destino}. Ver README."
        )
        formato = (22050, 2, 1)  # mismo formato que las voces "high" de Piper
        audios = [bytes(int(_duracion_simulada(o) * formato[0]) * formato[1] * formato[2]) for o in oraciones]

    sample_rate, sample_width, canales = formato
    bytes_por_seg = sample_rate * sample_width * canales
    pausa = bytes(int(PAUSA_ENTRE_ORACIONES_SEG * sample_rate) * sample_width * canales)

    tiempos, t = [], 0.0
    with wave.open(str(destino), "wb") as wav:
        wav.setframerate(sample_rate)
        wav.setsampwidth(sample_width)
        wav.setnchannels(canales)
        for i, audio in enumerate(audios):
            if i:
                wav.writeframes(pausa)
                t += len(pausa) / bytes_por_seg
            duracion = len(audio) / bytes_por_seg
            wav.writeframes(audio)
            tiempos.append((t, t + duracion))
            t += duracion
    return VozGenerada(ruta=destino, oraciones=oraciones, tiempos=tiempos)


def generar_voz(texto: str, nombre_archivo: str, voice_id: str | None = None) -> Path:
    """Convierte `texto` a voz (wav en settings.audio_dir). Atajo de
    sintetizar_oraciones() para quien solo necesita el audio (POST /ai/voz)."""
    return sintetizar_oraciones(dividir_oraciones(texto), nombre_archivo, voice_id=voice_id).ruta
