import pandas as pd

from services.clientes_ventra import calidad_de_fichas
from services.loader import STD_COLS
from services.ventra import COL_CLIENTE_CODIGO

S, N = STD_COLS["socio"], STD_COLS["nota"]


def df(filas):
    return pd.DataFrame(filas, columns=[S, COL_CLIENTE_CODIGO, N])


def test_el_mismo_cliente_con_dos_fichas_se_cuenta_como_duplicado():
    r = calidad_de_fichas(df([("EMILIO ARANGO", "1965", ""), ("EMILIO ARANGO", "1966", ""), ("ANA", "100", "")]))
    assert r == {"fichas": 3, "fichas_compartidas": 0, "clientes_con_varias_fichas": 1}


def test_el_prefijo_PO_y_la_tilde_no_hacen_otro_cliente():
    r = calidad_de_fichas(df([("PO-ALIESKI MORALES PACHECO", "3289", ""), ("Alieski Morales Pacheco", "1234", "")]))
    assert r["clientes_con_varias_fichas"] == 1


def test_un_apellido_mal_escrito_con_el_mismo_codigo_de_parranda_es_duplicado():
    n = "P-X; V-ANDY; C-CM01TCP0531;"
    r = calidad_de_fichas(df([("CAROL ALEJANDRO RODRIGUEZ", "1974", n), ("KAROL ALEJANDRO RODRIGUEZ", "3741", n)]))
    assert r["clientes_con_varias_fichas"] == 1


def test_una_ficha_con_dos_personas_distintas_es_compartida():
    r = calidad_de_fichas(df([("HODELVIS BRITO", "3641", ""), ("ODELKIS POLA GOMEZ", "3641", "")]))
    assert r["fichas_compartidas"] == 1 and r["clientes_con_varias_fichas"] == 0


def test_dos_personas_distintas_con_fichas_distintas_no_son_nada_raro():
    r = calidad_de_fichas(df([("ANA PEREZ", "1", ""), ("LUIS GOMEZ", "2", "")]))
    assert r == {"fichas": 2, "fichas_compartidas": 0, "clientes_con_varias_fichas": 0}


def test_el_texto_pegado_tras_el_codigo_no_crea_fichas_ni_duplicados():
    n1 = "P-X; V-A; C-CM01OTR0004; *TRANSFERENCIA: BR601DP175997"
    n2 = "P-Y; V-A; C-CM01OTR0004;"
    r = calidad_de_fichas(df([("JUAN RUIZ", "50", n1), ("JUAN RUIZ", "50", n2)]))
    assert r == {"fichas": 1, "fichas_compartidas": 0, "clientes_con_varias_fichas": 0}


def test_si_aun_no_hay_ningun_codigo_no_se_enseña_nada():
    assert calidad_de_fichas(df([("ANA", None, ""), ("PEDRO", "", "")])) is None
    assert calidad_de_fichas(pd.DataFrame(columns=[S])) is None
    assert calidad_de_fichas(None) is None


def test_los_valores_que_faltan_como_pd_NA_no_tumban_el_calculo():
    # Con columnas «nullable» de pandas lo que falta es pd.NA, y `valor or ""` revienta. Cayó el dashboard de Holguín.
    d = pd.DataFrame(
        {S: pd.array(["ANA", pd.NA, "ANA"], dtype="string"),
         COL_CLIENTE_CODIGO: pd.array(["100", "101", pd.NA], dtype="string"),
         N: pd.array([pd.NA, "P-1; C-CM01TCP0001;", "C-CM01TCP0001;"], dtype="string")}
    )
    r = calidad_de_fichas(d)
    assert r is not None and r["fichas"] == 2
