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
