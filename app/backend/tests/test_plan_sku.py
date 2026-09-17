"""
El reparto del plan por SKU, contra la hoja real de septiembre de 2026.

Se prueba con las cifras que Procovar llevaba a mano porque es el único sitio
donde se puede comprobar que la regla es la que ellos usan y no la que nosotros
entendimos. Hasta el 17/09/2026 la calculadora sembraba a TODOS los gestores con
la misma tabla escrita en el código, así que dos vendedores con metas distintas
salían con el mismo desglose y el mismo total de 232 HL.
"""
from services.plan_sku import repartir_plan_sku

# Ventas de junio por formato (HL). Los totales son los de la hoja, así que las
# filas incluyen un "RESTO" que junta a los demás comerciales: lo que importa de
# cada caso es la proporción contra el total, no quién es el resto.
VENTAS = {
    "gari":     {"P1500": 171.90, "M1500": 52.20, "M330": 11.10, "P330": 6.40, "P500": 0.00},
    "tadyslai": {"P1500": 169.56, "M1500": 52.02, "M330": 19.02, "P330": 3.14, "P500": 0.00},
    "claudia":  {"P1500": 172.80, "M1500": 58.05, "M330": 8.46,  "P330": 6.34, "P500": 0.00},
    "javier":   {"P1500": 135.09, "M1500": 40.14, "M330": 8.08,  "P330": 3.90, "P500": 1.02},
    "RESTO":    {"P1500": 706.68, "M1500": 149.76, "M330": 35.02, "P330": 12.32, "P500": 0.00},
}
# Lo que Procovar puso como plan del mes (ACTUAL_OFICIAL PROCOVAR).
GLOBAL = {"P1500": 3168.0, "M1500": 792.0, "M330": 196.0, "P330": 0.0, "P500": 0.23}


def test_los_totales_del_mes_anterior_son_los_de_la_hoja():
    r = repartir_plan_sku(VENTAS, GLOBAL)
    assert round(r["totales_anterior"]["P1500"], 2) == 1356.03
    assert round(r["totales_anterior"]["M1500"], 2) == 352.17
    assert round(r["totales_anterior"]["M330"], 2) == 81.68


def test_reparte_cada_sku_por_su_propia_proporcion():
    # Las seis celdas que se comprobaron una a una contra la hoja.
    r = repartir_plan_sku(VENTAS, GLOBAL)["por_gestor"]
    assert r["gari"]["P1500"] == 401.60
    assert r["gari"]["M1500"] == 117.39
    assert r["gari"]["M330"] == 26.64
    assert r["tadyslai"]["P1500"] == 396.13
    assert r["claudia"]["M1500"] == 130.55
    assert r["javier"]["M330"] == 19.39


def test_la_meta_del_vendedor_es_la_suma_de_sus_skus():
    # No se decide aparte: sale de la cuenta. Y coincide con la que ya estaba
    # guardada en la configuracion (Gari 545,63 · Tadyslai 558,76).
    r = repartir_plan_sku(VENTAS, GLOBAL)["total_por_gestor"]
    assert abs(r["gari"] - 545.63) < 0.05
    assert abs(r["tadyslai"] - 558.76) < 0.05


def test_un_sku_sin_meta_global_no_reparte_nada():
    # P330 se vendio, pero este mes no hay plan para el: cero para todos, y no es
    # un formato "sin base" — la base existe, lo que no hay es meta.
    r = repartir_plan_sku(VENTAS, GLOBAL)
    assert r["por_gestor"]["gari"]["P330"] == 0.0
    assert "P330" not in r["sin_base"]


def test_el_unico_que_vendio_un_sku_se_lo_lleva_entero():
    # Javier fue el unico con P500 en junio (1,02 de 1,02).
    r = repartir_plan_sku(VENTAS, GLOBAL)["por_gestor"]
    assert r["javier"]["P500"] == 0.23
    assert r["gari"]["P500"] == 0.0


def test_si_nadie_vendio_ese_sku_NO_se_inventa_el_reparto():
    # Hay meta y no hay con que repartirla. Cualquier reparto seria inventado, asi
    # que va a cero y se DICE, para que quien planifica lo meta a mano. Repartirlo
    # por partes iguales pareceria un dato calculado y nadie volveria a mirarlo.
    r = repartir_plan_sku({"a": {"M500": 0.0}, "b": {"M500": 0.0}}, {"M500": 100.0})
    assert r["sin_base"] == ["M500"]
    assert r["por_gestor"]["a"]["M500"] == 0.0
    assert r["total_por_gestor"]["a"] == 0.0


def test_los_datos_sucios_no_tumban_el_reparto():
    # Un None o un texto donde deberia ir un numero cuenta como cero, no revienta:
    # esto lo alimenta un Excel y siempre llega alguna celda vacia.
    r = repartir_plan_sku({"a": {"P1500": None}, "b": {"P1500": "12"}}, {"P1500": 60.0})
    assert r["por_gestor"]["a"]["P1500"] == 0.0
    assert r["por_gestor"]["b"]["P1500"] == 60.0


def test_la_suma_de_los_planes_ES_la_meta_global():
    # La propiedad que hace que esto sea un reparto y no una estimacion: lo que se
    # reparte es exactamente lo que se pidio repartir, ni mas ni menos.
    r = repartir_plan_sku(VENTAS, GLOBAL)
    for f, meta in GLOBAL.items():
        if meta <= 0:
            continue
        suma = round(sum(g[f] for g in r["por_gestor"].values()), 2)
        assert abs(suma - meta) < 0.05, f"{f}: se repartio {suma} de {meta}"


def test_quitar_a_uno_REPARTE_su_parte_en_vez_de_perderla():
    """El fallo del 17/09/2026: Jose puso 4.559 HL y le salieron 3.970.

    Los 589 que faltaban eran de dos vendedores dados de baja: se les quitaba del
    reparto pero se les dejaba en el denominador, asi que su trozo se evaporaba.
    La forma correcta es sacarlos de las VENTAS — al salir del denominador, su parte
    se reparte sola entre los que quedan y el total vuelve a cuadrar.
    """
    completo = repartir_plan_sku(VENTAS, GLOBAL)
    sin_resto = repartir_plan_sku({k: v for k, v in VENTAS.items() if k != "RESTO"}, GLOBAL)

    # El total sigue siendo la meta global entera, no una parte.
    assert abs(sum(sin_resto["total_por_gestor"].values()) - sum(completo["total_por_gestor"].values())) < 0.1
    # Y a cada uno de los que quedan le toca MAS que antes.
    for g in sin_resto["por_gestor"]:
        assert sin_resto["por_gestor"][g]["P1500"] > completo["por_gestor"][g]["P1500"]
