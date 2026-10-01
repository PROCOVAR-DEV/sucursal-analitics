"""El PLAN se ve aunque todavía no se haya vendido una sola cerveza.

El 01/10/2026 Sidney abrió octubre y no le salían las metas de sus vendedores: «aquí
salía lo de los planes individuales de cada gestor, pero no lo veo ahora». Era el día 1
del mes y lo único vendido eran importaciones —aceite, azúcar, arroz—, ni un hectolitro.

`compute_metas_gestor` se quedaba con las filas de cerveza y, si no quedaba ninguna,
cortaba devolviendo `por_gestor: []`. Con eso se iba también el PLAN, que no depende de
las ventas: es el objetivo, está guardado, y el día que más falta hace verlo es el
primero del mes. Lo que vale cero es la VENTA.
"""
import pandas as pd

from core.utils import extract_vendor_segment, normalize_text
from services.loader import ReportData, STD_COLS
from services.metas_gestor import compute_metas_gestor

MERC, CANT, NOTA, FEC, IMP = (
    STD_COLS["merc"], STD_COLS["cant"], STD_COLS["nota"], STD_COLS["fecha"], STD_COLS["importe"],
)

EFF = {
    "_period": "2026-10",
    "formatos": ["P1500", "M1500"],
    "gestores": {
        "GARI": {
            "nombre": "Gari", "activo": True, "aliases": ["GARI DURAN"],
            "cuota_hl": 226.57,
            "metas_formato": {"PARRANDA-1500": 177.93, "MALTA-1500": 48.64},
        },
    },
    "size_mult": {"330": 0.02, "500": 0.03, "1500": 0.09},
    "units_per_pallet": {"330": 496, "500": 336, "1500": 110},
    "product_groups_keywords": {},
    "groups_order": [],
}


def informe(filas):
    return ReportData(df=pd.DataFrame(filas), filename="prueba.xlsx", date_min=None, date_max=None)


def fila(nombre, cantidad):
    """Una línea como las que trae el reporte.

    `VendorSegNorm` se pone a mano porque la calcula el CARGADOR al leer el Excel
    (`_add_stable_helpers`), y aquí el `ReportData` se construye directo. Sin ella no hay
    vendedor que detectar y la prueba mide otra cosa — me costó dos vueltas.
    """
    nota = "P-X; V-GARI DURAN; C-Y;"
    return {FEC: pd.Timestamp("2026-10-01"), MERC: nombre, CANT: cantidad,
            IMP: 100.0, NOTA: nota,
            STD_COLS["vseg"]: normalize_text(extract_vendor_segment(nota))}


def bloque(r, gestor="GARI"):
    return next((g for g in r.get("por_gestor") or [] if g["gestor"] == gestor), None)


def test_sin_una_sola_cerveza_el_plan_sigue_saliendo():
    """EL CASO DE SIDNEY: sólo importaciones vendidas, y aun así tiene que verse la meta."""
    r = compute_metas_gestor(informe([
        fila("ACEITE SOYA SAUDE 900 ML CAJA 20U", 3),
        fila("AZUCAR PATEKO 1 KG PACA 10U", 6),
    ]), EFF, None)

    g = bloque(r)
    assert g is not None, "sin cerveza, el gestor desapareció del plan"
    # La meta está entera...
    assert g["mensual"]["meta_total"]["P1500"] == 177.93
    assert g["mensual"]["meta_total"]["M1500"] == 48.64
    assert g["totales"]["meta_hl"] == 226.57
    # ...y lo vendido en hectolitros es cero, que es lo único que debe valer cero.
    assert g["mensual"]["venta_acum"]["TOTAL"] == 0.0
    assert g["totales"]["total_hl"] == 0.0


def test_el_dia_sigue_pudiendose_elegir():
    """Los días del selector salen de TODO lo del mes, no sólo de la cerveza: si no, un
    día en que sólo se vendió arroz no se podría mirar."""
    r = compute_metas_gestor(informe([fila("ARROZ GRANO LARGO SACO 25KG", 10)]), EFF, None)

    assert r["dias_disponibles"] == ["2026-10-01"]
    assert r["report_date"] == "2026-10-01"


def test_con_cerveza_sigue_contando_igual():
    """La guarda no puede haberse llevado por delante el camino normal."""
    r = compute_metas_gestor(informe([
        fila("ACEITE SOYA SAUDE 900 ML CAJA 20U", 3),
        fila("CERVEZA PARRANDA 1500 ML BLISTER 6U", 100),
    ]), EFF, None)

    g = bloque(r)
    assert g is not None
    assert g["mensual"]["meta_total"]["P1500"] == 177.93
    # 100 x 0,09 = 9 HL. Vendió cerveza: ya no es cero.
    assert g["mensual"]["venta_acum"]["P1500"] == 9.0
    assert g["totales"]["total_hl"] == 9.0
