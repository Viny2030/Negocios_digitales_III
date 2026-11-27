"""Zona horaria de la grilla, recuperación del watchdog y del scheduler."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core import scheduler as scheduler_module
from app.core import watchdog as watchdog_module
from app.core.watchdog import StreamWatchdog


class _StreamerFalso:
    def __init__(self, corriendo=False, debe=True, falla=True):
        self.corriendo, self.debe, self.falla = corriendo, debe, falla
        self.starts = 0
        self.reloads = 0

    def debe_estar_corriendo(self):
        return self.debe

    def status(self):
        return {"running": self.corriendo}

    def start(self):
        self.starts += 1
        if self.falla:
            raise RuntimeError("ffmpeg no levanta")
        self.corriendo = True

    def reload(self):
        self.reloads += 1


def _fecha_fija(utc_hora):
    class _Fija(datetime):
        @classmethod
        def now(cls, tz=None):
            base = datetime(2026, 10, 7, utc_hora, 0, tzinfo=UTC)
            return base.astimezone(tz) if tz else base.replace(tzinfo=None)

    return _Fija


def test_grilla_usa_hora_argentina_aunque_el_servidor_este_en_utc(monkeypatch):
    # 11:00 UTC (lo que marca el reloj de un contenedor en Railway) = 08:00 en Argentina.
    monkeypatch.setattr(scheduler_module, "datetime", _fecha_fija(11))
    assert scheduler_module.bloque_actual().nombre == "UMSA Despierta"
    # 08:00 UTC = 05:00 en Argentina: todavía es el bloque nocturno (antes daba UMSA Despierta).
    monkeypatch.setattr(scheduler_module, "datetime", _fecha_fija(8))
    assert scheduler_module.bloque_actual().nombre == "UMSA Nocturno"


def test_watchdog_pausa_y_retoma_solo_cuando_pasa_la_ventana(monkeypatch):
    falso = _StreamerFalso(falla=True)
    monkeypatch.setattr(watchdog_module, "streamer", falso)
    monkeypatch.setattr(watchdog_module.settings, "watchdog_max_reintentos", 3)
    monkeypatch.setattr(watchdog_module.settings, "watchdog_ventana_seg", 600)
    w = StreamWatchdog()

    for _ in range(5):
        w.chequear()
    assert falso.starts == 3  # techo de reintentos dentro de la ventana
    assert w.estado()["agotado"] is True

    # Pasa la ventana: los reintentos viejos vencen y vuelve a intentar SOLO
    # (antes quedaba agotado para siempre, hasta reiniciar el proceso).
    viejo = datetime.now(UTC) - timedelta(seconds=601)
    w._reintentos = type(w._reintentos)([viejo] * 3)
    falso.falla = False
    w.chequear()
    assert falso.starts == 4
    assert falso.corriendo is True
    assert w.estado()["agotado"] is False


def test_watchdog_resetear_limpia_el_contador(monkeypatch):
    falso = _StreamerFalso(falla=True)
    monkeypatch.setattr(watchdog_module, "streamer", falso)
    monkeypatch.setattr(watchdog_module.settings, "watchdog_max_reintentos", 2)
    w = StreamWatchdog()
    w.chequear()
    w.chequear()
    assert w.estado()["agotado"] is True
    w.resetear()
    assert w.estado() == {"corriendo": False, "reintentos_recientes": 0, "agotado": False}


def test_watchdog_no_toca_un_stream_parado_a_proposito(monkeypatch):
    falso = _StreamerFalso(debe=False)
    monkeypatch.setattr(watchdog_module, "streamer", falso)
    StreamWatchdog().chequear()
    assert falso.starts == 0


def test_cambio_de_bloque_no_congela_el_loop_de_asyncio(monkeypatch):
    """reload() puede tardar hasta 10 s (stop de ffmpeg). Antes corría dentro
    del loop de asyncio y congelaba toda la API mientras tanto."""
    import asyncio
    import time

    class _StreamerLento(_StreamerFalso):
        def reload(self):
            time.sleep(1.0)  # simula un ffmpeg que tarda en cerrar
            super().reload()

    lento = _StreamerLento(corriendo=True, falla=False)
    monkeypatch.setattr(scheduler_module, "streamer", lento)
    monkeypatch.setattr(scheduler_module, "escribir_playlist", lambda nombres: None)

    async def escenario():
        s = scheduler_module.SchedulerBloques()
        s.start()
        t0 = time.perf_counter()
        # Mientras el ciclo está en el reload lento, otra corrutina (ej. un
        # request) tiene que poder correr: este sleep de 50 ms no puede
        # terminar tarde. Con el reload dentro del loop tardaba ~1 s.
        await asyncio.sleep(0.05)
        demora = time.perf_counter() - t0
        while lento.reloads == 0:
            await asyncio.sleep(0.05)
        s.stop()
        return demora

    assert asyncio.run(escenario()) < 0.3
    assert lento.reloads == 1


def test_reload_y_start_concurrentes_no_se_pisan(monkeypatch, tmp_path):
    """Un start() que llega en medio de un reload() espera a que termine, en
    vez de colarse entre su stop() y su start()."""
    import threading
    import time

    from app.core.streamer import FFmpegStreamer

    s = FFmpegStreamer()
    orden = []

    def stop_lento(timeout=10.0):
        orden.append("stop-ini")
        time.sleep(0.3)
        orden.append("stop-fin")

    def start_registrado():
        with s._ciclo_vida:
            orden.append("start")

    monkeypatch.setattr(s, "stop", stop_lento)
    monkeypatch.setattr(s, "start", start_registrado)
    hilo = threading.Thread(target=s.reload)
    hilo.start()
    time.sleep(0.1)  # el reload ya está dentro de stop()
    s.start()  # un POST /stream/start concurrente
    hilo.join()
    assert orden == ["stop-ini", "stop-fin", "start", "start"]


@pytest.mark.parametrize("corriendo,esperado", [(True, "recargado"), (False, "arrancado")])
def test_cambio_de_bloque_levanta_el_stream_si_estaba_caido(monkeypatch, corriendo, esperado):
    falso = _StreamerFalso(corriendo=corriendo, falla=False)
    monkeypatch.setattr(scheduler_module, "streamer", falso)
    monkeypatch.setattr(scheduler_module, "escribir_playlist", lambda nombres: None)
    detalle = scheduler_module.SchedulerBloques().forzar(hora=8)
    assert esperado in detalle
    assert (falso.reloads, falso.starts) == ((1, 0) if corriendo else (0, 1))
