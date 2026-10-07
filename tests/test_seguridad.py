"""Clave de transmisión oculta, ADMIN_TOKEN obligatorio en producción y
validación de rutas que llegan por la API."""

import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core import streamer as streamer_module
from app.core.playlist_io import escribir_playlist
from app.core.streamer import CLAVE_OCULTA, FFmpegStreamer, ocultar_clave
from app.main import app

CLAVE = "clave-secreta-de-prueba-123"
client = TestClient(app)


def _clip(media_tmp, nombre="clip_a.mp4"):
    destino = media_tmp / "videos" / nombre
    if not destino.exists():
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=s=160x120:r=30",
                "-f",
                "lavfi",
                "-i",
                "sine",
                "-t",
                "1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(destino),
            ],
            check=True,
        )
    return destino


def test_ocultar_clave_reemplaza_la_clave():
    assert (
        ocultar_clave(f"rtmp://x/live2/{CLAVE}: Connection refused")
        == f"rtmp://x/live2/{CLAVE_OCULTA}: Connection refused"
    )


def test_status_publico_no_expone_la_clave_aunque_ffmpeg_la_imprima(media_tmp):
    """ffmpeg imprime la URL completa (con la clave) cuando falla la conexión
    RTMP; GET /stream/status es público y devuelve esas líneas."""
    _clip(media_tmp)
    escribir_playlist(["clip_a.mp4"])
    s = FFmpegStreamer()
    s.start()
    for _ in range(100):
        if not s.status()["running"]:
            break
        time.sleep(0.1)
    time.sleep(0.3)  # deja terminar al hilo lector de stderr
    lineas = s.status()["last_log_lines"]
    assert lineas, "ffmpeg debería haber dejado algún error (puerto RTMP cerrado)"
    assert not any(CLAVE in linea for linea in lineas)
    assert any(CLAVE_OCULTA in linea for linea in lineas)


def test_comando_ffmpeg_sin_progreso_acumulado():
    comando = FFmpegStreamer()._comando_ffmpeg()
    assert "-nostats" in comando
    assert comando[comando.index("-loglevel") + 1] == "warning"


def test_no_arranca_con_playlist_vacia():
    escribir_playlist([])
    with pytest.raises(RuntimeError, match="vacía"):
        FFmpegStreamer().start()


def test_en_produccion_no_arranca_sin_admin_token(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "admin_token", "")
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        with TestClient(app):
            pass


def test_admin_token_rechaza_token_incorrecto_o_ausente(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "token-bueno")
    assert client.post("/api/v1/stream/stop").status_code == 401
    assert client.post("/api/v1/stream/stop", headers={"X-Admin-Token": "otro"}).status_code == 401
    assert client.post("/api/v1/stream/stop", headers={"X-Admin-Token": "token-bueno"}).status_code == 200


@pytest.mark.parametrize("nombre", ["../../fuera", "../x", "a/b", "/etc/passwd", ".oculto", "a..b"])
def test_voz_rechaza_nombres_con_rutas(nombre, media_tmp):
    r = client.post("/api/v1/ai/voz", json={"texto": "hola", "nombre_archivo": nombre})
    assert r.status_code == 422
    assert not (media_tmp.parent / "fuera.wav").exists()


def test_voz_rechaza_voice_id_con_rutas():
    r = client.post("/api/v1/ai/voz", json={"texto": "hola", "nombre_archivo": "ok", "voice_id": "../../modelo"})
    assert r.status_code == 422


def test_playlist_rechaza_rutas_fuera_de_videos():
    assert client.post("/api/v1/playlist", json={"filename": "../../app/main.py"}).status_code == 422
    assert client.put("/api/v1/playlist/reorder", json={"orden": ["../x.mp4"]}).status_code == 422


@pytest.mark.parametrize(
    "imagen", ["http://169.254.169.254/latest", "../app/main.py", "/etc/passwd", "media/placas/no_existe.png"]
)
def test_clip_rechaza_imagen_fondo_fuera_de_media(imagen, monkeypatch):
    import app.api.v1.ai_generator as gen

    llamado = []
    monkeypatch.setattr(gen, "generar_guion", lambda *a, **k: llamado.append(1) or "x")
    r = client.post("/api/v1/ai/clip", json={"tema": "t", "nombre_archivo": "clip_x", "imagen_fondo": imagen})
    assert r.status_code == 400
    assert llamado == []  # no gasta crédito de IA si la imagen es inválida


def test_clip_acepta_placa_dentro_de_media(media_tmp, monkeypatch):
    from app.core.rutas import resolver_imagen_fondo

    placa = media_tmp / "placas" / "fondo.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x36", "-frames:v", "1", str(placa)],
        check=True,
    )
    assert resolver_imagen_fondo(str(placa)) == placa.resolve()


def test_streamer_singleton_usa_la_clave_de_prueba():
    assert streamer_module.settings.rtmp_stream_key == CLAVE
