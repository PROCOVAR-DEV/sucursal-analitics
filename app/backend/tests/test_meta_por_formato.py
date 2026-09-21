"""
La meta del mes de cada SKU, que es la que se enseña al lado de los hectolitros en el
Resumen.

No hay una meta global guardada aparte: la de la sucursal ES la suma de las de su gente.
Guardar las dos daría dos verdades que se separan en cuanto alguien edite una, y entonces
no se puede creer ninguna. Lo que se prueba aquí es esa suma y la traducción de la clave
guardada (`PARRANDA-1500`) al código de las tablas (`P1500`), que no son lo mismo.
"""
from services.metas_gestor import meta_por_formato


def eff(gestores: dict) -> dict:
    return {"gestores": gestores}


def test_suma_lo_de_todos_los_gestores():
    m = meta_por_formato(eff({
        "GARI": {"metas_formato": {"PARRANDA-1500": 400.0, "MALTA-1500": 120.0}},
        "CLAUDIA": {"metas_formato": {"PARRANDA-1500": 396.13, "MALTA-330": 20.0}},
    }))

    assert m["P1500"] == 796.13
    assert m["M1500"] == 120.0
    assert m["M330"] == 20.0


def test_traduce_la_clave_guardada_al_codigo_de_la_tabla():
    m = meta_por_formato(eff({"GARI": {"metas_formato": {
        "PARRANDA-330": 5.0, "MALTA-500": 7.0, "GUAJIRA-1500": 9.0,
    }}}))

    assert m == {"P330": 5.0, "M500": 7.0, "M1500": 9.0}


def test_un_gestor_dado_de_baja_no_pone_meta():
    """`activo: False` sale de `gestor_keys`, así que su meta no cuenta — si contara,
    la sucursal tendría que cumplir la cuota de alguien que ya no está."""
    m = meta_por_formato(eff({
        "GARI": {"metas_formato": {"PARRANDA-1500": 400.0}},
        "AMSALE": {"activo": False, "metas_formato": {"PARRANDA-1500": 130.0}},
    }))

    assert m["P1500"] == 400.0


def test_sin_meta_no_aparece_el_formato():
    """Y así la pantalla pone una raya en vez de un 0 %, que se lee como «va fatal»."""
    m = meta_por_formato(eff({"GARI": {"metas_formato": {"PARRANDA-1500": 400.0}}}))

    assert "M500" not in m


def test_lo_que_no_se_entiende_se_ignora_en_vez_de_reventar():
    """Estas claves las teclea alguien en una pantalla: una rara no puede tumbar el
    Resumen entero de la sucursal."""
    m = meta_por_formato(eff({"GARI": {"metas_formato": {
        "PARRANDA-1500": "400", "REFRESCO-500": 10.0, "SIN-GUION": 3.0, "MALTA-330": None,
        "PARRANDA-330": "no es un numero",
    }}}))

    assert m["P1500"] == 400.0      # el texto numérico sí entra
    assert m["M330"] == 0.0         # None cuenta como cero, no rompe
    assert "P330" not in m or m["P330"] == 0.0
    assert all(not k.startswith("R") for k in m)


def test_sin_gestores_no_hay_metas():
    assert meta_por_formato({}) == {}
    assert meta_por_formato(eff({"GARI": {}})) == {}
