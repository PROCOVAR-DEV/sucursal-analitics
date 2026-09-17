"""
AUDITORIA EN FRIO del reparto de metas por SKU (17/09/2026).

La invariante que se audita, una sola:

    sum(plan(vendedor, sku))  ==  sum(meta_global(sku))

Si se reparte menos, hay HL que no se lleva nadie y la sucursal arranca el mes
debiendo sin que se vea. Si se reparte mas, alguien carga con una meta que nunca
se puso.

No hay `fastapi` en el entorno de pruebas, asi que el trozo de decision del
endpoint (`main.py::src_plan_sku`, lineas 903-917) se reproduce aqui LITERAL en
`_seleccion_endpoint`. Es copia textual: si alguien cambia el endpoint sin tocar
esto, estas pruebas dejan de auditar lo que dicen auditar.
"""
from services.plan_sku import repartir_plan_sku
from services.roster import filtrar_por_baja, quien_recibe

FMT = ["P1500", "M1500", "M330"]

# Ventas del mes de referencia. AMSALE y SIDNEY son los dos casos reales del
# 17/09/2026: vendieron de verdad y no pueden llevar meta.
VENTAS = {
    "GARI":     {"P1500": 400.0, "M1500": 100.0, "M330": 10.0},
    "TADYSLAI": {"P1500": 300.0, "M1500": 100.0, "M330": 10.0},
    "AMSALE":   {"P1500": 200.0, "M1500": 100.0, "M330": 10.0},
    "SIDNEY":   {"P1500": 100.0, "M1500": 100.0, "M330": 10.0},
}
GLOBAL = {"P1500": 3168.0, "M1500": 792.0, "M330": 196.0}


def _repartido(r) -> float:
    return round(sum(r["total_por_gestor"].values()), 2)


def _pedido(metas) -> float:
    return round(sum(v for v in metas.values() if v > 0), 2)


def _cuadra(r, metas=None, tol=0.05) -> bool:
    """La invariante con el margen del redondeo por celda.

    El redondeo tiene prueba PROPIA mas abajo (`test_el_redondeo_*`): aqui se le
    da margen a proposito para que estas pruebas midan SOLO el mecanismo de
    exclusion y no se contaminen con el otro fallo.
    """
    return abs(_repartido(r) - _pedido(GLOBAL if metas is None else metas)) <= tol


def _seleccion_endpoint(ventas, roster_bruto, periodo_plan, marcados_qs=()):
    """Llama a la MISMA funcion que el endpoint (`quien_recibe`), no a una copia.

    Antes esto era una copia literal de main.py y por eso seguia auditando la version
    vieja despues de arreglarla. El criterio vive en `services/roster.py` justo para
    que aqui no haya que duplicarlo.

    El filtro se aplica SIEMPRE, incluso con el conjunto vacio: "no queda nadie" no es
    lo mismo que "no hubo criterio". (El endpoint, ademas, contesta 400 en ese caso.)
    """
    roster = filtrar_por_baja(roster_bruto, periodo_plan)
    reciben = quien_recibe(roster, marcados_qs)
    return {g: v for g, v in ventas.items() if g in reciben}


def _plan(ventas, roster, periodo="2026-09", marcados=(), metas=None):
    metas = GLOBAL if metas is None else metas
    v = _seleccion_endpoint(ventas, roster, periodo, marcados)
    return repartir_plan_sku(v, metas, FMT)


TODOS = {g: {"nombre": g} for g in VENTAS}


# ---------------------------------------------------------------- via 1: sin_meta
def test_sin_meta_sale_del_denominador():
    roster = {**TODOS, "AMSALE": {"nombre": "AMSALE", "sin_meta": True}}
    r = _plan(VENTAS, roster)
    assert "AMSALE" not in r["por_gestor"]
    assert _cuadra(r), f"los HL de AMSALE se evaporaron: {_repartido(r)}"


# ---------------------------------------------------------------- via 2: baja_desde
def test_baja_desde_sale_del_denominador():
    roster = {**TODOS, "AMSALE": {"nombre": "AMSALE", "baja_desde": "2026-09"}}
    r = _plan(VENTAS, roster, periodo="2026-09")
    assert "AMSALE" not in r["por_gestor"]
    assert _cuadra(r), f"se repartieron {_repartido(r)} de {_pedido(GLOBAL)}"


def test_baja_del_mes_siguiente_todavia_recibe():
    roster = {**TODOS, "AMSALE": {"nombre": "AMSALE", "baja_desde": "2026-10"}}
    r = _plan(VENTAS, roster, periodo="2026-09")
    assert r["total_por_gestor"]["AMSALE"] > 0
    assert _cuadra(r), f"se repartieron {_repartido(r)} de {_pedido(GLOBAL)}"


# ---------------------------------------------------- via 3: casilla "EN EL MES"
def test_desmarcado_en_pantalla_sale_del_denominador():
    r = _plan(VENTAS, TODOS, marcados=["GARI", "TADYSLAI", "SIDNEY"])
    assert "AMSALE" not in r["por_gestor"]
    assert _cuadra(r), f"se repartieron {_repartido(r)} de {_pedido(GLOBAL)}"


# ------------------------------------------------------------------ combinaciones
def test_sin_meta_y_ademas_desmarcado():
    roster = {**TODOS, "AMSALE": {"nombre": "AMSALE", "sin_meta": True}}
    r = _plan(VENTAS, roster, marcados=["GARI", "TADYSLAI", "SIDNEY"])
    assert "AMSALE" not in r["por_gestor"]
    assert _cuadra(r), f"se repartieron {_repartido(r)} de {_pedido(GLOBAL)}"


def test_de_baja_que_si_vendio_mas_uno_sin_meta():
    roster = {
        **TODOS,
        "AMSALE": {"nombre": "AMSALE", "baja_desde": "2026-09"},
        "SIDNEY": {"nombre": "SIDNEY", "sin_meta": True},
    }
    r = _plan(VENTAS, roster)
    assert set(r["por_gestor"]) == {"GARI", "TADYSLAI"}
    assert _cuadra(r), f"se repartieron {_repartido(r)} de {_pedido(GLOBAL)}"


def test_todos_excluidos_menos_uno():
    r = _plan(VENTAS, TODOS, marcados=["GARI"])
    assert set(r["por_gestor"]) == {"GARI"}
    assert _cuadra(r), f"se repartieron {_repartido(r)} de {_pedido(GLOBAL)}"


# --------------------------------------------- FALLO 1: `if reciben:` se rinde
def test_si_NADIE_recibe_no_se_debe_repartir_a_todos():
    """Toda la sucursal marcada `sin_meta` -> `reciben` queda vacio.

    main.py:915 dice `if reciben:` en vez de comprobar si hubo criterio. Con el
    conjunto vacio NO filtra nada, asi que los 4.156 HL se reparten entre los
    cuatro que acaban de declararse sin cuota.
    """
    roster = {g: {"nombre": g, "sin_meta": True} for g in VENTAS}
    r = _plan(VENTAS, roster)
    assert r["por_gestor"] == {}, (
        "nadie debia recibir y recibieron todos: " + str(r["total_por_gestor"])
    )


def test_marcar_solo_a_alguien_sin_meta_no_puede_repartir_a_todos():
    """El caso que llega solo: se deja marcado EN EL MES a quien es `sin_meta`.

    `reciben` = roster sin sin_meta = {GARI, TADYSLAI, SIDNEY};
    `marcados` = {AMSALE}; la interseccion es vacia -> `if reciben:` no filtra ->
    reparte entre los CUATRO, incluidos los tres que el usuario desmarco.
    """
    roster = {**TODOS, "AMSALE": {"nombre": "AMSALE", "sin_meta": True}}
    r = _plan(VENTAS, roster, marcados=["AMSALE"])
    assert set(r["por_gestor"]) <= {"AMSALE"}, (
        "se repartio a quien no se marco: " + str(sorted(r["por_gestor"]))
    )


def test_el_ultimo_que_queda_se_da_de_baja():
    """Mes en que todo el roster esta de baja: `roster` vacio -> `reciben` vacio.

    Otra vez `if reciben:` deja pasar el reparto entero a gente que ya no esta.
    """
    roster = {g: {"nombre": g, "baja_desde": "2026-01"} for g in VENTAS}
    r = _plan(VENTAS, roster, periodo="2026-09")
    assert r["por_gestor"] == {}, (
        "reparte a un roster vacio: " + str(r["total_por_gestor"])
    )


# ------------------------------------------- FALLO 2: el redondeo pierde HL
def test_el_redondeo_por_celda_no_pierde_hectolitros():
    """`round(..., 2)` por celda (plan_sku.py:87) y la suma ya no es la meta.

    Tres vendedores iguales y una meta de 100: 33,33 x 3 = 99,99.
    """
    v = {"A": {"P1500": 1.0}, "B": {"P1500": 1.0}, "C": {"P1500": 1.0}}
    r = repartir_plan_sku(v, {"P1500": 100.0}, ["P1500"])
    assert _repartido(r) == 100.0, f"se repartieron {_repartido(r)} de 100"


def test_el_redondeo_en_una_sucursal_de_verdad():
    """Ocho vendedores y cinco formatos, con cifras de las que llegan de verdad.

    MAGNITUD: simulando 2.000 sucursales al azar (5-8 vendedores, 5 formatos,
    4.386 HL de meta) el peor descuadre fue de 0,06 HL. Rompe la invariante tal
    como esta escrita —"exactamente"— pero NO es de la familia de los 589 HL:
    son centesimas. Se informa para que nadie escriba un cuadre exacto contra
    esto y se lleve un susto.
    """
    v = {
        "G0": {"P1500": 171.90, "P500": 4.11, "P330": 6.40, "M1500": 52.20, "M330": 11.10},
        "G1": {"P1500": 169.56, "P500": 1.02, "P330": 3.14, "M1500": 52.02, "M330": 19.02},
        "G2": {"P1500": 172.80, "P500": 2.07, "P330": 6.34, "M1500": 58.05, "M330": 8.46},
        "G3": {"P1500": 135.09, "P500": 3.03, "P330": 3.90, "M1500": 40.14, "M330": 8.08},
        "G4": {"P1500": 706.68, "P500": 5.09, "P330": 12.32, "M1500": 149.76, "M330": 35.02},
    }
    metas = {"P1500": 3168.0, "P500": 90.0, "P330": 140.0, "M1500": 792.0, "M330": 196.0}
    r = repartir_plan_sku(v, metas, list(metas))
    assert _repartido(r) == _pedido(metas), (
        f"se repartieron {_repartido(r)} de {_pedido(metas)}"
    )


# ------------------------------- FALLO 3: metas que el reparto ni mira ni avisa
def test_una_meta_de_un_formato_fuera_de_la_lista_no_puede_desaparecer():
    """`formatos` manda sobre `metas_globales` (plan_sku.py:57).

    Una meta cuyo formato no este en la lista no se reparte NI sale en `sin_base`:
    desaparece en silencio. Hoy `main.py:947` construye `globales` a partir de
    `formatos`, asi que no llega por el endpoint — pero la funcion pura lo acepta
    y no lo denuncia.
    """
    metas = {"P1500": 100.0, "M500": 50.0}
    r = repartir_plan_sku({"A": {"P1500": 10.0}}, metas, ["P1500"])
    assert _repartido(r) == _pedido(metas) or "M500" in r["sin_base"], (
        f"faltan {_pedido(metas) - _repartido(r)} HL y sin_base dice {r['sin_base']}"
    )


def test_una_meta_negativa_se_denuncia():
    """Un signo de menos de mas al teclear: 200 HL que no se reparten y nadie avisa.

    `if meta > 0 and total <= 0` (plan_sku.py:78) solo mira metas positivas, y
    `round(v/total*meta, 2) if (meta > 0 ...)` deja la celda en 0 sin mas.
    """
    metas = {"P1500": 3168.0, "M1500": -200.0, "M330": 196.0}
    r = repartir_plan_sku(VENTAS, metas, FMT)
    assert "M1500" in r["sin_base"], (
        f"meta -200 tragada en silencio; sin_base = {r['sin_base']}"
    )


# ------------------------------------------- FALLO 4: ventas negativas
def test_una_devolucion_no_puede_dar_un_plan_negativo():
    """SIDNEY devolvio mas de lo que vendio: le sale meta NEGATIVA.

    Nadie puede tener una meta de -x HL, y el resto carga con la diferencia.
    """
    v = {"GARI": {"P1500": 100.0}, "SIDNEY": {"P1500": -20.0}}
    r = repartir_plan_sku(v, {"P1500": 100.0}, ["P1500"])
    assert r["por_gestor"]["SIDNEY"]["P1500"] >= 0, (
        f"plan negativo: {r['por_gestor']}"
    )


def test_ventas_que_se_anulan_dejan_el_sku_entero_sin_repartir():
    """+120 y -120 -> total 0 -> el SKU cae en `sin_base` y sus 792 HL no se reparten.

    Sale avisado (`sin_base`), pero la invariante se rompe: son 792 HL que nadie
    lleva hasta que alguien los ponga a mano.
    """
    v = {"A": {"M1500": 120.0}, "B": {"M1500": -120.0}}
    r = repartir_plan_sku(v, {"M1500": 792.0}, ["M1500"])
    assert _repartido(r) == 792.0, (
        f"se repartieron {_repartido(r)} de 792; sin_base = {r['sin_base']}"
    )


# ------------------------------------------------------------ casos limite
def test_meta_global_cero_no_reparte_nada_y_no_se_queja():
    r = repartir_plan_sku(VENTAS, {f: 0.0 for f in FMT}, FMT)
    assert _repartido(r) == 0.0
    assert r["sin_base"] == []


def test_mes_base_sin_datos_deja_TODA_la_meta_sin_repartir():
    """Se elige un `mes_base` sin ventas: `por_gestor` vacio y los 4.156 HL al aire.

    Va avisado en `sin_base`, que es lo unico que salva el caso.
    """
    r = repartir_plan_sku({}, GLOBAL, FMT)
    assert r["por_gestor"] == {}
    assert sorted(r["sin_base"]) == sorted(FMT)
    assert _repartido(r) == 0.0


def test_un_solo_vendedor_se_lleva_el_100_y_NADA_lo_avisa():
    """Si un SKU lo vendio una sola persona, se lleva la meta global entera.

    Es lo correcto segun la regla, pero no hay un solo campo en la respuesta que
    lo diga: ni `sin_base`, ni `fuera_del_reparto`, ni una marca de concentracion.
    Quien planifica ve 3.168 HL en una fila y no tiene como saber que salieron de
    una unica venta de 0,5 HL.
    """
    v = {"GARI": {"P1500": 0.5}, "TADYSLAI": {"P1500": 0.0}}
    r = repartir_plan_sku(v, {"P1500": 3168.0}, ["P1500"])
    assert r["por_gestor"]["GARI"]["P1500"] == 3168.0
    assert r["sin_base"] == []
    assert not [k for k in r if "concentra" in k or "aviso" in k or "alerta" in k]


def test_un_nombre_que_el_roster_no_conoce_se_lleva_su_parte_a_la_tumba():
    """Descuadre de claves entre el informe y el roster.

    `ventas` viene de `compute_metas_gestor` con la clave del roster del mes de
    REFERENCIA (metas_gestor.py:173); `reciben` sale del roster del mes que se
    PLANIFICA. Si el mes nuevo renombro la clave, el filtro de main.py:916 no lo
    reconoce y sus ventas salen del denominador: correcto para la invariante,
    invisible para quien planifica — `fuera_del_reparto` si lo lista.
    """
    roster = {g: {"nombre": g} for g in ("GARI", "TADYSLAI", "AMSALE")}   # falta SIDNEY
    r = _plan(VENTAS, roster)
    assert "SIDNEY" not in r["por_gestor"]
    assert _cuadra(r), f"se repartieron {_repartido(r)} de {_pedido(GLOBAL)}"


# ------------------------------------------- FRONT: el plan viejo que sobrevive
def test_SIMULACION_FRONT_el_plan_viejo_cuenta_en_el_total_de_pantalla():
    """CalculadoraView.jsx:216-231 + 284, reproducido en cuatro lineas.

    AMSALE esta marcada EN EL MES (la casilla viene marcada por defecto: `enMes`
    es `incluidos[k] !== false`) pero es `sin_meta`, asi que el backend NO la
    devuelve en `por_gestor`. El front hace `if (!plan) return;` y le deja el plan
    que ya tenia; `grandTotal` suma a todo el que este `enMes`, incluida ella.
    """
    roster = {**TODOS, "AMSALE": {"nombre": "AMSALE", "sin_meta": True}}
    r = _plan(VENTAS, roster, marcados=list(VENTAS))     # la pantalla las manda TODAS

    quick = {g: 0.0 for g in VENTAS}
    quick["AMSALE"] = 232.44        # seedRows(STD_FMT) = el plan de Camaguey de siempre

    # setQuick(prev => ({...prev, ...q})) — solo se pisan los que trajo el reparto
    # Arreglado: a quien va EN EL MES y no le toca nada se le pone CERO, no se le deja
    # el plan viejo. Antes el fantasma de 232,44 (seedRows) seguia sumando en el total.
    quick.update({g: 0.0 for g in quick})
    quick.update({g: t for g, t in r["total_por_gestor"].items()})
    # const grandTotal = gestores.reduce((s,[k]) => s + (enMes(k) ? vendorHL(k) : 0), 0)
    grand_total = round(sum(quick.values()), 2)

    assert grand_total == _pedido(GLOBAL), (
        f"la pantalla suma {grand_total} y las metas globales son {_pedido(GLOBAL)}"
    )


def test_SIMULACION_FRONT_marcar_solo_a_alguien_sin_cuota_se_RECHAZA():
    """Era la recaida numero CUATRO, y se llegaba con dos clics.

    El planificador desmarca a todos menos a AMSALE, que ademas esta `sin_meta`.
    Antes: `reciben` quedaba vacio, `if reciben:` no filtraba, el backend repartia
    entre los CUATRO y el front solo pintaba a AMSALE -> 880,60 de 4.156, con 3.275,40
    perdidos en silencio.

    Lo correcto NO es repartir los 4.156 a AMSALE: no tiene cuota por configuracion.
    Es que no haya respuesta posible y se DIGA. Hoy pasa en dos sitios:

      · el front no manda a los `sin_meta`, asi que la lista sale vacia y avisa antes
        de llamar;
      · y si llegara igual, `quien_recibe` devuelve vacio y el endpoint contesta 400.

    Aqui se comprueba lo segundo, que es la red de abajo.
    """
    roster = {**TODOS, "AMSALE": {"nombre": "AMSALE", "sin_meta": True}}
    r = _plan(VENTAS, roster, marcados=["AMSALE"])

    assert r["por_gestor"] == {}, (
        "no habia nadie que pudiera recibir y se repartio igual: "
        + str(r["total_por_gestor"])
    )
