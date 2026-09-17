"""
La baja de un gestor con fecha, que NO le borra el pasado.

`activo: false` es global y apaga al vendedor en todos los meses: un informe de
cuando si vendia se quedaria sin el, y esos informes ya se miraron, se discutieron
y se pagaron. Eso no es dar de baja, es reescribir el historico.

Lo pidio Jose el 17/09/2026 por el caso de Amsale: ya no es de Procovar pero
vendio los primeros dias del mes, y esas ventas son reales.
"""
from services.roster import filtrar_por_baja

G = {
    "GARI": {"nombre": "Gari", "activo": True},
    "AMSALE": {"nombre": "amsale", "activo": True, "baja_desde": "2026-09"},
}


def test_antes_de_la_baja_sigue_estando():
    assert set(filtrar_por_baja(G, "2026-08")) == {"GARI", "AMSALE"}


def test_el_mes_de_la_baja_ya_no_aparece():
    # `baja_desde` es el mes A PARTIR DEL CUAL deja de contar, ese incluido.
    assert set(filtrar_por_baja(G, "2026-09")) == {"GARI"}


def test_los_meses_siguientes_tampoco():
    assert set(filtrar_por_baja(G, "2026-12")) == {"GARI"}
    assert set(filtrar_por_baja(G, "2027-01")) == {"GARI"}


def test_sin_periodo_no_se_filtra_a_nadie():
    # El acumulado sin mes concreto los quiere a todos: es el historico entero.
    assert set(filtrar_por_baja(G, None)) == {"GARI", "AMSALE"}


def test_una_baja_vacia_o_en_blanco_no_da_de_baja():
    g = {"A": {"baja_desde": ""}, "B": {"baja_desde": "   "}, "C": {}}
    assert set(filtrar_por_baja(g, "2026-09")) == {"A", "B", "C"}


def test_el_cambio_de_anio_se_compara_bien():
    # Comparar textos AAAA-MM funciona porque el mes va con cero delante. Sin eso,
    # "2026-9" seria MAYOR que "2026-12" y la baja no entraria nunca en diciembre.
    g = {"X": {"baja_desde": "2026-02"}}
    assert set(filtrar_por_baja(g, "2026-01")) == {"X"}
    assert set(filtrar_por_baja(g, "2026-12")) == set()
    assert set(filtrar_por_baja(g, "2025-12")) == {"X"}
