"""
core/watchdog.py — Vigila que el streamer siga corriendo cuando se supone
que tiene que estar corriendo, y lo reinicia solo si se cayó de forma
inesperada (ej. un corte de red hacia YouTube, un frame corrupto que hace
abortar a ffmpeg) — sin esto, un crash de ffmpeg deja la señal caída hasta
que alguien lo note y llame a POST /stream/start a mano, algo inaceptable
para un canal pensado para emisión PERMANENTE 24/7 (ver README, sección
"Deploy en Railway").

No reemplaza a reload() (cambio de bloque horario, ver core/scheduler.py):
ese es un reinicio INTENCIONAL (stop + start), y start() vuelve a marcar
`streamer.debe_estar_corriendo() == True` de una. Este watchdog solo actúa
cuando el proceso murió SOLO mientras se suponía que tenía que seguir
transmitiendo (`debe_estar_corriendo()` True pero `status()["running"]`
False).

Backoff con techo: reintenta enseguida las primeras veces; si ffmpeg sigue
muriendo en loop (ej. RTMP_STREAM_KEY inválida, o YouTube rechazando la
conexión) hay un límite de reintentos por ventana de tiempo
(WATCHDOG_MAX_REINTENTOS / WATCHDOG_VENTANA_SEG) para no quedar en un loop
de reinicios infinito quemando CPU/red — pasado el límite, deja de
reintentar y loguea CRITICAL hasta un POST /stream/start manual (que
resetea el contador al arrancar el watchdog de nuevo... en realidad el
contador se resetea recién en el próximo `start()` del proceso completo;
ver `estado()`/`WatchdogStatus.agotado` para saber si hace falta intervenir
a mano).
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone

from app.config import settings
from app.core.streamer import streamer

logger = logging.getLogger("watchdog")


class StreamWatchdog:
    """Task de background que reinicia el streamer si se cae solo. Arranca/
    para desde el lifespan de FastAPI (ver app/main.py, settings.watchdog_enabled)."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._detener = asyncio.Event()
        self._reintentos: deque[datetime] = deque()
        self._agotado = False

    def _reintentos_recientes(self) -> int:
        limite = datetime.now(timezone.utc).timestamp() - settings.watchdog_ventana_seg
        while self._reintentos and self._reintentos[0].timestamp() < limite:
            self._reintentos.popleft()
        return len(self._reintentos)

    async def _ciclo(self) -> None:
        while not self._detener.is_set():
            try:
                await asyncio.wait_for(self._detener.wait(), timeout=settings.watchdog_check_interval_seg)
                break  # nos pidieron parar
            except asyncio.TimeoutError:
                pass  # chequeo normal cada watchdog_check_interval_seg

            if not streamer.debe_estar_corriendo() or streamer.status()["running"]:
                continue  # todo en orden: parado a propósito, o corriendo bien

            if self._agotado:
                continue  # ya se acabaron los reintentos — no insistir hasta un start() manual

            if self._reintentos_recientes() >= settings.watchdog_max_reintentos:
                self._agotado = True
                logger.critical(
                    f"Watchdog: ffmpeg se cayó {settings.watchdog_max_reintentos} veces en los "
                    f"últimos {settings.watchdog_ventana_seg}s — dejo de reintentar. Revisar a mano "
                    f"(GET /api/v1/stream/status para el último log de ffmpeg) y volver a arrancar "
                    f"con POST /stream/start cuando esté resuelto."
                )
                continue

            logger.warning("Watchdog: el streamer se cayó inesperadamente — reintentando arranque.")
            self._reintentos.append(datetime.now(timezone.utc))
            try:
                streamer.start()
            except RuntimeError as e:
                logger.error(f"Watchdog: no se pudo reiniciar el streamer: {e}")

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._detener.clear()
        self._agotado = False
        self._reintentos.clear()
        self._task = asyncio.create_task(self._ciclo())
        logger.info(
            f"Watchdog del streamer arrancado (chequeo cada {settings.watchdog_check_interval_seg}s, "
            f"máximo {settings.watchdog_max_reintentos} reintentos por {settings.watchdog_ventana_seg}s)."
        )

    def stop(self) -> None:
        self._detener.set()
        if self._task is not None:
            self._task.cancel()
        logger.info("Watchdog del streamer detenido.")

    def estado(self) -> dict:
        return {
            "corriendo": self._task is not None and not self._task.done(),
            "reintentos_recientes": self._reintentos_recientes(),
            "agotado": self._agotado,
        }


# Singleton — importado por app/main.py (lifespan) y api/v1/stream.py (endpoint de estado).
watchdog = StreamWatchdog()
