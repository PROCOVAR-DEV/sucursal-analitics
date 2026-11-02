import pandas as pd

from services.clientes_ventra import contar_clientes
from services.loader import STD_COLS
from services.ventra import COL_CLIENTE_CODIGO

S = STD_COLS["socio"]


def df(filas):
    return pd.DataFrame(filas, columns=[S, COL_CLIENTE_CODIGO])


def test_el_mismo_cliente_escrito_distinto_cuenta_una_vez_por_codigo():
    # «Geovany» y «Jeovani» son la misma persona: mismo código de Ventra
    r = contar_clientes(df([("GEOVANY HERNANDEZ", "5798"), ("Jeovani Hernandez", "5798"), ("ANA", "100")]))
    assert r == {"por_nombre": 3, "por_codigo": 2, "sin_codigo": 0}


def test_la_venta_de_mostrador_sin_pedido_tambien_es_un_cliente():
    # No lleva C- en la nota, pero sí su código de Ventra
    r = contar_clientes(df([("CARLOS LOPEZ", "31379"), ("CARLOS LOPEZ", "31379"), ("ROSA", "55")]))
    assert r["por_codigo"] == 2


def test_lineas_viejas_sin_codigo_cuentan_por_nombre_y_no_desaparecen():
    r = contar_clientes(df([("ANA", "100"), ("PEDRO", None), ("pedro", None), ("ANA", None)]))
    assert r == {"por_nombre": 2, "por_codigo": 2, "sin_codigo": 1}  # ANA ya está por código; PEDRO por nombre


def test_si_aun_no_hay_ningun_codigo_no_se_enseña_nada():
    assert contar_clientes(df([("ANA", None), ("PEDRO", "")])) is None
    assert contar_clientes(pd.DataFrame(columns=[S])) is None
    assert contar_clientes(None) is None


def test_el_relleno_arranca_aunque_el_bucle_este_apagado():
    # En producción VENTRA_SYNC_EN_API=false: un relleno colgado del bucle no corría nunca.
    from pathlib import Path
    fuente = (Path(__file__).resolve().parents[1] / "main.py").read_text()
    i = fuente.index("def _arrancar_sincronizador")
    cuerpo = fuente[i:fuente.index("@asynccontextmanager", i)]
    assert cuerpo.index("relleno_inicial") < cuerpo.index("os.environ.get(\"VENTRA_SYNC_EN_API\"")
