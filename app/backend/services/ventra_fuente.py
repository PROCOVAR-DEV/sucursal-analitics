"""Los informes, leyendo de lo que se trajo de Ventra en vez de un Excel subido a mano.

# Qué es esto

Un `ReportData` —lo mismo que devuelve subir un fichero— pero armado desde la tabla
`analytics_venta_ventra`. Los informes no se enteran de la diferencia: reciben el mismo
DataFrame, con las mismas columnas y los mismos ayudantes derivados, y siguen calculando
igual. Eso es lo que permite cambiar el origen sin tocar ni una pantalla.

# Por qué no se guarda ya calculado

De aquí sale el crudo. El gestor, los hectolitros y el grupo comercial los pone
`enrich_for_sucursal` con la configuración de CADA sucursal, que se edita. Guardando el
resultado, corregir el alias de un gestor no arreglaría el pasado: habría que reimportar
todo desde Ventra.

# El Excel no se quita todavía

Mientras las dos fuentes convivan se pueden comparar mes a mes. Quitar la barra de subir
ficheros antes de haber comprobado que los números cuadran deja a las sucursales sin
poder cargar nada y sin forma de demostrar que lo automático dice la verdad.
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from services.db import VentaVentra, session_scope
from services.loader import STD_COLS, ReportData, _add_stable_helpers, _type_df
from services.ventra import COL_BASE, COL_OBJETO, COL_TIPO_PUNTO
from services.ventra_sucursales import base_de

# Las mismas que arma `repository._df_de_filas`, más las tres que sólo trae Ventra.
# `suma` va vacía a propósito: es una columna del Excel —un acumulado por hoja— que
# Ventra no manda y que ningún informe usa para calcular. Ponerla a cero sería inventar
# un total.
_COLS = [
    STD_COLS["op"], STD_COLS["fecha"], STD_COLS["socio"], STD_COLS["merc"],
    STD_COLS["grupo"], STD_COLS["cant"], STD_COLS["importe"], STD_COLS["suma"],
    STD_COLS["nota"], COL_OBJETO, COL_TIPO_PUNTO, COL_BASE,
]


def _limite(v: date | datetime | None, fin: bool) -> datetime | None:
    """Un extremo del rango, en instantes.

    El día de `hasta` entra ENTERO: quien pide «hasta el 31» quiere el 31 incluido, y
    comparar contra el 31 a las 00:00 deja fuera las ventas de ese día — un mes que
    parece que cerró peor de lo que cerró.
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    return datetime(v.year, v.month, v.day, 23, 59, 59) if fin else datetime(v.year, v.month, v.day)


def hay_datos(sid: str) -> bool:
    """Si esa sucursal tiene algo traído de Ventra. Barato: no arma el DataFrame."""
    base = base_de(sid)

    if not base:
        return False

    with session_scope() as s:
        return s.query(VentaVentra.linea_id).filter(VentaVentra.database == base).first() is not None


def report_de_ventra(
    sid: str,
    desde: date | datetime | None = None,
    hasta: date | datetime | None = None,
) -> ReportData | None:
    """Las ventas de esa sucursal, con la forma que esperan los informes.

    None cuando la sucursal no tiene base asignada o no hay nada traído todavía. None y
    no un DataFrame vacío: un informe sobre cero filas se pinta con todo a cero y se lee
    como «esta sucursal no vendió nada», que es muy distinto de «esto aún no se ha
    traído».
    """
    base = base_de(sid)

    if not base:
        return None

    with session_scope() as s:
        q = s.query(VentaVentra).filter(VentaVentra.database == base)
        ini, fin = _limite(desde, False), _limite(hasta, True)

        if ini is not None:
            q = q.filter(VentaVentra.fecha >= ini)
        if fin is not None:
            q = q.filter(VentaVentra.fecha <= fin)

        filas = [
            {
                STD_COLS["op"]: r.oper_number,
                STD_COLS["fecha"]: r.fecha,
                STD_COLS["socio"]: r.socio,
                STD_COLS["merc"]: r.mercancia,
                STD_COLS["grupo"]: r.grupo,
                STD_COLS["cant"]: r.cantidad,
                STD_COLS["importe"]: r.importe,
                STD_COLS["suma"]: None,
                STD_COLS["nota"]: r.nota,
                COL_OBJETO: r.objeto,
                COL_TIPO_PUNTO: r.tipo_punto,
                COL_BASE: r.database,
            }
            for r in q.order_by(VentaVentra.fecha, VentaVentra.oper_number).all()
        ]

    if not filas:
        return None

    df = pd.DataFrame(filas, columns=_COLS)
    # Exactamente lo que hace el repositorio con las filas subidas: tipar las columnas
    # base y volver a derivar los ayudantes (vseg, tamaño, malta…). Los informes reciben
    # así el mismo DataFrame viniera de donde viniera.
    df = _add_stable_helpers(_type_df(df))

    fechas = pd.to_datetime(df[STD_COLS["fecha"]], errors="coerce").dropna()

    return ReportData(
        df=df,
        date_min=fechas.min() if not fechas.empty else None,
        date_max=fechas.max() if not fechas.empty else None,
        filename=f"Ventra · {base} ({len(df)} líneas)",
    )
