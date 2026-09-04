"""El filtro por rango de días, que antes no existía.

Sólo se podía elegir un mes entero (`AAAA-MM`), y «del 1 al 15» era una pregunta que había
que contestar subiendo un Excel recortado a esas fechas.
"""
from __future__ import annotations

import pandas as pd

from services.loader import STD_COLS, ReportData, filter_by_period


def informe(*dias: str) -> ReportData:
    df = pd.DataFrame({
        STD_COLS["fecha"]: pd.to_datetime(list(dias)),
        STD_COLS["importe"]: [100.0] * len(dias),
    })
    return ReportData(df=df, date_min=df[STD_COLS["fecha"]].min(),
                      date_max=df[STD_COLS["fecha"]].max(), filename="prueba")


R = informe("2026-06-30", "2026-07-01", "2026-07-15", "2026-07-31", "2026-08-01")


def test_sin_nada_no_filtra():
    assert len(filter_by_period(R, None).df) == 5


def test_el_mes_de_siempre_sigue_valiendo():
    assert len(filter_by_period(R, "2026-07").df) == 3


def test_rango_de_dias():
    assert len(filter_by_period(R, None, "2026-07-01", "2026-07-15").df) == 2


def test_el_ultimo_dia_entra_ENTERO():
    # Quien escribe «hasta el 15» quiere el 15 completo, no hasta su medianoche. Sin
    # esto, las ventas del propio día que se pide desaparecen del informe.
    con_hora = informe("2026-07-15 18:30:00")
    assert len(filter_by_period(con_hora, None, "2026-07-01", "2026-07-15").df) == 1


def test_solo_desde_y_solo_hasta():
    assert len(filter_by_period(R, None, "2026-07-15", None).df) == 3
    assert len(filter_by_period(R, None, None, "2026-07-01").df) == 2


def test_el_rango_MANDA_sobre_el_mes():
    # Si vienen los dos es que alguien afinó dentro de un mes ya elegido: lo que quiere
    # ver es el rango, no el mes entero.
    r = filter_by_period(R, "2026-08", "2026-07-01", "2026-07-15")
    assert len(r.df) == 2


def test_una_fecha_ilegible_no_tumba_la_pantalla():
    # Devuelve el informe sin filtrar en vez de reventar: un parámetro mal escrito en la
    # dirección no puede dejar a nadie sin poder mirar sus ventas.
    assert len(filter_by_period(R, None, "no-es-fecha", None).df) == 5


def test_un_rango_vacio_da_vacio_sin_reventar():
    r = filter_by_period(R, None, "2027-01-01", "2027-01-31")
    assert r.df.empty
    assert r.date_min is None
