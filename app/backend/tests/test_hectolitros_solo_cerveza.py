"""
Los hectolitros son de la CERVEZA. De lo demás no se sabe el volumen.

El tamaño se deduce del nombre buscando 330, 500 o 1500, y eso lo tienen productos que
no son cerveza. «REFRESCO SANTA COLA 330 ML CAJA 24U» salía con tamaño 330 y se le
aplicaba 0,02 HL por unidad — que es lo que mide un blíster de SEIS de cerveza, no una
caja de veinticuatro refrescos (7,92 litros).

No se veía en los totales, porque el Resumen, Ventas (HL) y las metas filtran por
Parranda/Malta. Se veía en las tablas de producto a producto —«Quién vende» y el
Excel—, donde un refresco aparecía con hectolitros: 95,72 HL de más sobre 1.806 en
Santiago, septiembre de 2026. Sidney lo cazó porque los números le bailaban entre
pantallas.
"""
import pandas as pd

from services.enrich import enrich_for_sucursal
from services.loader import ReportData, STD_COLS


def informe(filas):
    df = pd.DataFrame(filas)
    return ReportData(df=df, filename="prueba.xlsx", date_min=None, date_max=None)


CFG = {
    "gestores": {"GARI": {"nombre": "Gari", "aliases": ["GARI DURAN"]}},
    "size_mult": {"330": 0.02, "500": 0.03, "1500": 0.09},
    "units_per_pallet": {"330": 496, "500": 336, "1500": 110},
    "product_groups_keywords": {},
    "groups_order": [],
}

MERC, CANT, NOTA = STD_COLS["merc"], STD_COLS["cant"], STD_COLS["nota"]


def enriquecer(nombre, cantidad):
    rep = informe([{MERC: nombre, CANT: cantidad, NOTA: "P-X; V-GARI DURAN; C-Y;"}])
    return enrich_for_sucursal(rep, CFG).iloc[0]


def test_la_cerveza_si_lleva_hectolitros():
    assert enriquecer("CERVEZA PARRANDA 500 ML BLISTER 6U", 100)["Hectolitros"] == 3.0
    assert enriquecer("CERVEZA PARRANDA 1500 ML BLISTER 6U", 10)["Hectolitros"] == 0.9
    assert enriquecer("MALTA GUAJIRA 330 ML BLISTER 6U", 50)["Hectolitros"] == 1.0


def test_UN_REFRESCO_NO_LLEVA_HECTOLITROS():
    """El caso que lo destapó: 1.588 cajas dando 31,76 HL que no existen."""
    fila = enriquecer("REFRESCO SANTA COLA 330 ML CAJA 24U", 1588)

    assert fila["Hectolitros"] == 0.0
    assert fila["Pallets"] == 0.0


def test_ni_nada_que_no_sea_cerveza_aunque_el_nombre_traiga_el_tamano():
    for nombre in [
        "AGUA MINERAL 500 ML",
        "PAPEL HIGIENICO LIRIO 330 HOJAS",
        "CAJA PARA PIZZAS 1500",
    ]:
        assert enriquecer(nombre, 1000)["Hectolitros"] == 0.0, nombre


def test_el_tamano_se_sigue_detectando_para_todos():
    """Se apaga el cálculo, no la clasificación: el tamaño sigue estando por si hace
    falta para otra cosa. Lo que no se hace es convertirlo en litros de cerveza."""
    assert enriquecer("REFRESCO SANTA COLA 330 ML CAJA 24U", 10)[STD_COLS["size"]] == "330"


def test_los_pallets_tambien_son_de_la_cerveza():
    assert enriquecer("CERVEZA PARRANDA 500 ML BLISTER 6U", 336)["Pallets"] == 1.0
    assert enriquecer("REFRESCO SANTA PINA 330 ML CAJA 24U", 496)["Pallets"] == 0.0
