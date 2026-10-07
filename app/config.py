"""
config.py — Configuración central del servicio (Pydantic Settings).

Todo se lee de variables de entorno (ver .env.example). No hay valores por
defecto para credenciales/secretos: si falta alguno de esos, el servicio
arranca igual (para poder levantar el control panel y probar el streamer
con un fallback local), pero cada servicio que dependa de esa credencial
avisa explícitamente en vez de fallar en silencio — ver services/ai_service.py.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Entorno ---
    # "development" (local) o "production" (deploy público). Si no se define,
    # se detecta solo: dentro de Railway (variable RAILWAY_ENVIRONMENT_NAME,
    # que Railway inyecta siempre) es "production". En producción:
    #   - la app NO arranca sin ADMIN_TOKEN (la URL de Railway es pública);
    #   - no hay placeholders: sin LLM o sin modelo de voz, /ai/* falla con un
    #     error claro en vez de generar un clip "[SIMULADO]" o de silencio que
    #     terminaría saliendo AL AIRE en el canal.
    app_env: Literal["development", "production"] | None = None

    # Zona horaria de la grilla de programación (ver core/scheduler.py). Los
    # bloques están pensados en hora argentina; sin esto el scheduler usaba la
    # hora del servidor, que en Railway es UTC (todo corrido 3 horas).
    timezone: str = "America/Argentina/Buenos_Aires"

    # --- Emisión RTMP ---
    rtmp_url: str = "rtmp://a.rtmp.youtube.com/live2"
    rtmp_stream_key: str = ""

    # --- FFmpeg ---
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    # AUTOSTART=true levanta el streamer solo al arrancar el proceso (útil en
    # producción); en desarrollo local conviene dejarlo en false y arrancarlo
    # a mano desde POST /api/v1/stream/start.
    autostart: bool = False

    # --- Playlist / medios ---
    # Raíz de medios: `imagen_fondo` (POST /ai/clip) solo puede apuntar a un
    # archivo dentro de esta carpeta (ej. media/placas/...), nunca a una ruta
    # cualquiera del servidor ni a una URL.
    media_root: Path = Path("media")
    media_dir: Path = Path("media/videos")
    playlist_path: Path = Path("media/playlist.txt")

    # --- Grilla horaria automática (ver core/scheduler.py) ---
    # SCHEDULER_ENABLED=true (default) mantiene playlist.txt sincronizada con
    # el bloque horario de la grilla de 24hs (ver
    # Claude outputs/plan_contenido_canal_umsa.md) sin intervención manual.
    # Ponelo en false si querés armar la playlist a mano (POST /api/v1/playlist)
    # sin que el scheduler te la pise en el próximo cambio de bloque.
    scheduler_enabled: bool = True

    # --- Watchdog del streamer (ver core/watchdog.py) ---
    # Si ffmpeg se cae solo (corte de red hacia YouTube, frame corrupto,
    # etc.) mientras se suponía que tenía que seguir transmitiendo, el
    # watchdog lo reinicia automáticamente — sin esto, la señal queda caída
    # hasta que alguien lo note y llame a POST /stream/start a mano, algo
    # inaceptable para un canal pensado para emisión PERMANENTE 24/7.
    watchdog_enabled: bool = True
    watchdog_check_interval_seg: int = 15
    # Techo de reintentos por ventana de tiempo, para no quedar en un loop
    # de reinicios infinito si ffmpeg sigue muriendo (ej. stream key
    # inválida) — pasado el techo, el watchdog deja de insistir y loguea
    # CRITICAL hasta un POST /stream/start manual (que resetea el contador).
    watchdog_max_reintentos: int = 5
    watchdog_ventana_seg: int = 600

    # --- Seguridad ---
    # Si se define, protege con el header 'X-Admin-Token' los endpoints que
    # controlan el stream en vivo (/stream/start|stop|reload|schedule/force),
    # la playlist (altas/bajas/reorder) y la generación de contenido con IA
    # (/ai/*, que consume créditos pagos de Anthropic/OpenAI). Vacío/None
    # (default) = sin protección — cómodo en desarrollo local, pero
    # OBLIGATORIO configurar un valor propio en Railway: esa URL es pública
    # y sin este token cualquiera podría cortar la transmisión o gastar la
    # cuota de IA llamando a /ai/clip en loop.
    admin_token: str = ""

    # --- LLM (guiones) ---
    # generar_guion() prueba Anthropic primero si anthropic_api_key está
    # seteada; si no, cae a OpenAI; si tampoco hay OpenAI, devuelve un guion
    # [SIMULADO] (ver services/ai_service.py).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- TTS (voz) — Piper: motor neuronal local (pip install piper-tts),
    # sin costo ni cuota. generar_voz() en services/ai_service.py busca el
    # modelo <voice_id o piper_voice_default>.onnx (+ su .onnx.json) dentro
    # de tts_models_dir; si no lo encuentra, cae a un wav de silencio (mismo
    # comportamiento de placeholder que antes con ElevenLabs cuando faltaba
    # la API key, para no bloquear el resto del pipeline).
    piper_bin: str = "piper"
    tts_models_dir: Path = Path("media/tts")
    piper_voice_default: str = "es_AR-daniela-high"
    audio_dir: Path = Path("media/audio")

    log_level: str = "INFO"

    @model_validator(mode="after")
    def _resolver_entorno(self):
        if self.app_env is None:
            en_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_ENVIRONMENT"))
            self.app_env = "production" if en_railway else "development"
        return self

    @property
    def es_produccion(self) -> bool:
        return self.app_env == "production"


settings = Settings()
settings.media_dir.mkdir(parents=True, exist_ok=True)
settings.audio_dir.mkdir(parents=True, exist_ok=True)
settings.tts_models_dir.mkdir(parents=True, exist_ok=True)
settings.playlist_path.parent.mkdir(parents=True, exist_ok=True)
