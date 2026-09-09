"""
config.py — Configuración central del servicio (Pydantic Settings).

Todo se lee de variables de entorno (ver .env.example). No hay valores por
defecto para credenciales/secretos: si falta alguno de esos, el servicio
arranca igual (para poder levantar el control panel y probar el streamer
con un fallback local), pero cada servicio que dependa de esa credencial
avisa explícitamente en vez de fallar en silencio — ver services/ai_service.py.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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
    media_dir: Path = Path("media/videos")
    playlist_path: Path = Path("media/playlist.txt")

    # --- Grilla horaria automática (ver core/scheduler.py) ---
    # SCHEDULER_ENABLED=true (default) mantiene playlist.txt sincronizada con
    # el bloque horario de la grilla de 24hs (ver
    # Claude outputs/plan_contenido_canal_umsa.md) sin intervención manual.
    # Ponelo en false si querés armar la playlist a mano (POST /api/v1/playlist)
    # sin que el scheduler te la pise en el próximo cambio de bloque.
    scheduler_enabled: bool = True

    # --- LLM (guiones) ---
    # generar_guion() prueba Anthropic primero si anthropic_api_key está
    # seteada; si no, cae a OpenAI; si tampoco hay OpenAI, devuelve un guion
    # [SIMULADO] (ver services/ai_service.py).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
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


settings = Settings()
settings.media_dir.mkdir(parents=True, exist_ok=True)
settings.audio_dir.mkdir(parents=True, exist_ok=True)
settings.tts_models_dir.mkdir(parents=True, exist_ok=True)
settings.playlist_path.parent.mkdir(parents=True, exist_ok=True)
