"""Subtítulos de lo que se está emitiendo (para la página pública)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core import al_aire
from app.main import app
from app.services.subtitulos import generar_srt, guardar_srt

client = TestClient(app)
INICIO = datetime(2026, 12, 1, 12, 0, 0, tzinfo=UTC)


class _Emision:
    def __init__(self, clips):
        self.clips = clips

    def emision_actual(self):
        return (self.clips, INICIO) if self.clips is not None else None


@pytest.fixture
def emitiendo(monkeypatch):
    """Dos clips de 10 s: A con dos oraciones, B sin subtítulos."""
    monkeypatch.setattr(settings, "subtitulos_demora_seg", 0.0)
    monkeypatch.setattr(al_aire, "duracion", lambda nombre: 10.0)
    guardar_srt("test_a", "en", generar_srt(["First.", "Second."], [(0.0, 4.0), (5.0, 9.0)]))
    al_aire._cues_cacheados.cache_clear()

    def poner(clips):
        monkeypatch.setattr(al_aire, "streamer", _Emision(clips))

    return poner


def _en(segundos):
    return INICIO + timedelta(seconds=segundos)


def test_sin_emision_no_hay_subtitulos(emitiendo):
    emitiendo(None)
    assert al_aire.subtitulos_al_aire("en") == {"al_aire": False, "clip": None, "cues": []}


def test_subtitulos_relativos_a_ahora(emitiendo):
    emitiendo(["test_a.mp4", "test_b.mp4"])
    r = al_aire.subtitulos_al_aire("en", ahora=_en(2.0), ventana=20)
    assert r["clip"] == "test_a.mp4"
    # A empezó hace 2 s; B (sin srt) no aporta; A vuelve a empezar en 18 s (fuera de la ventana salvo su inicio)
    assert r["cues"] == [
        {"desde": -2.0, "hasta": 2.0, "texto": "First."},
        {"desde": 3.0, "hasta": 7.0, "texto": "Second."},
        {"desde": 18.0, "hasta": 22.0, "texto": "First."},
    ]


def test_loop_vuelve_al_primer_clip(emitiendo):
    emitiendo(["test_a.mp4", "test_b.mp4"])
    r = al_aire.subtitulos_al_aire("en", ahora=_en(20 * 3 + 15.0), ventana=10)  # 3 vueltas + mitad de B
    assert r["clip"] == "test_b.mp4"
    assert r["cues"][0] == {"desde": 5.0, "hasta": 9.0, "texto": "First."}


def test_demora_de_youtube_atrasa_los_subtitulos(emitiendo, monkeypatch):
    emitiendo(["test_a.mp4", "test_b.mp4"])
    monkeypatch.setattr(settings, "subtitulos_demora_seg", 20.0)
    r = al_aire.subtitulos_al_aire("en", ahora=_en(22.0), ventana=5)  # el espectador ve el segundo 2
    assert r["cues"][0]["texto"] == "First." and r["cues"][0]["desde"] == -2.0
    # Recién arrancado: el espectador todavía no ve nada; A empieza dentro de 15 s
    r = al_aire.subtitulos_al_aire("en", ahora=_en(5.0), ventana=20)
    assert r["clip"] is None
    assert r["cues"][0] == {"desde": 15.0, "hasta": 19.0, "texto": "First."}


def test_clip_sin_duracion_no_inventa_posicion(emitiendo, monkeypatch):
    emitiendo(["test_a.mp4"])
    monkeypatch.setattr(al_aire, "duracion", lambda nombre: None)
    assert al_aire.subtitulos_al_aire("en", ahora=_en(1.0))["cues"] == []


def test_endpoint_publico(emitiendo):
    emitiendo(None)
    r = client.get("/api/v1/stream/subtitulos?idioma=en")
    assert r.status_code == 200 and r.json()["al_aire"] is False
    assert client.get("/api/v1/stream/subtitulos?idioma=fr").status_code == 422


def test_parsear_srt_ida_y_vuelta():
    srt = generar_srt(["Hola.", "Línea larga " * 8], [(0.5, 1.5), (2.0, 6.0)])
    cues = al_aire.parsear_srt(srt)
    assert cues[0] == (0.5, 1.5, "Hola.")
    assert cues[-1][1] == 6.0 and "\n" in cues[1][2]


@pytest.mark.parametrize("ruta,lang", [("/", "es"), ("/en", "en")])
def test_pagina_tiene_barra_de_subtitulos(ruta, lang):
    html = client.get(ruta).text
    assert f'id="subtitulo" class="subtitulo vacio" lang="{lang}"' in html
    assert "/api/v1/stream/subtitulos?idioma=" in html
