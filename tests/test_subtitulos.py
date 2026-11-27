"""Subtítulos SRT (español + inglés) de los clips de /ai/clip."""

import re

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import ai_generator
from app.config import settings
from app.core import scheduler as scheduler_module
from app.main import app
from app.services.subtitulos import dividir_oraciones, generar_srt, partir_en_subtitulos

client = TestClient(app)


def test_dividir_oraciones():
    guion = "¿Querés estudiar en la UMSA? ¡Inscribite!\nLa cuota es de $1.500 hasta el 30/09.  Te esperamos…  Gracias."
    assert dividir_oraciones(guion) == [
        "¿Querés estudiar en la UMSA?",
        "¡Inscribite!",
        "La cuota es de $1.500 hasta el 30/09.",
        "Te esperamos…",
        "Gracias.",
    ]


def test_srt_valido_con_tiempos_exactos():
    srt = generar_srt(["Hola.", "Chau."], [(0.0, 1.25), (1.6, 3723.5)])
    assert srt == "1\n00:00:00,000 --> 00:00:01,250\nHola.\n\n2\n00:00:01,600 --> 01:02:03,500\nChau.\n"


def test_oracion_larga_se_parte_en_subtitulos_de_dos_lineas():
    texto = " ".join(["palabra"] * 40)  # ~320 caracteres
    partes = partir_en_subtitulos(texto, 10.0, 20.0)
    assert len(partes) > 1
    for _, _, parte in partes:
        lineas = parte.split("\n")
        assert len(lineas) <= 2 and all(len(linea) <= 42 for linea in lineas)
    assert partes[0][0] == 10.0 and partes[-1][1] == 20.0
    assert all(a[1] == pytest.approx(b[0]) for a, b in zip(partes, partes[1:], strict=False))  # sin huecos


def test_srt_rechaza_textos_y_tiempos_desparejos():
    with pytest.raises(ValueError, match="coincidir"):
        generar_srt(["a", "b"], [(0, 1)])


def test_clip_genera_srt_en_espanol_e_ingles(monkeypatch, media_tmp):
    monkeypatch.setattr(ai_generator, "generar_guion", lambda t, c: "Estudiá en la UMSA. Inscribite hoy.")
    monkeypatch.setattr(ai_generator, "traducir_oraciones", lambda o: ["Study at UMSA.", "Enroll today."])
    monkeypatch.setattr(ai_generator, "armar_clip_narrado", lambda *a, **k: None)

    r = client.post(
        "/api/v1/ai/clip",
        json={"tema": "t", "nombre_archivo": "foco_grado_subs", "agregar_a_playlist": False},
    )
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["guion_en"] == ["Study at UMSA.", "Enroll today."]
    en = open(datos["subtitulos"]["en"], encoding="utf-8").read()
    es = open(datos["subtitulos"]["es"], encoding="utf-8").read()
    assert "Study at UMSA." in en and "Inscribite hoy." in es
    # mismos tiempos en los dos idiomas
    tiempos = re.compile(r"\d\d:\d\d:\d\d,\d{3} --> \d\d:\d\d:\d\d,\d{3}")
    assert tiempos.findall(en) == tiempos.findall(es) and len(tiempos.findall(en)) == 2
    assert str(settings.subtitulos_dir) in datos["subtitulos"]["en"]


def test_clip_sin_subtitulos_no_llama_a_la_traduccion(monkeypatch, media_tmp):
    monkeypatch.setattr(ai_generator, "generar_guion", lambda t, c: "Hola.")
    monkeypatch.setattr(ai_generator, "traducir_oraciones", lambda o: pytest.fail("no debía traducir"))
    monkeypatch.setattr(ai_generator, "armar_clip_narrado", lambda *a, **k: None)
    r = client.post(
        "/api/v1/ai/clip",
        json={"tema": "t", "nombre_archivo": "sin_subs", "agregar_a_playlist": False, "subtitulos": []},
    )
    assert r.status_code == 200 and r.json()["subtitulos"] == {}


def test_scheduler_solo_toma_videos(media_tmp):
    """Un .srt con el prefijo del bloque en media/videos cortaría la emisión."""
    videos = media_tmp / "videos"
    nombres = ("hum_posgrado_zz.mp4", "hum_posgrado_zz.en.srt", "hum_posgrado_zz.tmp")
    for nombre in nombres:
        (videos / nombre).write_bytes(b"")
    try:
        bloque = next(b for b in scheduler_module.GRILLA if b.facultad == "hum")
        assert scheduler_module._clips_para(bloque) == ["hum_posgrado_zz.mp4"]
    finally:
        for nombre in nombres:
            (videos / nombre).unlink()


def test_clip_con_movimiento_y_rotulo_dura_lo_mismo_que_la_voz(media_tmp):
    """Antes quedaban ~2 s de video mudo al final (-shortest con imagen en loop)."""
    import subprocess

    from app.services.media_service import armar_clip_narrado, probar_clip

    audio = media_tmp / "audio_rotulo.wav"
    placa = media_tmp / "placas" / "vertical.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=1.5", str(audio)], check=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=400x900", "-frames:v", "1", str(placa)],
        check=True,
    )
    destino = media_tmp / "videos" / "rotulo_prueba.mp4"
    try:
        armar_clip_narrado(audio, destino, imagen_fondo=placa, rotulo="Licenciatura en Psicología: 100% práctica",
                           rotulo_secundario="Facultad de Ciencias Humanas · Grado · presencial")
        info = probar_clip(destino)
        assert info["resolucion"] == "1920x1080"
        assert abs(info["duracion_seg"] - 1.5) < 0.1
        assert not list(destino.parent.glob(".rotulo_prueba.*"))  # temporales borrados
    finally:
        destino.unlink(missing_ok=True)
