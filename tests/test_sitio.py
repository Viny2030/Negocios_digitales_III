"""Página pública: video, manual y grafos en español e inglés."""

import importlib.util
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.scheduler import GRILLA
from app.main import app

RAIZ = Path(__file__).resolve().parent.parent
CANAL = "UC" + "a" * 22
client = TestClient(app)


def _generador():
    spec = importlib.util.spec_from_file_location("generar_sitio", RAIZ / "scripts" / "generar_sitio.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


gen = _generador()


class _Textos(HTMLParser):
    """Junta los textos de cada nodo (<g class="nodo">) de los SVG."""

    def __init__(self):
        super().__init__()
        self.nodos, self._dentro, self._actual = [], 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "g" and "nodo" in (dict(attrs).get("class") or ""):
            self._dentro, self._actual = 1, []

    def handle_endtag(self, tag):
        if tag == "g" and self._dentro:
            self.nodos.append(" ".join(self._actual).strip())
            self._dentro = 0

    def handle_data(self, data):
        if self._dentro:
            self._actual.append(data.strip())


@pytest.mark.parametrize("lang", ["es", "en"])
def test_los_html_commiteados_estan_al_dia_con_el_generador(lang):
    commiteado = (RAIZ / "app" / "static" / f"sitio_{lang}.html").read_text(encoding="utf-8")
    assert commiteado == gen.render(lang), "Correr: python scripts/generar_sitio.py"


@pytest.mark.parametrize("ruta,lang", [("/", "es"), ("/en", "en")])
def test_pagina_responde_con_manual_y_dos_grafos(ruta, lang):
    r = client.get(ruta)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert f'<html lang="{lang}">' in html
    assert 'id="manual"' in html and 'id="grafo-funcionamiento"' in html and 'id="grafo-informacion"' in html
    assert html.count("<svg") == 2
    assert "__" not in html.replace("__init__", "")  # ningún marcador sin reemplazar


@pytest.mark.parametrize("lang", ["es", "en"])
def test_todos_los_nodos_tienen_nombre(lang):
    p = _Textos()
    p.feed(gen.render(lang))
    esperados = len(gen.NODOS_FUNC) + len(gen.BLOQUES) + len(gen.CONTENIDOS)
    assert len(p.nodos) == esperados
    assert all(texto for texto in p.nodos)


def test_ambos_idiomas_comparten_el_dibujo():
    """Mismas cajas y flechas en las mismas posiciones: solo cambian los textos."""

    def forma(lang):
        html = gen.render(lang)
        return re.findall(r'<rect [^>]+>|<path d="[^"]+" class="arista"', html)

    assert forma("es") == forma("en")


def test_el_grafo_de_informacion_cubre_toda_la_grilla_y_todas_las_carreras():
    from app.core.catalogo import PROGRAMAS

    assert [b[1] for b in gen.BLOQUES] == [b.nombre for b in GRILLA]
    es, en = client.get("/").text, client.get("/en").text
    for bloque in GRILLA:
        assert bloque.nombre in es
        assert gen.BLOQUE_EN[bloque.nombre] in en
    # Cada carrera del catálogo aparece con su nombre (los largos van partidos en líneas)
    texto_es = " ".join(_Textos_de(es))
    texto_en = " ".join(_Textos_de(en))
    for p in PROGRAMAS:
        assert " ".join(p.nombre.split()) in texto_es, p.nombre
        assert " ".join(p.nombre_en.split()) in texto_en, p.nombre_en


def _Textos_de(html):
    p = _Textos()
    p.feed(html)
    return p.nodos


def test_sin_canal_muestra_aviso_y_no_reproductor(monkeypatch):
    monkeypatch.setattr(settings, "youtube_channel_id", "")
    html = client.get("/").text
    assert "YOUTUBE_CHANNEL_ID" in html
    assert "<iframe" not in html


def test_con_canal_valido_incrusta_el_vivo(monkeypatch):
    monkeypatch.setattr(settings, "youtube_channel_id", CANAL)
    html = client.get("/en").text
    assert f"youtube-nocookie.com/embed/live_stream?channel={CANAL}" in html


@pytest.mark.parametrize("malo", ['UCx"><script>alert(1)</script>', "UC123", "https://youtube.com/@umsa", "UC" + "a" * 23])
def test_canal_invalido_no_se_inyecta(monkeypatch, malo):
    monkeypatch.setattr(settings, "youtube_channel_id", malo)
    html = client.get("/").text
    assert "<iframe" not in html
    assert "<script>alert" not in html


def test_info_json_sigue_disponible():
    r = client.get("/api/v1/info")
    assert r.status_code == 200
    assert r.json()["docs"] == "/docs"
