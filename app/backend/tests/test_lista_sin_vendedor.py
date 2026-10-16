"""La LISTA de facturas sin vendedor, con su nota, y quién la ve.

El 16/10/2026 Jose vio una venta de Holguín «en blanco» y no había forma de saber cuál: el
panel sólo daba el total. Para corregirlas hace falta ver la factura y lo que dice su nota
(vacía, sin `V-`, con una errata como «ALIANNIS»).
"""
import pandas as pd

from services.permisos import ve_lista_sin_vendedor
from services.loader import STD_COLS
from services.ventas import compute_ventas, facturas_sin_vendedor
from services.enrich import enrich_for_sucursal

from test_sin_vendedor_se_dice import CON_VENDEDOR, EFF, fila, informe

OP, FEC, NOTA = STD_COLS["op"], STD_COLS["fecha"], STD_COLS["nota"]


def con(op, dia, **kw):
    f = fila(kw.pop("merc"), kw.pop("imp"), kw.pop("nota"), kw.pop("socio", "UN CLIENTE"))
    f[OP] = op
    f[FEC] = pd.Timestamp(dia)
    return f


def lineas():
    return [
        con("100", "2026-10-01", merc="CERVEZA PARRANDA 1500 ML BLISTER 6U", imp=210.60, nota=None, socio="YOENIS"),
        con("100", "2026-10-01", merc="AZUCAR PATEKO 1 KG PACA 10U", imp=10.0, nota=pd.NA, socio="YOENIS"),  # pandas guarda el vacío como NA
        con("101", "2026-10-02", merc="CERVEZA PARRANDA 1500 ML BLISTER 6U", imp=500.0, nota=CON_VENDEDOR),
        con("102", "2026-10-03", merc="ENTREGA A DOMICILIO", imp=24.08, nota="ALIANNIS"),
        con("103", "2026-10-03", merc="ACEITE SOYA SAUDE 900 ML CAJA 20U", imp=57.0, nota="ALIANNIS"),
    ]


def test_la_lista_trae_cada_factura_con_su_nota_y_suma_el_total():
    rep = informe(lineas())
    bruto = enrich_for_sucursal(rep, EFF)
    facturas = facturas_sin_vendedor(bruto)

    # Más reciente primero, y la factura con dos líneas sale UNA vez.
    assert [f["factura"] for f in facturas] == ["103", "100"]
    assert facturas[0]["nota"] == "ALIANNIS"
    assert facturas[1]["nota"] == ""               # vacía: se dice vacía, no se inventa
    assert facturas[1]["lineas"] == 2 and facturas[1]["importe"] == 220.60
    assert facturas[1]["cliente"] == "YOENIS" and facturas[1]["fecha"] == "2026-10-01"
    # El domicilio (102) no es «sin vendedor»: tiene su propia tarjeta.
    assert "102" not in [f["factura"] for f in facturas]
    # La lista y el total del panel son la MISMA cuenta.
    assert round(sum(f["importe"] for f in facturas), 2) == compute_ventas(rep, EFF)["total_sin_vendedor"]


def test_sin_huerfanas_la_lista_esta_vacia():
    assert facturas_sin_vendedor(enrich_for_sucursal(informe([con("1", "2026-10-02", merc="CERVEZA PARRANDA 1500 ML BLISTER 6U", imp=5.0, nota=CON_VENDEDOR)]), EFF)) == []


def test_la_lista_la_ven_el_administrador_y_el_supervisor():
    assert ve_lista_sin_vendedor("admin")
    assert ve_lista_sin_vendedor(" Admin ")
    assert ve_lista_sin_vendedor("supervisor")
    for rol in ("analitico", "gestor", "vendedor", "", None, "rol-nuevo"):
        assert not ve_lista_sin_vendedor(rol)
