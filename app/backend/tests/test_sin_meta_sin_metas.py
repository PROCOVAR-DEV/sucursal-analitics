"""Quien está marcado «sin meta» no arrastra metas de cuando sí la llevaba.

El 01/10/2026 Sidney estaba sin cuota —0 HL, sin formatos— y aun así le salían 504
unidades de plan en arroz, aceite, azúcar, papel y caja de buffet, con su barra de
cumplimiento al 0 %. Eran las metas guardadas de un mes en que sí llevaba cuota.

Se limpia al LEER la configuración, no al guardarla: así vale para lo que ya está en la
base y nadie tiene que volver a guardar nada. El dato sigue ahí por si se le vuelve a dar
cuota; lo que se quita es que cuente mientras no la lleve.
"""
from __future__ import annotations

from services.sucursal_store import config_for_period

SUC = {
    "nombre": "Santiago",
    "gestores": {
        "GARI": {"nombre": "Gari", "activo": True},
        "SIDNEY": {"nombre": "Sidney", "activo": True, "sin_meta": True},
    },
    "metas_mensuales": {
        "2026-10": {
            "gestores": {
                "GARI": {"cuota_hl": 278.43,
                         "metas_formato": {"PARRANDA-1500": 177.93},
                         "metas_cantidad": {"ARROZ": 157.0}},
                # Lo que tenía guardado de cuando sí llevaba cuota.
                "SIDNEY": {"cuota_hl": 232.44,
                           "metas_formato": {"PARRANDA-1500": 91.08},
                           "metas_cantidad": {"ARROZ": 157.0, "ACEITE SOYA": 124.0}},
            },
        },
    },
}


def gestores(y=2026, m=10):
    return config_for_period(SUC, y, m)["gestores"]


def test_al_sin_meta_no_le_queda_ninguna_meta():
    """EL CASO DE SIDNEY: ni hectolitros, ni cantidades, ni cuota."""
    s = gestores()["SIDNEY"]

    assert s["metas_cantidad"] == {}
    assert s["metas_formato"] == {}
    assert s["cuota_hl"] == 0.0
    assert s["cuota_ccc"] == 0.0


def test_pero_sigue_estando():
    """No se le borra del roster: vende y sus ventas cuentan para el total de la
    oficina. Lo único que no tiene es objetivo."""
    g = gestores()

    assert "SIDNEY" in g
    assert g["SIDNEY"]["nombre"] == "Sidney"
    assert g["SIDNEY"]["activo"] is True


def test_a_los_demas_no_les_toca_nada():
    """La guarda no puede llevarse por delante a quien sí lleva cuota."""
    g = gestores()["GARI"]

    assert g["cuota_hl"] == 278.43
    assert g["metas_formato"] == {"PARRANDA-1500": 177.93}
    assert g["metas_cantidad"] == {"ARROZ": 157.0}


def test_se_limpia_al_LEER_y_el_dato_guardado_sigue_intacto():
    """Es lo que hace que valga para lo ya guardado sin que nadie reguarde."""
    config_for_period(SUC, 2026, 10)

    crudo = SUC["metas_mensuales"]["2026-10"]["gestores"]["SIDNEY"]
    assert crudo["metas_cantidad"] == {"ARROZ": 157.0, "ACEITE SOYA": 124.0}
    assert crudo["cuota_hl"] == 232.44
