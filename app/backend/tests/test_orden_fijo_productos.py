"""Los productos salen SIEMPRE los mismos y en el mismo orden, se vendan o no en el mes.

Sucursales, 08/10/2026: «que las columnas siempre mantengan un mismo orden y una misma
secuencia, independientemente que se venda o no el producto en el mes». Las columnas del
modelo y las filas del resumen de Productos salían de lo vendido en el periodo: un producto
sin ventas desaparecía y los demás se corrían de sitio, así que dos meses no se podían
poner uno junto al otro.
"""
import io

import openpyxl
import pandas as pd

from core.utils import detect_size, extract_vendor_segment, is_malta, is_parranda, normalize_text
from services.excel_export import export_modelo_ventas_cliente, export_productos
from services.loader import STD_COLS, ReportData, filter_by_period

MERC, CANT, NOTA, FEC, IMP, SOC = (
    STD_COLS["merc"], STD_COLS["cant"], STD_COLS["nota"], STD_COLS["fecha"],
    STD_COLS["importe"], STD_COLS["socio"],
)
NOTA_GARI = "P-X; V-GARI DURAN; C-Y;"
EFF = {
    "_period": "2026-09",
    "gestores": {"GARI": {"nombre": "Gari", "activo": True, "aliases": ["GARI DURAN"],
                          "cuota_hl": 100.0, "cuota_ccc": 10.0}},
    "size_mult": {"1500": 0.09, "330": 0.02},
    "units_per_pallet": {"1500": 110, "330": 496},
    "product_groups_keywords": {"IMPORTACIONES": ["ARROZ", "ACEITE", "AZUCAR"]},
    "groups_order": ["IMPORTACIONES"],
    "meta_hectolitros_total": 100.0, "meta_ccc_total": 10.0, "meta_dinero_total": 1000.0,
    "curva_venta": {"S1": 1, "S2": 1, "S3": 1, "S4": 1, "S5": 1},
    "frecuencia": {"S1": 1, "S2": 1, "S3": 1, "S4": 1, "S5": 1},
}


def fila(producto, mes):
    return {FEC: pd.Timestamp(f"2026-{mes}-02"), MERC: producto, CANT: 10, IMP: 100.0,
            SOC: "CLIENTE", NOTA: NOTA_GARI,
            STD_COLS["vseg"]: normalize_text(extract_vendor_segment(NOTA_GARI)),
            STD_COLS["size"]: detect_size(producto),
            STD_COLS["malta"]: is_malta(producto), STD_COLS["parr"]: is_parranda(producto)}


# Agosto vendió arroz y aceite; septiembre sólo azúcar.
COMPLETO = ReportData(
    df=pd.DataFrame([fila("ARROZ PATEKO 1 KG PACA 10U", "08"),
                     fila("ACEITE SOL 1 L CAJA 12U", "08"),
                     fila("AZUCAR BLANCA 1 KG PACA 10U", "09")]),
    filename="p.xlsx", date_min=None, date_max=None)


def hojas(datos):
    return openpyxl.load_workbook(io.BytesIO(datos))


def test_modelo_mismas_columnas_con_o_sin_ventas_en_el_mes():
    cabecera = []
    for mes in ("2026-08", "2026-09"):
        wb = hojas(export_modelo_ventas_cliente(filter_by_period(COMPLETO, mes), EFF, completo=COMPLETO))
        cabecera.append([c.value for c in wb["Resumen"][3]])
    assert cabecera[0] == cabecera[1]
    assert {"Arroz Pateko", "Aceite Sol", "Azucar Blanca"} <= set(cabecera[1])


def test_resumen_de_productos_mismas_filas_y_orden_y_cero_si_no_se_vendio():
    filas = []
    for mes in ("2026-08", "2026-09"):
        wb = hojas(export_productos(filter_by_period(COMPLETO, mes), EFF, completo=COMPLETO))
        filas.append({r[0].value: r[1].value for r in wb["Resumen"].iter_rows(min_row=3)
                      if isinstance(r[1].value, (int, float))})
    assert list(filas[0]) == list(filas[1])
    assert filas[1]["ARROZ PATEKO 1 KG PACA 10U"] == 0
    assert filas[1]["AZUCAR BLANCA 1 KG PACA 10U"] == 100.0


def test_sin_completo_se_comporta_como_antes():
    # Los demás llamadores (export_all, otros tests) no pasan `completo`.
    wb = hojas(export_modelo_ventas_cliente(filter_by_period(COMPLETO, "2026-09"), EFF))
    assert "Arroz Pateko" not in [c.value for c in wb["Resumen"][3]]
