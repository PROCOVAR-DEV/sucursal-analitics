"""
El «% del total» de un vendedor es su parte de la SUCURSAL, no de su propia tabla.

Santiago, 26/09/2026. Gari entra a «Quién vende → Gestor × Producto» y su fila dice
**100,0 %** con $27.563. Es cierto y es inútil: como a un vendedor se le recortan las
filas a las suyas (`recortar_a_gestor`), el total de esa tabla es el suyo, y lo suyo
entre lo suyo siempre da uno. En la pantalla del supervisor esa misma fila es el 8 %.

Lo que se prueba: el denominador es el de la sucursal entera, y la tabla del supervisor
no cambia — sigue sumando 100 %.
"""
import pandas as pd

from services.gestor_sku import compute_gestor_sku
from services.loader import ReportData, STD_COLS, _add_stable_helpers
from services.permisos import recortar_a_gestor

MERC, CANT, NOTA = STD_COLS["merc"], STD_COLS["cant"], STD_COLS["nota"]
IMP = STD_COLS["importe"]

CFG = {
    "gestores": {
        "GARI": {"nombre": "Gari", "aliases": ["GARI DURAN"]},
        "ODETTE": {"nombre": "Odette", "aliases": ["ODETTE PEREZ"]},
        "DAYLA": {"nombre": "Dayla", "aliases": ["DAYLA SUAREZ"]},
    },
    "size_mult": {"330": 0.02, "500": 0.03, "1500": 0.09},
    "units_per_pallet": {"330": 496, "500": 336, "1500": 110},
    "product_groups_keywords": {"PARRANDA": ["CERVEZA"], "IMPORTACIONES": ["ARROZ"]},
    "groups_order": ["PARRANDA", "IMPORTACIONES"],
}

# 8.000 + 42.000 + 50.000 = 100.000. Gari es el 8 %, que es el número de la captura.
VENTAS = [
    ("GARI DURAN", "CERVEZA PARRANDA 500 ML BLISTER 6U", 6000.0),
    ("GARI DURAN", "ARROZ PATEKO 1KG", 2000.0),
    ("ODETTE PEREZ", "CERVEZA PARRANDA 500 ML BLISTER 6U", 42000.0),
    ("DAYLA SUAREZ", "ARROZ PATEKO 1KG", 50000.0),
]


def informe():
    df = pd.DataFrame([
        {MERC: prod, CANT: 10, IMP: importe, NOTA: f"P-X; V-{vendedor}; C-Y;"}
        for vendedor, prod, importe in VENTAS
    ])
    # Por el mismo camino que un Excel de verdad: el vendedor de cada línea sale de la
    # Nota y lo pone el cargador, no el enriquecido. Armando el DataFrame a mano sin
    # esto, `GestorDetectado` queda en nulo y la prueba mide una tabla vacía.
    return ReportData(df=_add_stable_helpers(df), filename="prueba.xlsx",
                      date_min=None, date_max=None)


def fila_de(data, clave):
    return next(t for t in data["totales_gestor"] if t["gestor"] == clave)


def test_el_vendedor_ve_SU_peso_y_no_un_cien_por_ciento():
    """El caso de la captura: Gari solo, con $27.563 que eran el 8 % de la sucursal."""
    suyo = recortar_a_gestor(CFG, "GARI")
    data = compute_gestor_sku(informe(), suyo, eff_sucursal=CFG)

    assert fila_de(data, "GARI")["peso_pct"] == 8.0
    assert data["peso_pct_total"] == 8.0
    # Y lo suyo sigue siendo lo suyo: el recorte de filas no se toca.
    assert data["total_medida"] == 8000.0
    assert [g["clave"] for g in data["gestores"]] == ["GARI"]


def test_del_resto_de_la_sucursal_solo_viaja_el_porcentaje():
    """Su importe es suyo; el de los demás no es asunto suyo. Del total de la sucursal
    sale el denominador y nada más: ni filas, ni columnas, ni el total en dólares."""
    data = compute_gestor_sku(informe(), recortar_a_gestor(CFG, "GARI"), eff_sucursal=CFG)

    assert len(data["totales_gestor"]) == 1
    assert 100000.0 not in [v for v in data.values() if isinstance(v, float)]
    for clave in ("ODETTE", "DAYLA"):
        assert clave not in str(data)


def test_la_tabla_del_supervisor_sigue_sumando_cien():
    """Su tabla ES la sucursal, así que los dos totales son el mismo número."""
    data = compute_gestor_sku(informe(), CFG, eff_sucursal=CFG)

    assert data["peso_pct_total"] == 100.0
    assert fila_de(data, "GARI")["peso_pct"] == 8.0
    assert fila_de(data, "ODETTE")["peso_pct"] == 42.0
    assert fila_de(data, "DAYLA")["peso_pct"] == 50.0


def test_sin_la_config_de_la_sucursal_se_cae_a_lo_de_siempre():
    """La exportación a Excel llama sin ella y no enseña porcentajes. No puede reventar:
    se mide contra la propia tabla, que es lo que se hacía antes de esto."""
    data = compute_gestor_sku(informe(), recortar_a_gestor(CFG, "GARI"))

    assert data["peso_pct_total"] == 100.0


def test_el_filtro_de_grupo_tambien_recorta_el_denominador():
    """Con «sólo PARRANDA» puesto, el peso es sobre la cerveza de la sucursal —6.000 de
    48.000, un 12,5 %— y no sobre los 100.000 de todo, que daría un 6 % que no es el
    peso de nadie."""
    data = compute_gestor_sku(
        informe(), recortar_a_gestor(CFG, "GARI"), grupos=["PARRANDA"], eff_sucursal=CFG,
    )

    assert data["total_medida"] == 6000.0
    assert data["peso_pct_total"] == 12.5
