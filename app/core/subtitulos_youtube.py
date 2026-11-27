"""
core/subtitulos_youtube.py — Envía los subtítulos de lo que está al aire a
YouTube como pista CC (envío por URL, "Publicar subtítulos en URL").

Cada ~0,5 s calcula qué subtítulo empieza ahora (core/al_aire.py, sin demora:
YouTube alinea los subtítulos con la señal según el timestamp de cada envío) y
lo manda una sola vez por POST a YOUTUBE_CAPTIONS_URL.

Formato del envío (el que usan los programas de subtitulado en vivo con
YouTube; Google no publica la especificación, se pide por formulario a
proveedores): un POST text/plain a la URL de ingesta con `&seq=N` (N creciente)
y cuerpo

    2026-12-01T12:00:00.000
    texto del subtítulo

con la hora en UTC. VERIFICAR contra un evento real antes de confiar en esto
(ver README): si YouTube no muestra nada, el log dice qué respondió.

Requisitos del lado de YouTube: evento en latencia "Normal" y una sola pista
de subtítulos por transmisión (por eso YOUTUBE_CAPTIONS_IDIOMA elige una).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings
from app.core.al_aire import subtitulos_al_aire

logger = logging.getLogger("subtitulos_youtube")

INTERVALO_SEG = 0.5
# Un subtítulo se envía si empieza dentro de esta ventana alrededor de "ahora"
# (cubre el intervalo entre chequeos y algo de jitter del loop).
TOLERANCIA_SEG = 1.0


class EmisorSubtitulosYouTube:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._detener = asyncio.Event()
        self._seq = 0
        self._enviados: dict[tuple[str, float], datetime] = {}  # (texto, inicio epoch) → cuándo se envió
        self.ultimo_error: str | None = None
        self.enviados_ok = 0

    def _enviar(self, momento: datetime, texto: str) -> None:
        self._seq += 1
        cuerpo = f"{momento.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}\n{texto}\n"
        separador = "&" if "?" in settings.youtube_captions_url else "?"
        url = f"{settings.youtube_captions_url}{separador}seq={self._seq}"
        try:
            r = httpx.post(url, content=cuerpo.encode("utf-8"), headers={"Content-Type": "text/plain"}, timeout=5)
            r.raise_for_status()
            self.enviados_ok += 1
            self.ultimo_error = None
        except httpx.HTTPError as e:
            # Nunca loguear la URL: está firmada y permite publicar subtítulos en el evento.
            detalle = getattr(getattr(e, "response", None), "text", "")[:200]
            self.ultimo_error = f"{type(e).__name__}: {detalle or e.__class__.__doc__ or ''}".strip()
            logger.warning(f"YouTube rechazó/no recibió el subtítulo seq={self._seq}: {self.ultimo_error}")

    def chequear(self, ahora: datetime | None = None) -> None:
        if not settings.youtube_captions_url:
            return
        ahora = ahora or datetime.now(UTC)
        datos = subtitulos_al_aire(settings.youtube_captions_idioma, ahora=ahora, ventana=TOLERANCIA_SEG, demora=0.0)
        for cue in datos["cues"]:
            if not (-TOLERANCIA_SEG < cue["desde"] <= TOLERANCIA_SEG):
                continue  # ya empezado hace rato (se envió antes) o todavía no
            inicio = ahora + timedelta(seconds=cue["desde"])
            # Mismo texto con un inicio a menos de 2 s = el mismo subtítulo visto
            # en otro chequeo (no se compara por igualdad: el cálculo varía en ms).
            if any(t == cue["texto"] and abs(i - inicio.timestamp()) < 2 for t, i in self._enviados):
                continue
            self._enviados[(cue["texto"], inicio.timestamp())] = ahora
            # YouTube muestra cada línea por separado; un salto de línea del SRT
            # (2 líneas de 42 caracteres) se manda como un solo subtítulo.
            self._enviar(inicio, cue["texto"].replace("\n", " "))
        limite = ahora - timedelta(minutes=2)
        self._enviados = {k: v for k, v in self._enviados.items() if v > limite}

    async def _ciclo(self) -> None:
        while not self._detener.is_set():
            await asyncio.to_thread(self.chequear)  # el POST es bloqueante: fuera del loop de asyncio
            try:
                await asyncio.wait_for(self._detener.wait(), timeout=INTERVALO_SEG)
            except TimeoutError:
                pass

    def start(self) -> None:
        if not settings.youtube_captions_url or (self._task is not None and not self._task.done()):
            return
        self._detener.clear()
        self._task = asyncio.create_task(self._ciclo())
        logger.info(f"Envío de subtítulos a YouTube activado (idioma {settings.youtube_captions_idioma}).")

    def stop(self) -> None:
        self._detener.set()
        if self._task is not None:
            self._task.cancel()

    def estado(self) -> dict:
        return {
            "activo": self._task is not None and not self._task.done(),
            "idioma": settings.youtube_captions_idioma,
            "enviados_ok": self.enviados_ok,
            "ultimo_error": self.ultimo_error,
        }


emisor_subtitulos = EmisorSubtitulosYouTube()
