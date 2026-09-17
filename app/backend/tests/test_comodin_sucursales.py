"""
El comodin `*` solo es para admin y analitico.

No es una inyeccion —el `*` es una constante del propio programa— pero da MAS que
vista: `can_write_metas` llama a `can_access`, asi que un supervisor con comodin puede
escribirle las metas a las diez sucursales. El campo se teclea a mano en la pantalla de
usuarios y nada lo comprobaba.

Paso de verdad: `pedro`, supervisor de Santiago, tenia ["*", "santiago-de-cuba"].
"""
from services.permisos import sucursales_para


def test_un_supervisor_no_se_queda_con_el_comodin():
    assert sucursales_para("supervisor", ["*", "santiago-de-cuba"]) == ["santiago-de-cuba"]


def test_un_gestor_tampoco():
    assert sucursales_para("gestor", ["*"]) == []


def test_un_usuario_normal_tampoco():
    assert sucursales_para("usuario", ["habana", "*"]) == ["habana"]


def test_admin_y_analitico_SI_lo_llevan():
    assert sucursales_para("admin", []) == ["*"]
    assert sucursales_para("analitico", ["habana"]) == ["*"]


def test_con_espacios_alrededor_tambien_se_quita():
    # El campo se teclea a mano: " * " es lo mismo que "*".
    assert sucursales_para("supervisor", [" * ", "granma"]) == ["granma"]


def test_lo_que_no_es_comodin_se_respeta_tal_cual():
    assert sucursales_para("supervisor", ["granma", "moa"]) == ["granma", "moa"]


def test_una_lista_vacia_o_nula_no_revienta():
    assert sucursales_para("supervisor", None) == []
    assert sucursales_para("supervisor", []) == []
