"""Días LABORALES del mes (los de la calculadora de metas).

La meta de cada SKU se reparte entre los días que realmente se trabaja, no entre los del
calendario: julio 2026 tiene 31 días de calendario pero 23 laborales (lun-vie).

  meta_dia(sku)  = meta_mensual(sku) / dias_laborales_del_mes        (ej. /23, no /31)
  meta_acum(sku) = meta_dia(sku) * dias_laborales_transcurridos      (la meta "a la fecha")

Los sábados/domingos se cuentan solo si la sucursal los trabaja (config `eff`).
"""
from __future__ import annotations

import calendar

import pandas as pd


def weekmask(eff: dict) -> str:
    """Máscara de días trabajados (lun..dom). Por defecto lun-vie."""
    wm = list("1111100")
    if (eff or {}).get("trabaja_sabado"):
        wm[5] = "1"
    if (eff or {}).get("trabaja_domingo"):
        wm[6] = "1"
    return "".join(wm)


def working_days(year: int, month: int, eff: dict) -> int:
    """Días laborales TOTALES del mes (entre los que se reparte la meta mensual)."""
    last = calendar.monthrange(year, month)[1]
    rng = pd.bdate_range(
        start=f"{year}-{month:02d}-01",
        end=f"{year}-{month:02d}-{last:02d}",
        freq="C",
        weekmask=weekmask(eff),
    )
    return max(1, len(rng))


def working_days_elapsed(report_date, eff: dict) -> int:
    """Días laborales TRANSCURRIDOS del mes hasta `report_date` (inclusive)."""
    start = pd.Timestamp(report_date).replace(day=1)
    rng = pd.bdate_range(start=start, end=pd.Timestamp(report_date), freq="C", weekmask=weekmask(eff))
    return max(1, len(rng))


def working_days_left(report_date, eff: dict) -> int:
    """Días laborales que QUEDAN del mes, contando el día de corte si se trabaja ese día.

    Es entre los que hay que repartir lo que falta del plan: a 13/10/2026 (martes) quedan 14
    —hoy y los del 14 al 30—, no los 22 del mes. Mínimo 1: pasado el último día laborable no
    se puede dividir entre cero y lo que falta se enseña entero.
    """
    d = pd.Timestamp(report_date)
    hoy_laboral = weekmask(eff)[d.weekday()] == "1"
    return max(1, working_days(d.year, d.month, eff) - working_days_elapsed(d, eff) + (1 if hoy_laboral else 0))


def meta_diaria_restante(meta_mes: float, vendido_antes_de_hoy: float, dias_que_quedan: int) -> float:
    """Lo que falta del plan del mes entre los días que quedan.

    Pedido de Sidney el 13/10/2026: «si quedan 10 días y tienes un plan de 400 pacas de
    azúcar, la meta diaria sea de 40». La meta del día de siempre (plan ÷ días del mes) no se
    ajusta: quien va atrasado seguía viendo la misma cifra. Lo vendido cuenta HASTA AYER;
    lo de hoy es lo que se compara contra esta meta, no lo que la mueve.
    """
    return round(max(0.0, float(meta_mes) - float(vendido_antes_de_hoy)) / max(1, int(dias_que_quedan)), 2)
