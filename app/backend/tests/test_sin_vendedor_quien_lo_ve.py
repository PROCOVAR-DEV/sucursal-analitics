"""Lo facturado SIN VENDEDOR lo ve de supervisor para arriba, no el vendedor.

Jose, 02/10/2026: «los sin vendedor le salen a los vendedores; eso es una cosa que le
sale de supervisores para arriba, no a los vendedores».

Es un número de la OFICINA, no de nadie: una factura cuya nota no trae el segmento `V-`
no se le puede atribuir a ninguna persona. Está en el panel para que el total cuadre
contra el reporte de AXIS, y eso es trabajo de quien cuadra la sucursal. A un vendedor
le enseña un dinero que no es suyo, que no puede arreglar y que no sale en ninguna de
sus cuentas.
"""
from services.permisos import ve_sin_vendedor


def test_de_supervisor_para_arriba_si():
    assert ve_sin_vendedor("supervisor")
    assert ve_sin_vendedor("admin")
    assert ve_sin_vendedor("analitico")


def test_el_vendedor_no():
    assert not ve_sin_vendedor("gestor")


def test_un_rol_que_no_existe_todavia_NO_lo_ve():
    """El lado seguro: la lista dice quién SÍ. Un `!= "gestor"` escrito en el endpoint
    se lo enseñaría a cualquier rol nuevo sin que nadie lo decidiera."""
    assert not ve_sin_vendedor("vendedor")
    assert not ve_sin_vendedor("repartidor")
    assert not ve_sin_vendedor("")
    assert not ve_sin_vendedor(None)


def test_da_igual_como_venga_escrito():
    assert ve_sin_vendedor("SUPERVISOR")
    assert ve_sin_vendedor("  Supervisor  ")
    assert not ve_sin_vendedor("  GESTOR ")
