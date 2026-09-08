"""
core/scheduler.py — Selector automático de bloque horario para la grilla de
programación de 24hs (ver Claude outputs/plan_contenido_canal_umsa.md,
sección 2 "Grilla de programación").

Cómo funciona: un task de asyncio corriendo en background (arrancado desde
el lifespan de FastAPI, ver app/main.py) chequea cada 60 segundos la hora
actual, determina a qué bloque de la grilla corresponde (GRILLA más abajo) y,
si cambió respecto al bloque anterior, arma la lista de clips de ese bloque
y reescribe playlist.txt con core/playlist_io.escribir_playlist. Si el
streamer ya está corriendo, además llama a streamer.reload() para que ffmpeg
relea la playlist nueva (ver la limitación de "reload" documentada en
core/streamer.py: corta la señal un par de segundos, no es un hot-swap real).

Cómo se arman los clips de cada bloque: por PREFIJO de nombre de archivo, no
por una lista hardcodeada. Todo clip que se genere con
POST /api/v1/ai/clip usando un nombre_archivo que empiece con el prefijo de
un bloque (ver GRILLA) se suma automáticamente la próxima vez que el
scheduler arme ese bloque — no hace falta tocar este archivo para sumar
contenido nuevo a una franja existente.

Bloques sin contenido propio todavía — Prime Time real (requiere que el
equipo defina un calendario de webinars/paneles en vivo, no se puede generar
solo) y Study Lounge (requiere una pista de música libre de derechos, que el
pipeline actual de IA no genera — ai_service.py solo hace guion+voz, no
música) — ver "Próximos pasos sugeridos" del plan de contenido. Mientras
tanto caen a FALLBACK_PREFIX: repiten el video de fondo institucional en
loop, para que la señal nunca se corte aunque todavía no haya contenido
propio de esos bloques.

Testing manual sin esperar 24hs reales: POST /api/v1/stream/schedule/force
(ver api/v1/stream.py) fuerza un recálculo ya mismo, opcionalmente simulando
una hora puntual (?hora=10) para poder probar los 6 bloques uno detrás del
otro en un rato.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from app.config import settings
from app.core.playlist_io import escribir_playlist
from app.core.streamer import streamer

logger = logging.getLogger("scheduler")

# Prefijo de respaldo: si un bloque no tiene clips propios, se usa este loop
# institucional para no dejar la señal sin nada que transmitir.
FALLBACK_PREFIX = "prueba_fondo_umsa"

# Cada cuánto chequea el task de background si cambió el bloque. Los bloques
# cambian en horas en punto, así que no hace falta más precisión que esta.
INTERVALO_CHEQUEO_SEG = 60


@dataclass(frozen=True)
class Bloque:
    nombre: str
    hora_inicio: int  # hora local, 0-23, inclusive
    hora_fin: int  # exclusivo; si hora_fin <= hora_inicio, el bloque cruza medianoche
    prefijo: str  # prefijo de nombre_archivo que agrupa los clips de este bloque

    def activo_a_las(self, hora: int) -> bool:
        if self.hora_inicio < self.hora_fin:
            return self.hora_inicio <= hora < self.hora_fin
        return hora >= self.hora_inicio or hora < self.hora_fin  # cruza medianoche (ej. Study Lounge)


# Grilla completa — ver Claude outputs/plan_contenido_canal_umsa.md sección 2.
# Los prefijos coinciden con los nombre_archivo usados en cargar_bloques.ps1
# y en las llamadas manuales a POST /api/v1/ai/clip.
GRILLA: list[Bloque] = [
    Bloque("UMSA Despierta", 7, 10, "umsa_despierta_"),
    Bloque("Foco Grado y Vocación", 10, 13, "foco_grado_"),
    Bloque("Extensión y Comunidad", 13, 16, "extension_"),
    Bloque("Espacio Posgrados y Negocios", 16, 19, "posgrado_"),
    Bloque("Prime Time: Clases Abiertas", 19, 22, "primetime_"),  # sin contenido propio todavía — ver docstring
    Bloque("UMSA Study Lounge", 22, 7, "studylounge_"),  # sin contenido propio todavía — ver docstring
]


def bloque_actual(hora: int | None = None) -> Bloque:
    """Devuelve el bloque de la grilla activo a la hora dada (0-23). Si no se
    pasa `hora`, usa la hora local actual del sistema."""
    hora = datetime.now().hour if hora is None else hora
    for bloque in GRILLA:
        if bloque.activo_a_las(hora):
            return bloque
    # No debería pasar nunca si GRILLA cubre las 24hs completas — si esto
    # salta, revisar que no haya un hueco en los rangos horarios.
    raise RuntimeError(f"Ningún bloque de la grilla cubre la hora {hora} — revisar GRILLA en scheduler.py")


def _clips_para(bloque: Bloque) -> list[str]:
    """Devuelve los nombres de archivo de `media_dir` que empiezan con el
    prefijo del bloque, ordenados alfabéticamente (orden estable entre
    reloads). Si no hay ninguno, cae al fallback institucional."""
    if not settings.media_dir.exists():
        return []
    candidatos = sorted(
        p.name for p in settings.media_dir.iterdir()
        if p.is_file() and p.name.startswith(bloque.prefijo)
    )
    if candidatos:
        return candidatos

    fallback = sorted(
        p.name for p in settings.media_dir.iterdir()
        if p.is_file() and p.name.startswith(FALLBACK_PREFIX)
    )
    if fallback:
        logger.warning(
            f"Bloque «{bloque.nombre}» no tiene clips propios (prefijo "
            f"'{bloque.prefijo}') — usando el loop de fondo institucional como respaldo."
        )
        return fallback

    logger.error(
        f"Bloque «{bloque.nombre}» no tiene clips propios NI existe el fallback "
        f"'{FALLBACK_PREFIX}*' en {settings.media_dir} — la playlist va a quedar vacía."
    )
    return []


class SchedulerBloques:
    """Task de background que mantiene playlist.txt sincronizada con la hora
    actual. Arranca/para desde el lifespan de FastAPI (ver app/main.py,
    settings.scheduler_enabled). Solo mantiene el archivo — no arranca la
    emisión por sí solo; si el streamer ya está corriendo, recarga ffmpeg
    cuando cambia de bloque."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._bloque_actual: str | None = None
        self._detener = asyncio.Event()

    async def _ciclo(self) -> None:
        while not self._detener.is_set():
            bloque = bloque_actual()
            if bloque.nombre != self._bloque_actual:
                self._aplicar(bloque)
            try:
                await asyncio.wait_for(self._detener.wait(), timeout=INTERVALO_CHEQUEO_SEG)
            except asyncio.TimeoutError:
                pass  # es el chequeo normal cada INTERVALO_CHEQUEO_SEG, no un error

    def _aplicar(self, bloque: Bloque) -> str:
        clips = _clips_para(bloque)
        logger.info(
            f"Cambio de bloque: «{bloque.nombre}» ({len(clips)} clip(s)) — "
            f"reescribiendo playlist."
        )
        escribir_playlist(clips)
        self._bloque_actual = bloque.nombre
        detail = f"Playlist actualizada al bloque «{bloque.nombre}» ({len(clips)} clip(s))."
        if streamer.status()["running"]:
            try:
                streamer.reload()
                detail += " Streamer recargado."
            except RuntimeError as e:
                logger.error(f"No se pudo recargar el streamer al cambiar de bloque: {e}")
                detail += f" No se pudo recargar el streamer: {e}"
        return detail

    def forzar(self, hora: int | None = None) -> str:
        """Recalcula y reescribe la playlist ya mismo, sin esperar al
        próximo chequeo del loop de background — pensado para testing manual
        (ver POST /api/v1/stream/schedule/force). `hora` (0-23) simula esa
        hora en vez de la hora real del sistema."""
        return self._aplicar(bloque_actual(hora))

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._detener.clear()
        self._task = asyncio.create_task(self._ciclo())
        logger.info("Scheduler de bloques horarios arrancado.")

    def stop(self) -> None:
        self._detener.set()
        if self._task is not None:
            self._task.cancel()
        logger.info("Scheduler de bloques horarios detenido.")

    def estado(self) -> dict:
        return {
            "bloque_actual": self._bloque_actual,
            "corriendo": self._task is not None and not self._task.done(),
        }


# Singleton — importado por app/main.py (lifespan) y api/v1/stream.py (endpoints).
scheduler = SchedulerBloques()
