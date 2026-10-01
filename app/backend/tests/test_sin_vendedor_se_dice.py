"""Lo facturado SIN vendedor no se cuenta, pero se dice.

El 01/10/2026 Sidney comparó su reporte de AXIS (18.615,50) con el panel (18.588,10).
La diferencia eran 27,40 de UNA factura: azúcar a CRISTIAN MARCOS MONTOYA GONZÁLEZ, cuya
nota traía el nombre del cliente y ningún segmento `V-`. Sin vendedor no hay a quién
atribuirla, y el panel entero es por vendedor — pero restarla callando es media mañana
comparando dos números que no tienen por qué coincidir.

Esto fue enorme y está casi resuelto: 125.189,87 en junio, 51.226,57 en julio, 5.422,78
en agosto, 12,00 en septiembre. Que se vea es lo que hace que se siga arreglando.
"""
import pandas as pd

from core.utils import detect_size, extract_vendor_segment, is_malta, is_parranda, normalize_text
from services.loader import ReportData, STD_COLS
from services.ventas import compute_ventas

MERC, CANT, NOTA, FEC, IMP, SOC = (
    STD_COLS["merc"], STD_COLS["cant"], STD_COLS["nota"], STD_COLS["fecha"],
    STD_COLS["importe"], STD_COLS["socio"],
)

EFF = {
    "_period": "2026-10",
    "formatos": ["P1500"],
    "gestores": {"GARI": {"nombre": "Gari", "activo": True, "aliases": ["GARI DURAN"], "cuota_hl": 100.0}},
    "size_mult": {"1500": 0.09},
    "units_per_pallet": {"1500": 110},
    "product_groups_keywords": {},
    "groups_order": [],
    "meta_hectolitros_total": 100.0,
    "meta_dinero_total": 1000.0,
    "meta_ccc_total": 0.0,
}


def fila(nombre, importe, nota, socio="UN CLIENTE"):
    """Una línea como la que deja el CARGADOR al leer el Excel.

    `VendorSegNorm`, `IsMalta`, `IsParranda` y `Size` las pone `_add_stable_helpers` al
    cargar, no el enriquecido. Construyendo el `ReportData` a mano hay que ponerlas, o la
    prueba revienta con un `KeyError` que no tiene nada que ver con lo que se mide.
    """
    return {FEC: pd.Timestamp("2026-10-01"), MERC: nombre, CANT: 1, IMP: importe,
            SOC: socio, NOTA: nota,
            STD_COLS["vseg"]: normalize_text(extract_vendor_segment(nota)),
            STD_COLS["size"]: detect_size(nombre),
            STD_COLS["malta"]: is_malta(nombre),
            STD_COLS["parr"]: is_parranda(nombre)}


def informe(filas):
    return ReportData(df=pd.DataFrame(filas), filename="p.xlsx", date_min=None, date_max=None)


CON_VENDEDOR = "P-X; V-GARI DURAN; C-Y;"
SIN_VENDEDOR = "CRISTIAN MARCOS MONTOYA GONZÁLEZ\n\n"


def test_la_factura_sin_vendedor_no_cuenta_pero_se_dice():
    """EL CASO DE SIDNEY, con sus números."""
    d = compute_ventas(informe([
        fila("CERVEZA PARRANDA 1500 ML BLISTER 6U", 18588.10, CON_VENDEDOR),
        fila("AZUCAR PATEKO 1 KG PACA 10U", 27.40, SIN_VENDEDOR, "CRISTIAN MARCOS MONTOYA GONZÁLEZ"),
    ]), EFF)

    assert d["total_importe"] == 18588.10        # lo que enseña el panel
    assert d["total_sin_vendedor"] == 27.40      # y lo que explica la diferencia
    # Las dos partes suman lo que da AXIS. Si esto deja de cuadrar, el total vuelve a ser
    # inexplicable y se pierde otra mañana.
    assert round(d["total_importe"] + d["total_sin_vendedor"], 2) == 18615.50


def test_sin_huerfanas_sale_cero_y_no_estorba():
    """Una tarjeta en cero todos los días es ruido: el panel sólo la pinta si hay algo."""
    d = compute_ventas(informe([fila("CERVEZA PARRANDA 1500 ML BLISTER 6U", 500.0, CON_VENDEDOR)]), EFF)

    assert d["total_sin_vendedor"] == 0.0
    assert d["total_importe"] == 500.0


def test_el_domicilio_no_se_cuenta_como_huerfano():
    """Son dos cosas distintas y cada una tiene su tarjeta. Contar el domicilio aquí
    sería explicar la diferencia dos veces."""
    d = compute_ventas(informe([
        fila("CERVEZA PARRANDA 1500 ML BLISTER 6U", 500.0, CON_VENDEDOR),
        fila("ENTREGA A DOMICILIO", 24.08, CON_VENDEDOR),
        fila("AZUCAR PATEKO 1 KG PACA 10U", 27.40, SIN_VENDEDOR),
    ]), EFF)

    assert d["total_importe"] == 500.0
    assert d["total_domicilio"] == 24.08
    assert d["total_sin_vendedor"] == 27.40
