"""La meta diaria se ajusta a los días que quedan (pedido de Sidney, 13/10/2026).

«Si quedan 10 días y tienes un plan de 400 pacas de azúcar, la meta diaria sea de 40.»
La meta del día de siempre (plan ÷ días del mes) no se movía: quien iba atrasado veía la misma cifra.
"""
from datetime import date

import pandas as pd

from core.utils import detect_size, extract_vendor_segment, is_malta, is_parranda, normalize_text
from services.calendario import meta_diaria_restante, working_days_left
from services.loader import STD_COLS, ReportData
from services.metas_cantidad_gestor import compute_metas_cantidad_gestor
from services.metas_gestor import compute_metas_gestor


def test_el_ejemplo_de_sidney():
    assert meta_diaria_restante(400, 0, 10) == 40.0


def test_lo_ya_vendido_hasta_ayer_baja_la_meta():
    assert meta_diaria_restante(400, 100, 10) == 30.0


def test_si_ya_cumplio_la_meta_es_cero_y_no_negativa():
    assert meta_diaria_restante(400, 450, 10) == 0.0


def test_no_divide_entre_cero():
    assert meta_diaria_restante(400, 0, 0) == 400.0


def test_dias_que_quedan_octubre_2026():
    # Octubre 2026: 22 días laborales (lun-vie). Martes 13 → quedan 14: hoy y del 14 al 30.
    assert working_days_left(date(2026, 10, 13), {}) == 14
    assert working_days_left(date(2026, 10, 1), {}) == 22
    # Un sábado que no se trabaja no cuenta: quedan los del 19 al 30.
    assert working_days_left(date(2026, 10, 17), {}) == 10
    # Pasado el último día laborable, 1 (no cero).
    assert working_days_left(date(2026, 10, 31), {}) == 1
    # Si la sucursal trabaja el sábado, ese sábado sí cuenta.
    assert working_days_left(date(2026, 10, 17), {"trabaja_sabado": True}) > 10


MERC, CANT, NOTA, IMP, FEC = (STD_COLS["merc"], STD_COLS["cant"], STD_COLS["nota"], STD_COLS["importe"], STD_COLS["fecha"])
CFG = {
    "_period": "2026-09",
    "gestores": {"GARI": {"nombre": "Gari", "aliases": ["GARI DURAN"], "cuota_hl": 100.0,
                          "metas_formato": {"PARRANDA-1500": 90.0}, "metas_cantidad": {"ARROZ": 100.0}}},
    "size_mult": {"330": 0.02, "500": 0.03, "1500": 0.09},
    "units_per_pallet": {"330": 496, "500": 336, "1500": 110},
    "product_groups_keywords": {"PARRANDA": ["CERVEZA"], "IMPORTACIONES": ["ARROZ"]},
    "groups_order": ["PARRANDA", "IMPORTACIONES"],
}


def informe():
    def fila(prod, dia, cant):
        return {FEC: pd.Timestamp(f"2026-09-{dia:02d}"), MERC: prod, CANT: cant, IMP: 100.0, NOTA: "P-X; V-GARI DURAN; C-Y;",
                STD_COLS["socio"]: "CLI", STD_COLS["vseg"]: normalize_text(extract_vendor_segment("P-X; V-GARI DURAN; C-Y;")),
                STD_COLS["size"]: detect_size(prod), STD_COLS["malta"]: is_malta(prod), STD_COLS["parr"]: is_parranda(prod)}
    filas = [fila("CERVEZA PARRANDA 1500 ML BLISTER 6U", 3, 100),   # antes de hoy: 9 HL
             fila("CERVEZA PARRANDA 1500 ML BLISTER 6U", 10, 10),   # hoy (día de corte): 0,9 HL
             fila("ARROZ PATEKO 1 KG PACA 10U", 3, 40), fila("ARROZ PATEKO 1 KG PACA 10U", 10, 5)]
    return ReportData(df=pd.DataFrame(filas), filename="p.xlsx", date_min=None, date_max=None)


def test_hectolitros_septiembre_el_dia_10():
    # Sept 2026: 22 laborales, 8 corridos hasta el 10 (jueves) → quedan 15 con hoy.
    r = compute_metas_gestor(informe(), CFG)
    g = r["por_gestor"][0]["diario"]
    assert r["dias_que_quedan"] == g["dias_que_quedan"] == 15
    # Meta 90 HL, vendidos antes de hoy 9 HL → faltan 81 entre 15 días = 5,4. El 0,9 de hoy no la mueve.
    assert g["meta_dia_resto"]["P1500"] == 5.4


def test_unidades_septiembre_el_dia_10():
    r = compute_metas_cantidad_gestor(informe(), CFG)
    g = r["por_gestor"][0]["diario"]
    assert g["dias_que_quedan"] == 15
    # Plan 100 de arroz, 40 vendidos antes de hoy → faltan 60 entre 15 días = 4.
    assert g["meta_dia_resto"]["ARROZ"] == 4.0
    assert g["meta_dia_resto"]["TOTAL"] == 4.0
