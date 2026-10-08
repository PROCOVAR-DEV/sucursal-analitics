"""Malta 500 ml ya no se vende en ninguna sucursal (Jose, 08/10/2026): no sale en ninguna tabla.

Aunque haya quedado una meta vieja guardada para ese formato, no lo hace volver.
"""
import pandas as pd

from services.loader import ReportData, STD_COLS, _add_stable_helpers
from services.metas_gestor import DEFAULT_FORMATOS, compute_metas_gestor
from services.ventas import compute_ventas

MERC, CANT, NOTA, IMP, FEC = (STD_COLS["merc"], STD_COLS["cant"], STD_COLS["nota"],
                              STD_COLS["importe"], STD_COLS["fecha"])
CFG = {
    "_period": "2026-09",
    "gestores": {"GARI": {"nombre": "Gari", "aliases": ["GARI DURAN"], "cuota_hl": 100.0,
                          # La meta vieja de Malta 500 sigue guardada en la base.
                          "metas_formato": {"MALTA-500": 20.0, "PARRANDA-1500": 90.0}}},
    "size_mult": {"330": 0.02, "500": 0.03, "1500": 0.09},
    "units_per_pallet": {"330": 496, "500": 336, "1500": 110},
    "product_groups_keywords": {"PARRANDA": ["CERVEZA", "MALTA"]},
    "groups_order": ["PARRANDA"],
    "meta_hectolitros_total": 100.0, "meta_dinero_total": 1000.0,
}


def informe():
    df = pd.DataFrame([{MERC: "CERVEZA PARRANDA 1500 ML BLISTER 6U", CANT: 10, IMP: 100.0,
                        FEC: pd.Timestamp("2026-09-10"), NOTA: "P-X; V-GARI DURAN; C-Y;"}])
    return ReportData(df=_add_stable_helpers(df), filename="p.xlsx", date_min=None, date_max=None)


def test_la_casa_maneja_cinco_formatos():
    assert "M500" not in DEFAULT_FORMATOS and len(DEFAULT_FORMATOS) == 5


def test_una_meta_vieja_de_malta_500_no_lo_hace_volver():
    assert "M500" not in compute_metas_gestor(informe(), CFG)["formatos"]


def test_ventas_ya_no_trae_la_columna():
    g = compute_ventas(informe(), CFG)["gestores"][0]
    assert "malta_500" not in g and "parranda_500" in g
    assert all("M500" not in r for r in compute_ventas(informe(), CFG)["supervisor"])
