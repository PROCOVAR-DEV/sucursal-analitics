"""El cobro del reparto no es una venta, y no puede contar como tal.

En AxisPOS todo lo que se cobra en una factura es una línea y toda línea apunta al
catálogo, así que el reparto se cobra con una entrada llamada «ENTREGA A DOMICILIO»,
categoría `SERV`. analitics la sumaba como mercancía: inflaba la Venta Total y, lo que
importa, el ingreso de cada vendedor — que no vende el reparto, lo cobra el que conduce.

Medido en Santiago, septiembre de 2026: 363 líneas, 379,26.
"""
from __future__ import annotations

import pandas as pd
import pytest

from services import servicios
from services.enrich import only_valid
from services.loader import STD_COLS

MERC, GRUPO, IMP = STD_COLS["merc"], STD_COLS["grupo"], STD_COLS["importe"]


def _filas() -> pd.DataFrame:
    return pd.DataFrame(
        {
            MERC: [
                "CERVEZA PARRANDA 330",
                "ENTREGA A DOMICILIO",
                "MALTA 500",
                "Entrega a Domicilio",      # como venga escrito
                "SERVICIO DE ENTREGA",
                "CERVEZA ENTREGA ESPECIAL",  # lleva «entrega» y SÍ es mercancía
                "SERVILLETA AZANAR CAJA 60P",  # lleva «serv» y SÍ es mercancía
            ],
            GRUPO: ["PARRANDA", "", "MALTA", "", "", "OTRO", "OTRO"],
            IMP: [100.0, 1.0, 200.0, 2.0, 3.0, 50.0, 66.0],
            "GestorDetectado": ["ANA"] * 7,
        }
    )


# --------------------------------------------------------------- la regla, sola

def test_reconoce_el_cobro_del_reparto():
    assert servicios.es_servicio("ENTREGA A DOMICILIO")
    assert servicios.es_servicio("entrega a domicilio")
    assert servicios.es_servicio("Entrega A Domicilio")
    assert servicios.es_servicio("SERVICIO DE ENTREGA")
    # Y por la categoría, para el día que AXIS la mande puesta.
    assert servicios.es_servicio("LO QUE SEA", "SERV")
    assert servicios.es_servicio("LO QUE SEA", "Servicios")


def test_no_se_lleva_por_delante_la_mercancia():
    """La frase ENTERA, no una palabra. Ésta es la guarda que evita el desastre grande:
    si bastara «entrega» o «serv», desaparecerían productos de verdad del total."""
    assert not servicios.es_servicio("CERVEZA ENTREGA ESPECIAL")
    assert not servicios.es_servicio("SERVILLETA AZANAR CAJA 60P")
    assert not servicios.es_servicio("CONSERVA DE TOMATE")
    assert not servicios.es_servicio("MALTA 500")
    assert not servicios.es_servicio("")
    assert not servicios.es_servicio(None)


# ------------------------------------------------------------- el embudo de verdad

def test_only_valid_quita_el_cobro_y_deja_la_venta():
    df = servicios.marcar(_filas())
    fuera = only_valid(df, ["ANA"])

    assert list(fuera[MERC]) == [
        "CERVEZA PARRANDA 330",
        "MALTA 500",
        "CERVEZA ENTREGA ESPECIAL",
        "SERVILLETA AZANAR CAJA 60P",
    ]
    # 100 + 200 + 50 + 66. Los 6,00 del reparto se quedaron fuera.
    assert round(float(fuera[IMP].sum()), 2) == 416.0


def test_el_cobro_se_puede_medir_aparte():
    """Quitarlo en silencio es cómo se pierde una tarde comparando con AXIS."""
    df = servicios.marcar(_filas())

    assert servicios.importe_de_servicios(df, ["ANA"]) == 6.0
    # Y con los mismos gestores que el total al que acompaña: un cobro de un gestor que no
    # cuenta no puede aparecer en el número de al lado.
    assert servicios.importe_de_servicios(df, ["OTRO"]) == 0.0


def test_el_total_cuadra_con_lo_de_antes():
    """La suma de las dos partes tiene que ser el archivo entero. Si no cuadra, hay dinero
    que no está en ningún sitio, y eso no se ve en ninguna pantalla."""
    df = servicios.marcar(_filas())
    venta = round(float(only_valid(df, ["ANA"])[IMP].sum()), 2)
    cobro = servicios.importe_de_servicios(df, ["ANA"])

    assert round(venta + cobro, 2) == round(float(df[IMP].sum()), 2)


# --------------------------------------------------------------- las guardas sordas

def test_sin_marcar_no_se_filtra_a_ciegas():
    """Un DataFrame que no pasó por `enrich` no trae la columna. Ahí es mejor no filtrar
    que devolver cero filas: un filtro que se come todo parece «no hubo ventas»."""
    df = _filas()  # sin marcar
    assert len(servicios.solo_mercancia(df)) == len(df)
    assert servicios.importe_de_servicios(df) == 0.0


def test_vacio_no_revienta():
    vacio = pd.DataFrame({MERC: [], GRUPO: [], IMP: []})
    marcado = servicios.marcar(vacio)
    assert servicios.COL in marcado.columns
    assert len(servicios.solo_mercancia(marcado)) == 0
    assert servicios.importe_de_servicios(marcado) == 0.0
