"""Clientes: elegir PRODUCTOS dentro de los grupos (Lixander, supervisor de Parranda, 19/10/2026).

Pedía «poder seleccionar uno o varios productos de ese grupo» al lado del filtro de grupo y de
«sólo compran esto». Se prueba el recorte, que es donde se puede equivocar sin fallar: un filtro
que deja de aplicarse sigue pintando una tabla.
"""
import pandas as pd

from services.clientes_analisis import recortar
from services.loader import STD_COLS

SOC, MERC = STD_COLS["socio"], STD_COLS["merc"]


def filas():
    return pd.DataFrame([
        # Ana: sólo Parranda (dos formatos).
        {SOC: "ANA", MERC: "PARRANDA 500 ML", "GrupoComercial": "PARRANDA"},
        {SOC: "ANA", MERC: "PARRANDA 1.5 L", "GrupoComercial": "PARRANDA"},
        # Beto: Parranda 500 ml y además arroz (otro grupo).
        {SOC: "BETO", MERC: "PARRANDA 500 ML", "GrupoComercial": "PARRANDA"},
        {SOC: "BETO", MERC: "ARROZ 1 KG", "GrupoComercial": "IMPORTACIONES"},
        # Carla: sólo arroz.
        {SOC: "CARLA", MERC: "ARROZ 1 KG", "GrupoComercial": "IMPORTACIONES"},
        # Dani: Parranda 1.5 L, con un espacio de más en el nombre.
        {SOC: "DANI", MERC: "PARRANDA 1.5 L ", "GrupoComercial": "PARRANDA"},
    ])


def clientes(df):
    return sorted(df[SOC].unique())


def test_sin_filtros_no_toca_nada():
    df = filas()
    assert len(recortar(df, [], [], False)) == len(df)
    assert len(recortar(df, None, None, True)) == len(df)  # «sólo compran esto» sin elegir nada no filtra


def test_solo_grupo_es_lo_de_siempre():
    df = recortar(filas(), ["PARRANDA"], [], False)
    assert clientes(df) == ["ANA", "BETO", "DANI"] and len(df) == 4  # a Beto se le oculta el arroz


def test_un_producto_del_grupo_deja_solo_esas_lineas():
    df = recortar(filas(), ["PARRANDA"], ["PARRANDA 500 ML"], False)
    assert clientes(df) == ["ANA", "BETO"] and set(df[MERC]) == {"PARRANDA 500 ML"}


def test_varios_productos_de_cualquier_grupo_sin_elegir_grupo():
    df = recortar(filas(), [], ["PARRANDA 1.5 L", "ARROZ 1 KG"], False)
    assert clientes(df) == ["ANA", "BETO", "CARLA", "DANI"]
    assert set(df[MERC].str.strip()) == {"PARRANDA 1.5 L", "ARROZ 1 KG"}


def test_el_espacio_de_mas_en_el_nombre_no_deja_al_cliente_fuera():
    df = recortar(filas(), [], ["PARRANDA 1.5 L"], False)
    assert "DANI" in clientes(df)


def test_solo_compran_esto_con_productos_mide_lo_que_compraron_fuera_de_los_elegidos():
    # Quien compra PARRANDA 500 ML y nada más: Beto compra también arroz, Ana también 1.5 L.
    df = recortar(filas(), ["PARRANDA"], ["PARRANDA 500 ML"], True)
    assert clientes(df) == []
    # Quien sólo compra Parranda 1.5 L: Dani.
    df = recortar(filas(), ["PARRANDA"], ["PARRANDA 1.5 L"], True)
    assert clientes(df) == ["DANI"]
    # Con los dos formatos de Parranda: Ana y Dani (Beto compra además arroz).
    df = recortar(filas(), ["PARRANDA"], ["PARRANDA 500 ML", "PARRANDA 1.5 L"], True)
    assert clientes(df) == ["ANA", "DANI"]


def test_solo_compran_esto_solo_con_grupo_se_comporta_como_antes():
    df = recortar(filas(), ["PARRANDA"], [], True)
    assert clientes(df) == ["ANA", "DANI"]
