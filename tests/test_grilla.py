"""Grilla por facultad y catálogo de carreras."""

import pytest

from app.core import scheduler as sch
from app.core.catalogo import FACULTADES, PROGRAMAS, RENOMBRES_ANTERIORES
from app.core.rutas import validar_nombre


def test_la_grilla_cubre_las_24_horas_sin_superposiciones():
    for hora in range(24):
        activos = [b.nombre for b in sch.GRILLA if b.activo_a_las(hora)]
        assert len(activos) == 1, (hora, activos)


def test_cada_facultad_tiene_su_franja_y_el_nocturno_las_rota_todas():
    assert {b.facultad for b in sch.GRILLA if b.facultad} == set(FACULTADES)
    nocturno = sch.bloque_actual(3)
    assert set(nocturno.prefijos) == {f.prefijo for f in FACULTADES.values()}


def test_nombres_de_archivo_del_catalogo_son_validos_y_unicos():
    nombres = [p.nombre_archivo for p in PROGRAMAS]
    assert len(nombres) == len(set(nombres))
    for n in nombres:
        validar_nombre(n)  # lanza si tuviera caracteres que la API rechaza
    assert set(RENOMBRES_ANTERIORES.values()) <= set(nombres)


@pytest.fixture
def videos(media_tmp):
    creados = []

    def crear(*nombres):
        for n in nombres:
            (media_tmp / "videos" / n).write_bytes(b"")
            creados.append(media_tmp / "videos" / n)

    yield crear
    for c in creados:
        c.unlink()


def test_franja_de_facultad_toma_solo_sus_carreras(videos):
    videos("jur_grado_abogacia.mp4", "eco_grado_contador_publico.mp4", "jur_posgrado_doctorado.mp4")
    franja = next(b for b in sch.GRILLA if b.facultad == "jur")
    assert sch._clips_para(franja) == ["jur_grado_abogacia.mp4", "jur_posgrado_doctorado.mp4"]


def test_bloque_vacio_cae_a_la_rotacion_de_todas_las_carreras(videos):
    videos("jur_grado_abogacia.mp4", "art_grado_artes_visuales.mp4", "prueba_fondo_umsa.mp4")
    prime = next(b for b in sch.GRILLA if b.nombre.startswith("Prime Time"))
    # orden facultad por facultad (el de la grilla), no alfabético global
    assert sch._clips_para(prime) == ["jur_grado_abogacia.mp4", "art_grado_artes_visuales.mp4"]


def test_sin_carreras_cae_al_loop_institucional(videos):
    videos("prueba_fondo_umsa.mp4")
    prime = next(b for b in sch.GRILLA if b.nombre.startswith("Prime Time"))
    assert sch._clips_para(prime) == ["prueba_fondo_umsa.mp4"]
