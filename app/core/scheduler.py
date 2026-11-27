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

Grilla por facultad (2026-11-27): una franja diurna para cada una de las 5
facultades de core/catalogo.py y, de 22 a 7, una rotación de TODAS las
carreras. Prime Time todavía no tiene contenido propio (requiere un
calendario de webinars/paneles en vivo, no se puede generar solo): mientras
tanto, como cualquier bloque vacío, cae a la rotación de todas las carreras
y, si no hubiera ningún clip de carreras, a FALLBACK_PREFIX (el video de
fondo institucional en loop), para que la señal nunca se corte.

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
from zoneinfo import ZoneInfo

from app.config import settings
from app.core.catalogo import FACULTADES
from app.core.playlist_io import escribir_playlist
from app.core.streamer import streamer

logger = logging.getLogger("scheduler")

# Prefijo de respaldo: si un bloque no tiene clips propios, se usa este loop
# institucional para no dejar la señal sin nada que transmitir.
FALLBACK_PREFIX = "prueba_fondo_umsa"

# Cada cuánto chequea el task de background si cambió el bloque. Los bloques
# cambian en horas en punto, así que no hace falta más precisión que esta.
INTERVALO_CHEQUEO_SEG = 60

# Lo que el scheduler acepta como clip. Todo pasa por el perfil fijo de
# media_service (1080p30 H.264/AAC), que /ai/clip y normalizar_clip escriben en .mp4.
EXTENSIONES_VIDEO = {".mp4", ".m4v", ".mov", ".mkv"}


@dataclass(frozen=True)
class Bloque:
    nombre: str
    hora_inicio: int  # hora en settings.timezone (Argentina por default), 0-23, inclusive
    hora_fin: int  # exclusivo; si hora_fin <= hora_inicio, el bloque cruza medianoche
    prefijos: tuple[str, ...]  # prefijos de nombre_archivo que agrupan los clips de este bloque
    facultad: str | None = None  # clave de core/catalogo.FACULTADES, si es la franja de una facultad

    def activo_a_las(self, hora: int) -> bool:
        if self.hora_inicio < self.hora_fin:
            return self.hora_inicio <= hora < self.hora_fin
        return hora >= self.hora_inicio or hora < self.hora_fin  # cruza medianoche (ej. el nocturno)


# Todas las facultades: el bloque nocturno las rota, y es también el respaldo
# de cualquier bloque que todavía no tenga clips propios (ej. Prime Time).
PREFIJOS_CARRERAS = tuple(f.prefijo for f in FACULTADES.values())


def _franja(clave: str, inicio: int, fin: int) -> Bloque:
    f = FACULTADES[clave]
    return Bloque(f.nombre.removeprefix("Facultad de "), inicio, fin, (f.prefijo,), facultad=clave)


# Grilla por facultad (decidido 2026-11-27): una franja diurna por facultad
# con sus carreras de grado y posgrado (prefijo jur_, eco_, hum_, len_, art_ —
# ver core/catalogo.py), y de noche una rotación de todas las carreras.
GRILLA: list[Bloque] = [
    Bloque("UMSA Despierta", 7, 9, ("umsa_despierta_",)),
    _franja("jur", 9, 11),
    _franja("eco", 11, 13),
    _franja("hum", 13, 15),
    _franja("len", 15, 17),
    _franja("art", 17, 19),
    Bloque("Prime Time: Clases Abiertas", 19, 22, ("primetime_",)),  # sin contenido propio todavía — ver docstring
    Bloque("UMSA Nocturno", 22, 7, PREFIJOS_CARRERAS),  # rotación de todas las carreras
]


def bloque_actual(hora: int | None = None) -> Bloque:
    """Devuelve el bloque de la grilla activo a la hora dada (0-23). Si no se
    pasa `hora`, usa la hora actual en `settings.timezone` (Argentina) -- NO
    la del servidor: en Railway el contenedor corre en UTC y la grilla
    quedaba corrida 3 horas (UMSA Despierta salía de 4 a 7)."""
    hora = datetime.now(ZoneInfo(settings.timezone)).hour if hora is None else hora
    for bloque in GRILLA:
        if bloque.activo_a_las(hora):
            return bloque
    # No debería pasar nunca si GRILLA cubre las 24hs completas — si esto
    # salta, revisar que no haya un hueco en los rangos horarios.
    raise RuntimeError(f"Ningún bloque de la grilla cubre la hora {hora} — revisar GRILLA en scheduler.py")


def _videos_con_prefijo(*prefijos: str) -> list[str]:
    """Solo archivos de video: un .srt, un .tmp o cualquier otro archivo con el
    mismo prefijo que quede en media_dir no puede terminar en la playlist (ffmpeg
    cortaría la emisión al llegarle el turno). Orden: por prefijo (en el orden
    dado, ej. facultad por facultad) y dentro de cada uno alfabético, estable
    entre reloads."""
    archivos = [
        p.name for p in settings.media_dir.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES_VIDEO
    ]
    return [n for prefijo in prefijos for n in sorted(a for a in archivos if a.startswith(prefijo))]


def _clips_para(bloque: Bloque) -> list[str]:
    """Devuelve los videos de `media_dir` de los prefijos del bloque. Si no hay
    ninguno, cae a la rotación de todas las carreras y, si tampoco hay, al loop
    institucional."""
    if not settings.media_dir.exists():
        return []
    candidatos = _videos_con_prefijo(*bloque.prefijos)
    if candidatos:
        return candidatos

    carreras = _videos_con_prefijo(*PREFIJOS_CARRERAS)
    if carreras:
        logger.warning(
            f"Bloque «{bloque.nombre}» no tiene clips propios ({', '.join(bloque.prefijos)}) — "
            "usando la rotación de todas las carreras como respaldo."
        )
        return carreras

    fallback = _videos_con_prefijo(FALLBACK_PREFIX)
    if fallback:
        logger.warning(
            f"Bloque «{bloque.nombre}» no tiene clips propios ni hay clips de carreras — "
            "usando el loop de fondo institucional como respaldo."
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
                # En un hilo aparte: reload() hace stop() de ffmpeg, que puede
                # esperar hasta 10 s; corrido directo en el loop de asyncio
                # congelaba TODA la API (incluido el healthcheck) mientras tanto.
                await asyncio.to_thread(self._aplicar, bloque)
            try:
                await asyncio.wait_for(self._detener.wait(), timeout=INTERVALO_CHEQUEO_SEG)
            except TimeoutError:
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
        elif streamer.debe_estar_corriendo():
            # Se supone que estamos al aire pero ffmpeg está caído (ej. el
            # bloque anterior no tenía clips): el bloque nuevo puede traer
            # contenido, así que se intenta levantar la emisión de nuevo.
            try:
                streamer.start()
                detail += " Streamer arrancado (estaba caído)."
            except RuntimeError as e:
                logger.error(f"No se pudo arrancar el streamer al cambiar de bloque: {e}")
                detail += f" No se pudo arrancar el streamer: {e}"
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
