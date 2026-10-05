"""El CCC del Market cuenta clientes DE CERVEZA, no todo el que compró algo.

Sidney, 03/10/2026: «me está sacando todos los clientes que se atienden en vez de sacarme
sólo los de parranda y malta que atendieron los vendedores».

Las dos secciones del informe son de cerveza. Los hectolitros ya filtraban a Malta y
Parranda; el cliente no, así que uno que sólo se llevó arroz contaba igual. Y como el CCC
se mide contra una cuota de cerveza, el porcentaje salía inflado sin que nada lo dijera.
"""
import pandas as pd

from core.utils import detect_size, extract_vendor_segment, is_malta, is_parranda, normalize_text
from services.loader import ReportData, STD_COLS
from services.market import compute_market

MERC, CANT, NOTA, FEC, IMP, SOC = (
    STD_COLS["merc"], STD_COLS["cant"], STD_COLS["nota"], STD_COLS["fecha"],
    STD_COLS["importe"], STD_COLS["socio"],
)

EFF = {
    "_period": "2026-09",
    "gestores": {"GARI": {"nombre": "Gari", "activo": True, "aliases": ["GARI DURAN"],
                          "cuota_hl": 100.0, "cuota_ccc": 10.0}},
    "size_mult": {"1500": 0.09, "330": 0.02},
    "units_per_pallet": {"1500": 110, "330": 496},
    "product_groups_keywords": {},
    "groups_order": [],
    "meta_hectolitros_total": 100.0,
    "meta_ccc_total": 10.0,
    "meta_dinero_total": 1000.0,
    "curva_venta": {"S1": 1, "S2": 1, "S3": 1, "S4": 1, "S5": 1},
    "frecuencia": {"S1": 1, "S2": 1, "S3": 1, "S4": 1, "S5": 1},
}

NOTA_GARI = "P-X; V-GARI DURAN; C-Y;"


def fila(producto, cliente, dia=2):
    return {FEC: pd.Timestamp(f"2026-09-{dia:02d}"), MERC: producto, CANT: 10, IMP: 100.0,
            SOC: cliente, NOTA: NOTA_GARI,
            STD_COLS["vseg"]: normalize_text(extract_vendor_segment(NOTA_GARI)),
            STD_COLS["size"]: detect_size(producto),
            STD_COLS["malta"]: is_malta(producto),
            STD_COLS["parr"]: is_parranda(producto)}


def informe(filas):
    return ReportData(df=pd.DataFrame(filas), filename="p.xlsx", date_min=None, date_max=None)


def ccc_de(r, gestor="GARI"):
    return next(x for x in r["ccc"] if x["gestor"] == gestor)


CERVEZA = "CERVEZA PARRANDA 1500 ML BLISTER 6U"
ARROZ = "ARROZ PATEKO 1 KG PACA 10U"


def test_el_que_solo_compro_arroz_NO_cuenta():
    """EL CASO DE SIDNEY."""
    r = compute_market(informe([
        fila(CERVEZA, "CLIENTE DE CERVEZA"),
        fila(ARROZ, "CLIENTE DE ARROZ"),
        fila(ARROZ, "OTRO DE ARROZ"),
    ]), EFF)

    assert ccc_de(r)["real_mes"] == 1, "sólo uno compró cerveza"


def test_el_que_compro_las_dos_cosas_cuenta_UNA_vez():
    r = compute_market(informe([
        fila(CERVEZA, "MIXTO"),
        fila(ARROZ, "MIXTO"),
        fila(ARROZ, "SOLO ARROZ"),
    ]), EFF)

    assert ccc_de(r)["real_mes"] == 1


def test_sin_cerveza_en_el_mes_el_CCC_es_CERO():
    """Y no el número de clientes de la sucursal, que es lo que salía."""
    r = compute_market(informe([fila(ARROZ, "UNO"), fila(ARROZ, "DOS"), fila(ARROZ, "TRES")]), EFF)

    assert ccc_de(r)["real_mes"] == 0
    assert ccc_de(r)["cumplimiento_pct"] == 0.0


def test_los_hectolitros_siguen_igual():
    """La guarda no puede haberse llevado por delante lo que ya funcionaba."""
    r = compute_market(informe([fila(CERVEZA, "A"), fila(ARROZ, "B")]), EFF)
    hl = next(x for x in r["hl"] if x["gestor"] == "GARI")

    assert hl["real_mes"] == 0.9     # 10 x 0,09 — el arroz no suma HL


def test_cada_cliente_cuenta_en_SU_semana():
    """El reparto semanal no se toca: sólo se dejó de contar al que no compra cerveza."""
    r = compute_market(informe([
        fila(CERVEZA, "A", dia=2),      # S1
        fila(CERVEZA, "B", dia=23),     # S4
        fila(ARROZ, "C", dia=23),
    ]), EFF)
    c = ccc_de(r)

    assert c["real_mes"] == 2
    assert sum(c["real_semanal"].values()) == 2
