"""
Configuración de tests: aísla el entorno ANTES de importar la app.

`app.config.settings` se crea al importar el módulo y lee `.env` — que en
local tiene la clave real de YouTube y las API keys. Las variables de entorno
pisan al `.env`, así que acá se fijan valores de prueba (clave falsa, sin
LLMs, carpetas temporales, sin scheduler/watchdog/autostart) para que ningún
test toque servicios reales ni la carpeta media/ del proyecto.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="umsa_tests_"))
(_TMP / "media" / "videos").mkdir(parents=True)
(_TMP / "media" / "placas").mkdir(parents=True)

os.environ.update(
    {
        "APP_ENV": "development",
        "RTMP_URL": "rtmp://127.0.0.1:1/live2",  # puerto cerrado: ffmpeg falla enseguida, sin red
        "RTMP_STREAM_KEY": "clave-secreta-de-prueba-123",
        "ADMIN_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "AUTOSTART": "false",
        "SCHEDULER_ENABLED": "false",
        "WATCHDOG_ENABLED": "false",
        "MEDIA_ROOT": str(_TMP / "media"),
        "MEDIA_DIR": str(_TMP / "media" / "videos"),
        "PLAYLIST_PATH": str(_TMP / "media" / "playlist.txt"),
        "AUDIO_DIR": str(_TMP / "media" / "audio"),
        "TTS_MODELS_DIR": str(_TMP / "tts"),
    }
)

import pytest  # noqa: E402


@pytest.fixture
def media_tmp() -> Path:
    return _TMP / "media"
