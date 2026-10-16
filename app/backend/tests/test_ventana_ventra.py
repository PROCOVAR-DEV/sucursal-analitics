"""La ventana del repaso de Ventra y la hora del cierre (sin base de datos)."""
from datetime import date, datetime

from services.ventana_ventra import desde_del_repaso, dias_del_repaso, toca_cierre


def test_a_mitad_de_mes_el_repaso_llega_al_dia_uno():
    assert desde_del_repaso(date(2026, 10, 16)) == date(2026, 10, 1)
    assert dias_del_repaso(date(2026, 10, 16)) == 15   # el 01/10 queda dentro: es el caso de Holguín


def test_los_primeros_dias_incluye_el_mes_anterior_entero():
    assert desde_del_repaso(date(2026, 10, 3)) == date(2026, 9, 1)
    assert desde_del_repaso(date(2026, 10, 7)) == date(2026, 9, 1)
    assert desde_del_repaso(date(2026, 10, 8)) == date(2026, 10, 1)


def test_enero_mira_diciembre_del_año_anterior():
    assert desde_del_repaso(date(2027, 1, 2)) == date(2026, 12, 1)


def test_el_cierre_toca_pasadas_las_18_30_y_una_sola_vez_al_dia():
    hoy = date(2026, 10, 16)
    assert not toca_cierre(datetime(2026, 10, 16, 18, 29), None)
    assert toca_cierre(datetime(2026, 10, 16, 18, 30), None)
    assert toca_cierre(datetime(2026, 10, 16, 23, 59), date(2026, 10, 15))
    assert not toca_cierre(datetime(2026, 10, 16, 19, 0), hoy)       # ya se hizo hoy
    assert toca_cierre(datetime(2026, 10, 17, 18, 30), hoy)           # y mañana vuelve a tocar
    assert not toca_cierre(datetime(2026, 10, 17, 9, 0), hoy)
