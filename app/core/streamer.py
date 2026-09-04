"""
core/streamer.py — Wrapper del subproceso FFmpeg que sostiene la emisión
RTMP 24/7 en loop, leyendo la playlist con el demuxer "concat".

Decisión de diseño clave (la misma que menciona el documento de costos):
usar `-c copy` (stream copy, sin recodificar) para que el contenedor en
Railway consuma CPU/RAM mínimos. PERO stream copy con el demuxer concat
tiene una restricción real que el documento no menciona: todos los clips
de la playlist tienen que compartir el MISMO códec, resolución, fps y
sample rate de audio — si no, el concat con -c copy falla o produce un
video con audio/video desincronizado o cortes. Por eso `media_service.py`
normaliza cada clip a un perfil fijo ANTES de agregarlo a la playlist
(ver services/media_service.py) — el streamer en sí no valida esto de
nuevo en cada arranque, confía en que playlist.py ya lo garantizó al
agregar el clip.

Limitación conocida de "reload": el demuxer concat de FFmpeg lee la
playlist una sola vez, al arrancar — no existe una forma soportada de
inyectarle clips nuevos a un proceso ffmpeg ya corriendo sin cortar la
señal. `reload()` acá abajo reinicia el proceso (stop + start): hay un
corte de señal de un par de segundos en el peor caso, no un hot-swap real.
Si más adelante hace falta un hot-swap sin corte, la alternativa es
FFmpeg leyendo de un named pipe / `ffconcat` regenerado con seek, que es
bastante más complejo — no vale la pena para el alcance actual.
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger("streamer")


@dataclass
class _EstadoStreamer:
    proceso: subprocess.Popen | None = None
    started_at: datetime | None = None
    return_code: int | None = None
    log_lines: deque[str] = field(default_factory=lambda: deque(maxlen=200))


class FFmpegStreamer:
    """Controla un único proceso ffmpeg a la vez. Pensado como singleton
    (ver `streamer` al final del archivo) — no soporta múltiples streams
    concurrentes, que no es un caso de uso de este proyecto."""

    def __init__(self) -> None:
        self._estado = _EstadoStreamer()
        self._lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None

    def _comando_ffmpeg(self) -> list[str]:
        if not settings.rtmp_stream_key:
            raise RuntimeError(
                "RTMP_STREAM_KEY no está seteada — no se puede transmitir sin la "
                "clave de stream de YouTube Live. Ver .env.example."
            )
        destino = f"{settings.rtmp_url}/{settings.rtmp_stream_key}"
        return [
            settings.ffmpeg_bin,
            "-re",  # respeta el framerate original en vez de leer el archivo lo más rápido posible
            "-stream_loop", "-1",  # repite la playlist entera indefinidamente
            "-f", "concat",
            "-safe", "0",
            "-i", str(settings.playlist_path),
            "-c", "copy",  # sin recodificar — ver docstring del módulo
            "-f", "flv",
            destino,
        ]

    def _leer_stderr(self, proceso: subprocess.Popen) -> None:
        """FFmpeg escribe su progreso y errores en stderr. Hay que drenarlo en
        un hilo aparte: si nadie lee ese pipe y se llena el buffer del SO,
        ffmpeg se cuelga esperando que alguien lo vacíe."""
        assert proceso.stderr is not None
        for linea in proceso.stderr:
            texto = linea.decode("utf-8", errors="replace").rstrip()
            if texto:
                self._estado.log_lines.append(texto)
        proceso.wait()
        with self._lock:
            self._estado.return_code = proceso.returncode
            if proceso.returncode != 0:
                logger.error(f"ffmpeg terminó con código {proceso.returncode} — ver last_log_lines en /status")

    def start(self) -> None:
        with self._lock:
            if self._estado.proceso is not None and self._estado.proceso.poll() is None:
                raise RuntimeError("El streamer ya está corriendo — llamá a /stop o /reload primero.")
            comando = self._comando_ffmpeg()
            logger.info(f"Arrancando ffmpeg: {' '.join(comando)}")
            proceso = subprocess.Popen(
                comando,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._estado = _EstadoStreamer(proceso=proceso, started_at=datetime.now(timezone.utc))
            self._reader_thread = threading.Thread(
                target=self._leer_stderr, args=(proceso,), daemon=True
            )
            self._reader_thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        with self._lock:
            proceso = self._estado.proceso
        if proceso is None or proceso.poll() is not None:
            return  # ya estaba parado, no es un error
        proceso.terminate()  # SIGTERM — le da tiempo a ffmpeg a cerrar el stream prolijo
        try:
            proceso.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg no respondió a SIGTERM a tiempo — forzando con SIGKILL")
            proceso.kill()
            proceso.wait()

    def reload(self) -> None:
        """Reinicia el proceso para que relea la playlist. Ver limitación en
        el docstring del módulo: esto corta la señal un par de segundos."""
        self.stop()
        self.start()

    def status(self) -> dict:
        with self._lock:
            estado = self._estado
            proceso = estado.proceso
            corriendo = proceso is not None and proceso.poll() is None
            uptime = None
            if estado.started_at is not None:
                uptime = (datetime.now(timezone.utc) - estado.started_at).total_seconds()
            return {
                "running": corriendo,
                "pid": proceso.pid if corriendo else None,
                "started_at": estado.started_at.isoformat() if estado.started_at else None,
                "uptime_seconds": uptime,
                "return_code": estado.return_code,
                "last_log_lines": list(estado.log_lines)[-20:],
            }


# Singleton — importado por los routers de la API. Ver app/main.py para el
# arranque/apagado automático (AUTOSTART) vía el lifespan de FastAPI.
streamer = FFmpegStreamer()
