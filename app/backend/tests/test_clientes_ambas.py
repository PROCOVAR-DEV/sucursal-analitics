"""
La fusion de importe y cantidad en una sola tabla.

Se prueba porque es facil que salga MAL SIN FALLAR: si un cliente aparece en un
pivote y no en el otro, o si el orden lo acaba decidiendo la cantidad, la tabla
sigue pintandose y nadie nota que esta ordenada por otra cosa. Lo pidio Claudia
para poder ver «de este vendi mucho dinero pero pocas cajas», que es justo lo que
se pierde si los dos numeros no son de la misma fila.
"""
from services.clientes_analisis import _fundir_ambas

IMPORTE = {
    "skus": [{"sku": "CERVEZA", "total": 900.0}, {"sku": "MALTA", "total": 100.0}],
    "clientes": [
        {"cliente": "A", "total": 700.0, "num_skus": 2, "pedidos": 3,
         "sku_montos": {"CERVEZA": 600.0, "MALTA": 100.0}},
        {"cliente": "B", "total": 300.0, "num_skus": 1, "pedidos": 1,
         "sku_montos": {"CERVEZA": 300.0}},
    ],
    "total": 1000.0, "num_clientes": 2, "num_skus": 2,
}
CANTIDAD = {
    "skus": [{"sku": "MALTA", "total": 50.0}, {"sku": "CERVEZA", "total": 30.0}],
    "clientes": [
        # OJO: en cantidad manda B, y el orden es el contrario. Es el caso que
        # importa: son dos rankings distintos.
        {"cliente": "B", "total": 60.0, "num_skus": 1, "pedidos": 1,
         "sku_montos": {"CERVEZA": 60.0}},
        {"cliente": "A", "total": 20.0, "num_skus": 2, "pedidos": 3,
         "sku_montos": {"CERVEZA": 10.0, "MALTA": 10.0}},
    ],
    "total": 80.0, "num_clientes": 2, "num_skus": 2,
}


def test_el_orden_lo_manda_el_importe():
    # En cantidad B va primero. La tabla dice "clientes rankeados por ventas", asi
    # que el importe manda y la cantidad acompaña.
    r = _fundir_ambas(IMPORTE, CANTIDAD)
    assert [c["cliente"] for c in r["clientes"]] == ["A", "B"]
    assert [s["sku"] for s in r["skus"]] == ["CERVEZA", "MALTA"]


def test_cada_cliente_lleva_SU_cantidad_no_la_de_la_misma_posicion():
    # El fallo que esto evita: cruzar por posicion en vez de por nombre, y pegarle
    # a A la cantidad de B. Los numeros seguirian saliendo y estarian cambiados.
    r = _fundir_ambas(IMPORTE, CANTIDAD)
    porNombre = {c["cliente"]: c for c in r["clientes"]}
    assert porNombre["A"]["total"] == 700.0 and porNombre["A"]["total_cantidad"] == 20.0
    assert porNombre["B"]["total"] == 300.0 and porNombre["B"]["total_cantidad"] == 60.0
    assert porNombre["A"]["sku_cantidades"] == {"CERVEZA": 10.0, "MALTA": 10.0}


def test_los_totales_por_sku_tambien_van_por_nombre():
    # En cantidad, MALTA va delante de CERVEZA. Si se cruzara por posicion, CERVEZA
    # se quedaria con las 50 de MALTA.
    r = _fundir_ambas(IMPORTE, CANTIDAD)
    porSku = {s["sku"]: s for s in r["skus"]}
    assert porSku["CERVEZA"]["total"] == 900.0 and porSku["CERVEZA"]["total_cantidad"] == 30.0
    assert porSku["MALTA"]["total"] == 100.0 and porSku["MALTA"]["total_cantidad"] == 50.0


def test_un_cliente_que_no_esta_en_cantidad_sale_con_cero_no_desaparece():
    solo_a = {**CANTIDAD, "clientes": [CANTIDAD["clientes"][1]]}
    r = _fundir_ambas(IMPORTE, solo_a)
    porNombre = {c["cliente"]: c for c in r["clientes"]}
    assert set(porNombre) == {"A", "B"}
    assert porNombre["B"]["total_cantidad"] == 0.0
    assert porNombre["B"]["sku_cantidades"] == {}


def test_el_total_de_cantidad_del_bloque_viaja():
    r = _fundir_ambas(IMPORTE, CANTIDAD)
    assert r["total"] == 1000.0
    assert r["total_cantidad"] == 80.0
