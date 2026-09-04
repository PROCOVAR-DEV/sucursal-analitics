"""Que leer de Ventra dé el MISMO número que el Excel que se subía a mano.

El caso de oro es Camagüey del 1 al 3 de julio de 2026, cotejado contra la hoja Supervisor
del Excel que generaron los scripts originales: `DEYANIRA ZALDIVAR LUGO` = 5.069,70. Las
líneas de abajo son las de verdad, copiadas de la respuesta de Ventra.
"""
from __future__ import annotations

import pandas as pd

from services import ventra
from services.loader import STD_COLS


def linea(**kw):
    """Una línea de Ventra con los valores por defecto que trae de verdad."""
    base = {
        "id": 1, "date": "2026-07-01T04:00:00.000Z", "branchName": "CAMAGUEY",
        "operType": 2, "operNumber": 14522, "quantity": 1, "priceOut": 10,
        "priceIn": 0, "discount": 0, "productCode": "ALIM0020",
        "productName": "QUESO GOUDA LITUANO BARRA", "customerCode": "5798",
        "customerName": "RAMÓN ARIAS FOLGOSO", "objectCode": "1",
        "objectName": "PV CAMAGUEY", "note": "P-PAP25-260701-1547; V-DEYANIRA ZALDIVAR LUGO; C-KIOSCO;",
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------- el tipo de punto

def test_reconoce_las_tres_familias():
    assert ventra.tipo_de_punto("PV CAMAGUEY") == ventra.PUNTO_VENTA
    assert ventra.tipo_de_punto("PV-TUNAS") == ventra.PUNTO_VENTA
    assert ventra.tipo_de_punto("TIENDA S-SPIRITUS") == ventra.PUNTO_VENTA
    assert ventra.tipo_de_punto("ALM CAMAGUEY") == ventra.ALMACEN
    assert ventra.tipo_de_punto("ALMACEN MOA") == ventra.ALMACEN
    assert ventra.tipo_de_punto("PTO MONEDERO") == ventra.MONEDERO
    assert ventra.tipo_de_punto("PTOS MONEDERO") == ventra.MONEDERO


def test_lo_que_no_se_sabe_NO_se_adivina():
    # AURORA, FLORIDA, HABANA HACENDADO y PUNTO J existen de verdad y nadie sabe qué son.
    # Meterlos en "punto de venta" porque suenan a tienda es inventarse un dato que
    # después alguien suma en un informe.
    for desconocido in ("AURORA", "FLORIDA", "HABANA HACENDADO", "PUNTO J"):
        assert ventra.tipo_de_punto(desconocido) == ventra.SIN_CLASIFICAR
    assert ventra.tipo_de_punto(None) == ventra.SIN_CLASIFICAR
    assert ventra.tipo_de_punto("") == ventra.SIN_CLASIFICAR


# ---------------------------------------------------------------- el vendedor

def test_el_vendedor_sale_SOLO_del_segmento_V():
    assert ventra._solo_segmento_v("P-X; V-MAYLEN REMÓN DÍAZ; C-KIOSCO;") == "MAYLEN REMÓN DÍAZ"
    assert ventra._solo_segmento_v("V-ADRIANA KARINA DEL TORO DERONCELE;") == "ADRIANA KARINA DEL TORO DERONCELE"


def test_sin_V_el_vendedor_queda_VACIO_aunque_la_nota_nombre_a_uno():
    # Éste es el fallo caro. El cliente se llama como un gestor, y la función vieja
    # (`extract_vendor_segment`) devuelve la nota entera cuando no hay `V-`, así que la
    # venta acababa atribuida a ALEXANDER sin que él la hiciera.
    assert ventra._solo_segmento_v("C-CONSUMO PROPIO (ALEXANDER);") == ""
    assert ventra._solo_segmento_v("TRABAJADOR") == ""
    assert ventra._solo_segmento_v(None) == ""


def test_se_cuenta_lo_que_no_tiene_vendedor():
    # En Palma Soriano y Moa esto es el 100 % de las líneas. Tiene que poder decirse.
    df = ventra.a_dataframe([
        linea(operNumber=1, quantity=2, priceOut=10),
        linea(operNumber=2, quantity=3, priceOut=10, note="C-ALGUIEN;"),
    ], base="camaguey")
    n, importe = ventra.sin_vendedor(df)
    assert n == 1
    assert importe == 30.0


# ---------------------------------------------------------------- el importe

def test_el_importe_descuenta():
    # El Excel traía el importe hecho; aquí se compone. El descuento se resta porque es lo
    # que de verdad se cobró: dejarlo fuera infla las ventas de quien más descuenta.
    assert ventra._importe({"quantity": 10, "priceOut": 5, "discount": 7}) == 43.0
    assert ventra._importe({"quantity": 2, "priceOut": 3.5, "discount": None}) == 7.0
    assert ventra._importe({}) == 0.0


def test_la_factura_14522_de_camaguey():
    """El caso real que destapó el error de 10.764,00 en los números de referencia."""
    df = ventra.a_dataframe([
        linea(operNumber=14522, quantity=1, priceOut=10764,
              note="P-PAP25-260701-1547; V-MAYLEN REMÓN DÍAZ; C-KIOSCO( RAMÓN ARIAS FOLGOSO);",
              objectName="ALM CAMAGUEY"),
    ], base="camaguey")

    assert float(df[STD_COLS["importe"]].iloc[0]) == 10764.0
    # Es de MAYLEN, no de quien aparezca dentro del `C-`.
    assert "MAYLEN" in df[STD_COLS["vseg"]].iloc[0]
    assert "RAMON" not in df[STD_COLS["vseg"]].iloc[0]
    assert df[ventra.COL_TIPO_PUNTO].iloc[0] == ventra.ALMACEN


# ---------------------------------------------------------------- la forma del dato

def test_deja_las_MISMAS_columnas_que_el_excel():
    # Si esto se rompe, el resto de la aplicación nota de dónde vinieron las filas — y ése
    # es justo el fallo que no se ve hasta que un informe da otro número.
    df = ventra.a_dataframe([linea()], base="camaguey")
    for c in ("op", "fecha", "socio", "merc", "grupo", "cant", "importe", "nota", "vseg"):
        assert STD_COLS[c] in df.columns


def test_solo_entran_las_ventas():
    # El día que Ventra devuelva devoluciones o traslados por el mismo endpoint, que se
    # queden fuera en vez de sumarse a las ventas sin que nadie lo note.
    df = ventra.a_dataframe([linea(operType=2), linea(operType=7), linea(operType=3)])
    assert len(df) == 1


def test_la_fecha_no_se_va_al_dia_anterior():
    # Ventra da la medianoche de Cuba en UTC. Comparando en UTC, una venta del día 1 se
    # lee como del 30 del mes anterior, y los informes de fin de mes no cuadran.
    df = ventra.a_dataframe([linea(date="2026-07-01T04:00:00.000Z")])
    assert df[STD_COLS["fecha"]].iloc[0] == pd.Timestamp("2026-07-01 00:00:00")


def test_sin_lineas_no_revienta():
    df = ventra.a_dataframe([], base="moa")
    assert df.empty
    assert ventra.sin_vendedor(df) == (0, 0.0)
