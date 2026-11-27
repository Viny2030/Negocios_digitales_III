"""Envío de subtítulos a YouTube por URL (pista CC)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import settings
from app.core import subtitulos_youtube as sy

AHORA = datetime(2026, 12, 1, 15, 0, 0, tzinfo=UTC)


@pytest.fixture
def emisor(monkeypatch):
    monkeypatch.setattr(settings, "youtube_captions_url", "https://upload.youtube.com/closedcaption?cid=abc")
    enviados = []
    e = sy.EmisorSubtitulosYouTube()
    monkeypatch.setattr(e, "_enviar", lambda momento, texto: enviados.append((momento, texto)))
    return e, enviados


def _al_aire(cues):
    return lambda idioma, ahora, ventana, demora: {"al_aire": True, "clip": "x.mp4", "cues": cues}


def test_envia_cada_subtitulo_una_sola_vez_al_empezar(emisor, monkeypatch):
    e, enviados = emisor
    monkeypatch.setattr(sy, "subtitulos_al_aire", _al_aire([{"desde": 0.2, "hasta": 3.0, "texto": "Hello\nthere."}]))
    e.chequear(AHORA)
    # El mismo subtítulo medio segundo después: ahora "empezó hace 0,3 s"
    # (cruza el borde de un segundo entero: antes se reenviaba).
    monkeypatch.setattr(sy, "subtitulos_al_aire", _al_aire([{"desde": -0.299, "hasta": 2.5, "texto": "Hello\nthere."}]))
    e.chequear(AHORA + timedelta(seconds=0.5))
    assert enviados == [(AHORA + timedelta(seconds=0.2), "Hello there.")]


def test_no_envia_lo_que_empezo_hace_rato_ni_lo_futuro(emisor, monkeypatch):
    e, enviados = emisor
    cues = [{"desde": -3.0, "hasta": 1.0, "texto": "Viejo."}, {"desde": 5.0, "hasta": 8.0, "texto": "Futuro."}]
    monkeypatch.setattr(sy, "subtitulos_al_aire", _al_aire(cues))
    e.chequear(AHORA)
    assert enviados == []


def test_sin_url_no_hace_nada(monkeypatch):
    monkeypatch.setattr(settings, "youtube_captions_url", "")
    monkeypatch.setattr(sy, "subtitulos_al_aire", lambda *a, **k: pytest.fail("no debía calcular nada"))
    sy.EmisorSubtitulosYouTube().chequear(AHORA)


def test_formato_del_post(monkeypatch):
    monkeypatch.setattr(settings, "youtube_captions_url", "https://upload.youtube.com/closedcaption?cid=abc")
    capturado = {}

    class _Resp:
        def raise_for_status(self):
            pass

    def post(url, content, headers, timeout):
        capturado.update(url=url, cuerpo=content.decode("utf-8"), tipo=headers["Content-Type"])
        return _Resp()

    monkeypatch.setattr(sy.httpx, "post", post)
    e = sy.EmisorSubtitulosYouTube()
    e._enviar(datetime(2026, 12, 1, 15, 0, 1, 250000, tzinfo=UTC), "Study at UMSA.")
    assert capturado == {
        "url": "https://upload.youtube.com/closedcaption?cid=abc&seq=1",
        "cuerpo": "2026-12-01T15:00:01.250\nStudy at UMSA.\n",
        "tipo": "text/plain",
    }
    assert e.estado()["enviados_ok"] == 1
