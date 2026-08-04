"""Pruebas del motor de reglas de comisión.

La prueba que de verdad importa es `test_sin_reglas_no_cambia_nada`: mientras
nadie cree una regla, la comisión tiene que salir EXACTAMENTE igual que con el
cálculo plano de siempre. Si eso se rompe, activar esta función movería cifras
que ya se pagaron.
"""
from __future__ import annotations

import pandas as pd
import pytest

from services.comisiones import (
    TIPO_GRUPO,
    TIPO_PRODUCTO,
    comision_de,
    reglas_vigentes,
    solapes,
)


@pytest.fixture(autouse=True)
def _init():
    """Anula el fixture global que abre la base de datos.

    Este módulo es puro —entra config, sale número— y no toca nada persistente.
    Atarlo a Postgres solo conseguiría que las reglas de comisión dejaran de
    poder probarse cuando la base no esté a mano, que es justo cuando más falta
    hace comprobarlas.
    """
    yield


def lineas(*filas) -> pd.DataFrame:
    """(producto, grupo, importe) -> DataFrame como el que llega del enriquecido."""
    return pd.DataFrame(
        [{"Mercancia": p, "GrupoComercial": g, "Importe": i} for p, g, i in filas]
    )


def regla(rid, nombre, tipo, objetivo, pct, desde, hasta=None, creada="2026-08-01T00:00:00"):
    return {"id": rid, "nombre": nombre, "tipo": tipo, "objetivo": objetivo,
            "pct": pct, "desde": desde, "hasta": hasta, "creada": creada, "activa": True}


DF = lineas(
    ("ARROZ GRANO LARGO 1KG", "ALIMENTOS", 1000.0),
    ("CERVEZA PARRANDA 330", "PARRANDA", 2000.0),
    ("PAPEL HIGIENICO HS 275", "OTRO", 500.0),
)


def test_sin_reglas_no_cambia_nada():
    r = comision_de(DF, 0.01, [], "2026-08")
    assert r["base"] == 3500.0
    assert r["comision"] == pytest.approx(35.0)
    assert r["detalle"] == []


def test_sin_reglas_vigentes_es_igual_que_sin_reglas():
    # Una regla que aún no ha empezado no debe tocar el mes anterior.
    futura = [regla("r1", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-09")]
    assert comision_de(DF, 0.01, futura, "2026-08") == comision_de(DF, 0.01, [], "2026-08")


def test_regla_por_producto_y_por_grupo_a_la_vez():
    reglas = [
        regla("r1", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08"),
        regla("r2", "Parranda 0,8%", TIPO_GRUPO, "PARRANDA", 0.008, "2026-08"),
    ]
    r = comision_de(DF, 0.01, reglas, "2026-08")
    # arroz 1000*2% + parranda 2000*0,8% + resto 500*1% general
    assert r["comision"] == pytest.approx(20.0 + 16.0 + 5.0)
    assert r["base"] == 3500.0

    por_nombre = {d["nombre"]: d for d in r["detalle"]}
    assert por_nombre["Comisión general"]["base"] == 500.0
    assert por_nombre["Arroz 2%"]["comision"] == pytest.approx(20.0)
    assert por_nombre["Parranda 0,8%"]["comision"] == pytest.approx(16.0)


def test_la_mas_nueva_gana_el_solape():
    reglas = [
        regla("vieja", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08", creada="2026-08-01T00:00:00"),
        regla("nueva", "Arroz 3%", TIPO_PRODUCTO, "ARROZ", 0.03, "2026-08", creada="2026-08-04T00:00:00"),
    ]
    r = comision_de(DF, 0.01, reglas, "2026-08")
    # 1000*3% (gana la nueva) + 2500*1% general
    assert r["comision"] == pytest.approx(30.0 + 25.0)
    assert reglas_vigentes(reglas, "2026-08")[0]["id"] == "nueva"


def test_se_avisa_del_solape_y_de_quien_manda():
    reglas = [
        regla("vieja", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08", creada="2026-08-01T00:00:00"),
        regla("nueva", "Arroz 3%", TIPO_PRODUCTO, "ARROZ", 0.03, "2026-08", creada="2026-08-04T00:00:00"),
    ]
    avisos = solapes(reglas)
    assert len(avisos) == 1
    assert avisos[0]["gana"]["id"] == "nueva"
    assert "Arroz 3%" in avisos[0]["mensaje"]


def test_no_hay_solape_si_una_termina_antes_de_empezar_la_otra():
    reglas = [
        regla("r1", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-01", hasta="2026-07"),
        regla("r2", "Arroz 3%", TIPO_PRODUCTO, "ARROZ", 0.03, "2026-08"),
    ]
    assert solapes(reglas) == []
    # y cada mes usa la suya
    assert comision_de(DF, 0.01, reglas, "2026-07")["comision"] == pytest.approx(20.0 + 25.0)
    assert comision_de(DF, 0.01, reglas, "2026-08")["comision"] == pytest.approx(30.0 + 25.0)


def test_distinto_objetivo_no_es_solape():
    reglas = [
        regla("r1", "Arroz", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08"),
        regla("r2", "Parranda", TIPO_GRUPO, "PARRANDA", 0.008, "2026-08"),
    ]
    assert solapes(reglas) == []


def test_regla_cerrada_deja_de_aplicarse_al_mes_siguiente():
    reglas = [regla("r1", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-06", hasta="2026-07")]
    assert comision_de(DF, 0.01, reglas, "2026-07")["comision"] == pytest.approx(20.0 + 25.0)
    assert comision_de(DF, 0.01, reglas, "2026-08")["comision"] == pytest.approx(35.0)


def test_regla_desactivada_no_cuenta():
    r = regla("r1", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08")
    r["activa"] = False
    assert comision_de(DF, 0.01, [r], "2026-08")["comision"] == pytest.approx(35.0)
    assert solapes([r]) == []


def test_dataframe_vacio_no_revienta():
    r = comision_de(pd.DataFrame(), 0.01, [], "2026-08")
    assert r["comision"] == 0.0 and r["detalle"] == []


# --------------------------------------------------------- lo general y lo concreto
#
# Caso que planteó Jose: "si pongo arroz la comisión va para todos los arroz; si
# especifico arroz pateko, pues para ese solamente".

ARROCES = lineas(
    ("ARROZ PATEKO 1KG", "ALIMENTOS", 1000.0),
    ("ARROZ GRANO LARGO 1KG", "ALIMENTOS", 2000.0),
    ("ACEITE GIRASOL 1L", "ALIMENTOS", 500.0),
)


def test_regla_generica_cubre_todos_los_arroces():
    reglas = [regla("r1", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08")]
    r = comision_de(ARROCES, 0.01, reglas, "2026-08")
    # los dos arroces al 2%, el aceite a la general
    assert r["comision"] == pytest.approx(3000.0 * 0.02 + 500.0 * 0.01)


def test_la_especifica_manda_sobre_la_generica():
    reglas = [
        regla("gen", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08"),
        regla("esp", "Pateko 3%", TIPO_PRODUCTO, "ARROZ PATEKO", 0.03, "2026-08"),
    ]
    r = comision_de(ARROCES, 0.01, reglas, "2026-08")
    # pateko 1000*3%, el otro arroz 2000*2%, aceite 500*1%
    assert r["comision"] == pytest.approx(30.0 + 40.0 + 5.0)


def test_crear_la_generica_despues_no_se_lleva_por_delante_la_especifica():
    """El caso peligroso: la genérica es MÁS NUEVA que la específica."""
    reglas = [
        regla("esp", "Pateko 3%", TIPO_PRODUCTO, "ARROZ PATEKO", 0.03, "2026-08", creada="2026-08-01T00:00:00"),
        regla("gen", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08", creada="2026-08-04T00:00:00"),
    ]
    r = comision_de(ARROCES, 0.01, reglas, "2026-08")
    assert r["comision"] == pytest.approx(30.0 + 40.0 + 5.0)
    assert reglas_vigentes(reglas, "2026-08")[0]["id"] == "esp"


def test_generica_y_especifica_no_se_avisan_como_solape():
    """No es un conflicto: es afinar. Avisar aquí sería ruido."""
    reglas = [
        regla("gen", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08"),
        regla("esp", "Pateko 3%", TIPO_PRODUCTO, "ARROZ PATEKO", 0.03, "2026-08"),
    ]
    assert solapes(reglas) == []


def test_producto_concreto_manda_sobre_el_grupo_entero():
    df = lineas(("CERVEZA PARRANDA 330", "PARRANDA", 1000.0), ("RON PARRANDA", "PARRANDA", 500.0))
    reglas = [
        regla("g", "Parranda 0,8%", TIPO_GRUPO, "PARRANDA", 0.008, "2026-08"),
        regla("p", "Cerveza 5%", TIPO_PRODUCTO, "CERVEZA PARRANDA", 0.05, "2026-08"),
    ]
    r = comision_de(df, 0.01, reglas, "2026-08")
    assert r["comision"] == pytest.approx(1000.0 * 0.05 + 500.0 * 0.008)


# ------------------------------------------------------------ alta y validación

from services.comisiones import normalizar_regla  # noqa: E402


def test_alta_pone_id_y_fecha_de_creacion():
    r = normalizar_regla({"tipo": TIPO_PRODUCTO, "objetivo": "ARROZ", "pct": 0.02, "desde": "2026-08"},
                         ahora="2026-08")
    assert r["id"] and r["creada"] and r["activa"] is True
    assert r["nombre"] == "ARROZ 2%"   # se autocompleta si no se pone


def test_no_se_puede_empezar_en_un_mes_pasado():
    with pytest.raises(ValueError, match="ya pasado"):
        normalizar_regla({"tipo": TIPO_PRODUCTO, "objetivo": "ARROZ", "pct": 0.02, "desde": "2026-07"},
                         ahora="2026-08")


def test_no_se_puede_cerrar_en_un_mes_pasado():
    vieja = regla("r1", "Arroz", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-01")
    with pytest.raises(ValueError, match="ya calculadas"):
        normalizar_regla({"hasta": "2026-07"}, existente=vieja, ahora="2026-08")


def test_una_regla_vieja_se_puede_seguir_editando():
    """Su propio `desde` de hace meses no debe bloquear subirle el %."""
    vieja = regla("r1", "Arroz", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-01")
    r = normalizar_regla({"pct": 0.03}, existente=vieja, ahora="2026-08")
    assert r["pct"] == 0.03 and r["desde"] == "2026-01" and r["id"] == "r1"


def test_se_puede_cerrar_en_el_mes_en_curso_o_despues():
    vieja = regla("r1", "Arroz", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-01")
    assert normalizar_regla({"hasta": "2026-08"}, existente=vieja, ahora="2026-08")["hasta"] == "2026-08"
    assert normalizar_regla({"hasta": "2026-12"}, existente=vieja, ahora="2026-08")["hasta"] == "2026-12"


def test_porcentaje_en_tanto_por_uno_no_en_porciento():
    """Escribir 2 en vez de 0.02 sería pagar un 200%: se corta con un mensaje claro."""
    with pytest.raises(ValueError, match="fracción"):
        normalizar_regla({"tipo": TIPO_PRODUCTO, "objetivo": "ARROZ", "pct": 2, "desde": "2026-08"},
                         ahora="2026-08")


def test_faltan_datos_obligatorios():
    with pytest.raises(ValueError, match="Falta a qué se aplica"):
        normalizar_regla({"tipo": TIPO_PRODUCTO, "objetivo": "  ", "pct": 0.02, "desde": "2026-08"}, ahora="2026-08")
    with pytest.raises(ValueError, match="AAAA-MM"):
        normalizar_regla({"tipo": TIPO_PRODUCTO, "objetivo": "ARROZ", "pct": 0.02}, ahora="2026-08")
    with pytest.raises(ValueError, match="Tipo desconocido"):
        normalizar_regla({"tipo": "loquesea", "objetivo": "ARROZ", "pct": 0.02, "desde": "2026-08"}, ahora="2026-08")


def test_el_cliente_no_puede_falsear_la_fecha_de_creacion():
    """`creada` decide quién gana un solape: si viniera de fuera se podría colar
    una regla 'más nueva' con fecha inventada."""
    r = normalizar_regla({"tipo": TIPO_PRODUCTO, "objetivo": "ARROZ", "pct": 0.02,
                          "desde": "2026-08", "creada": "2099-01-01T00:00:00"}, ahora="2026-08")
    assert not r["creada"].startswith("2099")


# --------------------------------------------------- reglas globales vs sucursal
#
# Se pueden poner reglas para TODAS las sucursales o solo para una. Lo de la
# sucursal es una excepción a lo general, así que manda cuando apuntan a lo mismo.

from services.comisiones import AMBITO_GLOBAL, AMBITO_SUCURSAL  # noqa: E402


def con_ambito(r, ambito):
    return {**r, "ambito": ambito}


def test_regla_global_se_aplica_si_la_sucursal_no_tiene_nada():
    reglas = [con_ambito(regla("g1", "Arroz 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08"), AMBITO_GLOBAL)]
    r = comision_de(ARROCES, 0.01, reglas, "2026-08")
    assert r["comision"] == pytest.approx(3000.0 * 0.02 + 500.0 * 0.01)


def test_la_sucursal_manda_sobre_la_global_en_el_mismo_objetivo():
    reglas = [
        con_ambito(regla("g1", "Arroz 2% (todas)", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08"), AMBITO_GLOBAL),
        con_ambito(regla("s1", "Arroz 4% (aquí)", TIPO_PRODUCTO, "ARROZ", 0.04, "2026-08"), AMBITO_SUCURSAL),
    ]
    r = comision_de(ARROCES, 0.01, reglas, "2026-08")
    assert r["comision"] == pytest.approx(3000.0 * 0.04 + 500.0 * 0.01)
    assert reglas_vigentes(reglas, "2026-08")[0]["id"] == "s1"


def test_la_sucursal_manda_aunque_la_global_sea_mas_nueva():
    reglas = [
        con_ambito(regla("s1", "Aquí 4%", TIPO_PRODUCTO, "ARROZ", 0.04, "2026-08", creada="2026-08-01T00:00:00"), AMBITO_SUCURSAL),
        con_ambito(regla("g1", "Todas 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08", creada="2026-08-04T00:00:00"), AMBITO_GLOBAL),
    ]
    assert reglas_vigentes(reglas, "2026-08")[0]["id"] == "s1"


def test_lo_mas_especifico_manda_aunque_sea_global():
    """Una global de ARROZ PATEKO gana a una de sucursal de ARROZ: primero se mira
    a qué apunta cada una, y solo si apuntan a lo mismo decide el ámbito."""
    reglas = [
        con_ambito(regla("s1", "Arroz aquí 4%", TIPO_PRODUCTO, "ARROZ", 0.04, "2026-08"), AMBITO_SUCURSAL),
        con_ambito(regla("g1", "Pateko todas 6%", TIPO_PRODUCTO, "ARROZ PATEKO", 0.06, "2026-08"), AMBITO_GLOBAL),
    ]
    r = comision_de(ARROCES, 0.01, reglas, "2026-08")
    # pateko 1000*6% (global específica), otro arroz 2000*4% (sucursal), aceite 500*1%
    assert r["comision"] == pytest.approx(60.0 + 80.0 + 5.0)


def test_el_aviso_dice_que_la_de_la_sucursal_manda():
    reglas = [
        con_ambito(regla("g1", "Todas 2%", TIPO_PRODUCTO, "ARROZ", 0.02, "2026-08"), AMBITO_GLOBAL),
        con_ambito(regla("s1", "Aquí 4%", TIPO_PRODUCTO, "ARROZ", 0.04, "2026-08"), AMBITO_SUCURSAL),
    ]
    avisos = solapes(reglas)
    assert len(avisos) == 1
    assert avisos[0]["gana"]["id"] == "s1"
    assert "manda sobre la global" in avisos[0]["mensaje"]


def test_el_ambito_no_lo_decide_el_cliente():
    """Una petición a la sucursal no puede colar una regla que afecte a todas."""
    r = normalizar_regla({"tipo": TIPO_PRODUCTO, "objetivo": "ARROZ", "pct": 0.02,
                          "desde": "2026-08", "ambito": AMBITO_GLOBAL},
                         ahora="2026-08", ambito=AMBITO_SUCURSAL)
    assert r["ambito"] == AMBITO_SUCURSAL
