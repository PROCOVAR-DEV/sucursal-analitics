"""
Lo que ve un vendedor cuando entra: SUS metas.

El 25/09/2026 Santiago mandó dos capturas de la misma fila. En la del supervisor,
ARROZ: meta 2.945, real 1.208, **41 %**. En la del vendedor, ARROZ: meta 2.945, real
82, **3 %**. La meta era la misma en las dos —la de la sucursal entera— y las ventas
no, porque al vendedor ya se le recortaban las filas a las suyas. Cada vendedor medía
lo que vende él contra lo que tiene que vender el equipo.

Aquí se prueba el recorte entero, que es puro y no toca la base.
"""
from services.permisos import recortar_a_gestor


def eff(**extra) -> dict:
    return {
        "gestores": {
            "GARI": {"nombre": "Gari", "cuota_hl": 420.0, "cuota_ccc": 100.0,
                     "metas_cantidad": {"AZUCAR PATEKO": 270.0, "VODKA": 30.0}},
            "DAYLA": {"nombre": "Dayla", "cuota_hl": 350.0, "cuota_ccc": 80.0,
                      "metas_cantidad": {"AZUCAR PATEKO": 350.0}},
        },
        "meta_hectolitros_total": 4559.0,
        "meta_ccc_total": 900.0,
        "meta_dinero_total": 250000.0,
        "metas_productos_ces": {"AZUCAR PATEKO": 2700.0, "ARROZ": 2945.0, "VODKA": 492.0},
        "groups_order": ["PARRANDA", "IMPORTACIONES"],
        **extra,
    }


def test_las_metas_por_producto_son_las_suyas():
    e = recortar_a_gestor(eff(), "GARI")

    assert e["metas_productos_ces"] == {"AZUCAR PATEKO": 270.0, "VODKA": 30.0}


def test_un_producto_sin_plan_suyo_no_sale():
    """Antes salía con los 2.945 de la sucursal, y su 82 daba un 3 % que no era suyo.
    Sin meta no hay cumplimiento: la fila se va, no se rellena con la del equipo."""
    e = recortar_a_gestor(eff(), "GARI")

    assert "ARROZ" not in e["metas_productos_ces"]


def test_un_cero_no_es_una_meta():
    c = eff()
    c["gestores"]["GARI"]["metas_cantidad"]["PAPEL HIGIENICO MANATI"] = 0.0

    assert "PAPEL HIGIENICO MANATI" not in recortar_a_gestor(c, "GARI")["metas_productos_ces"]


def test_los_hectolitros_son_su_cuota_y_no_la_de_la_sucursal():
    e = recortar_a_gestor(eff(), "DAYLA")

    assert e["meta_hectolitros_total"] == 350.0
    assert e["meta_ccc_total"] == 80.0


def test_solo_queda_su_ficha():
    e = recortar_a_gestor(eff(), "DAYLA")

    assert list(e["gestores"]) == ["DAYLA"]


def test_la_clave_casa_aunque_venga_con_espacios_o_en_minusculas():
    """El `gestor` del usuario lo teclea quien da de alta la cuenta."""
    e = recortar_a_gestor(eff(), " gari ")

    assert list(e["gestores"]) == ["GARI"]


def test_un_vendedor_sin_planes_se_queda_sin_metas_no_con_las_de_todos():
    c = eff()
    del c["gestores"]["GARI"]["metas_cantidad"]

    e = recortar_a_gestor(c, "GARI")

    assert e["metas_productos_ces"] == {}
    assert e["meta_hectolitros_total"] == 420.0


def test_un_gestor_que_no_esta_no_hereda_nada_de_la_sucursal():
    """Si el nombre está mal escrito, lo que sale es un vendedor vacío —no la sucursal
    entera, que es lo que vería si el recorte se limitara a filtrar filas."""
    e = recortar_a_gestor(eff(), "NADIE")

    assert e["gestores"] == {}
    assert e["metas_productos_ces"] == {}
    assert e["meta_hectolitros_total"] == 0.0


def test_lo_que_no_es_una_meta_suya_se_queda_como_estaba():
    """El dinero no tiene cuota por vendedor que poner en su lugar, y el resto de la
    configuración —grupos, parámetros— es de la sucursal y sigue siéndolo."""
    e = recortar_a_gestor(eff(), "GARI")

    assert e["meta_dinero_total"] == 250000.0
    assert e["groups_order"] == ["PARRANDA", "IMPORTACIONES"]


def test_una_meta_escrita_a_mano_que_no_es_un_numero_no_tumba_la_pantalla():
    c = eff()
    c["gestores"]["GARI"]["metas_cantidad"] = {"AZUCAR PATEKO": "270", "ARROZ": "no", "VODKA": None}

    assert recortar_a_gestor(c, "GARI")["metas_productos_ces"] == {"AZUCAR PATEKO": 270.0}
