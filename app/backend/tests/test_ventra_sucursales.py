"""La tabla de sucursal a base de Ventra.

Equivocarse aquí no da error: da un informe con las ventas de otra sucursal dentro, y
eso no lo detecta nadie mirando la pantalla. Por eso se fija con pruebas.
"""
import pytest

from services.ventra_sucursales import (
    BASE_POR_SUCURSAL,
    base_de,
    sucursal_de,
)


def test_las_tres_que_no_cuadran_por_el_nombre():
    # Son las que un emparejado por parecido de texto se llevaría por delante.
    assert base_de("holguin") == "holguinmoa"
    assert base_de("sancti-spiritus") == "sspiritus"
    assert base_de("santiago-de-cuba") == "santiago"


def test_moa_y_palma_van_aparte_de_su_provincia():
    """Decisión de Jose, 05/09/2026: venden por su cuenta y se miran solas."""
    assert base_de("moa") == "moa"
    assert base_de("palma-soriano") == "palmasoriano"
    # Y no se cuelan dentro de Holguín ni de Santiago.
    assert base_de("holguin") != "moa"
    assert base_de("santiago-de-cuba") != "palmasoriano"


def test_las_tunas_existe():
    # Llevaba meses vendiendo sin estar dada de alta en analitics.
    assert base_de("las-tunas") == "tunas"


def test_una_sucursal_desconocida_no_se_inventa_una_base():
    # None, no la base más parecida: es un aviso de que falta decidir de dónde lee.
    assert base_de("sucursal-nueva") is None
    assert base_de("") is None


def test_ninguna_base_se_reparte_entre_dos_sucursales():
    bases = list(BASE_POR_SUCURSAL.values())

    assert len(bases) == len(set(bases)), "una base en dos sucursales duplicaría ventas"


@pytest.mark.parametrize("sid,base", sorted(BASE_POR_SUCURSAL.items()))
def test_la_vuelta_es_la_misma(sid, base):
    assert sucursal_de(base) == sid
