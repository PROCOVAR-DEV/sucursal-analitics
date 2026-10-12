"""Lo que Ventra anula tiene que salir también de la copia de analitics.

12/10/2026: contra el reporte de septiembre de Ventra, Santiago daba 734,50 de más y Granma
1.138,00. `guardar` solo escribía: las líneas anuladas en Ventra se quedaban para siempre.
"""
from services.ventra import lineas_a_retirar


def test_retira_lo_que_ventra_ya_no_tiene():
    assert lineas_a_retirar({1, 2, 3, 4}, {1, 2, 4}) == {3}


def test_no_retira_nada_si_todo_sigue_en_ventra():
    assert lineas_a_retirar({1, 2, 3}, {1, 2, 3, 99}) == set()


def test_ventra_sin_ninguna_linea_es_una_caida_no_una_anulacion_masiva():
    assert lineas_a_retirar({1, 2, 3}, set()) == set()


def test_una_respuesta_recortada_no_borra_el_tramo():
    guardadas = set(range(1000))
    recortada = set(range(100))            # faltan 900: casi seguro un fallo de Ventra
    assert lineas_a_retirar(guardadas, recortada) == set()


def test_unas_pocas_anulaciones_en_un_tramo_grande_si_se_retiran():
    guardadas = set(range(4045))
    vivas = guardadas - set(range(12))     # el caso real de Santiago en septiembre
    assert lineas_a_retirar(guardadas, vivas) == set(range(12))


def test_la_pasada_diaria_cubre_el_mes_y_el_anterior_los_primeros_dias():
    from datetime import date
    from services.ventra import tramos_del_mes

    assert tramos_del_mes(date(2026, 10, 12)) == [(date(2026, 10, 1), date(2026, 10, 12))]
    assert tramos_del_mes(date(2026, 10, 3)) == [
        (date(2026, 9, 1), date(2026, 9, 30)), (date(2026, 10, 1), date(2026, 10, 3))]
    assert tramos_del_mes(date(2026, 1, 2))[0] == (date(2025, 12, 1), date(2025, 12, 31))
    assert len(tramos_del_mes(date(2026, 10, 6))) == 1
