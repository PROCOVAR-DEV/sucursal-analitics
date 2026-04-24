"""Servicio de Productos: CES vs PROCOVAR y cumplimiento de metas mensuales."""
from __future__ import annotations

import calendar
from datetime import date

import pandas as pd

from core.constants import GESTORES_PERMITIDOS, METAS_PRODUCTOS_CES
from services.loader import STD_COLS, ReportData, only_valid_gestores


def _build_resumen(df_src: pd.DataFrame) -> list[dict]:
    if df_src.empty or STD_COLS["merc"] not in df_src.columns:
        return []
    imp = STD_COLS["importe"]
    cant = STD_COLS["cant"]
    r = df_src.groupby(df_src[STD_COLS["merc"]].astype(str).str.strip()).agg({
        imp: "sum",
        cant: "sum",
    }).reset_index()
    r.columns = ["producto", "total", "cantidad"]
    r["total"] = r["total"].round(2)
    r = r[r["total"] != 0].sort_values("total", ascending=False)
    return r.to_dict(orient="records")


def compute_productos(report: ReportData, trabaja_sabado: bool = False) -> dict:
    """Calcula resumen CES/PROCOVAR, por gestor y cumplimiento vs meta mensual."""
    df = only_valid_gestores(report.df).copy()

    # Separar CES (general) y PROCOVAR (cervezas / parranda)
    if STD_COLS["grupo"] in df.columns:
        mask_proc = (
            df[STD_COLS["grupo"]].astype(str).str.contains("PROCOVAR|PARRANDA", case=False, na=False)
            | df["IsParranda"]
        )
    else:
        mask_proc = df["IsParranda"]

    ces = df[~mask_proc].copy()
    procovar = df[mask_proc].copy()

    # Días laborales (lun-vie o lun-sáb) basados en rango del reporte
    dias_trans = dias_totales = dias_rest = 1
    if report.date_min is not None and report.date_max is not None:
        weekmask = "1111100" if not trabaja_sabado else "1111110"
        start = report.date_min.date().replace(day=1)
        end = report.date_max.date()
        last_day = date(end.year, end.month, calendar.monthrange(end.year, end.month)[1])
        dias_totales = max(1, len(pd.bdate_range(start=start, end=last_day, freq="C", weekmask=weekmask)))
        dias_trans = max(1, len(pd.bdate_range(start=start, end=end, freq="C", weekmask=weekmask)))
        dias_rest = max(1, dias_totales - dias_trans)

    # Cumplimiento de metas por producto CES (se matchea por substring)
    cumplimiento: list[dict] = []
    qcol = STD_COLS["cant"]
    for producto, meta in METAS_PRODUCTOS_CES.items():
        if STD_COLS["merc"] not in ces.columns or qcol not in ces.columns:
            real = 0.0
        else:
            mask = ces[STD_COLS["merc"]].astype(str).str.contains(producto, case=False, na=False)
            real = float(ces.loc[mask, qcol].sum())
        real = round(real, 2)
        deberia = round((meta / dias_totales) * dias_trans, 2)
        delta = round(real - deberia, 2)
        cumplimiento.append({
            "producto": producto,
            "meta": meta,
            "real": real,
            "cumplimiento_pct": round((real / meta * 100) if meta else 0.0, 2),
            "deberia": deberia,
            "delta": delta,
            "prom_diario": round(real / dias_trans, 2),
            "necesario_por_dia": round(max(0.0, (meta - real) / dias_rest), 2),
            "estado": "ok" if delta >= 0 else ("alerta" if real >= 0.8 * deberia else "critico"),
        })

    # Resumen por gestor
    por_gestor: list[dict] = []
    for g in GESTORES_PERMITIDOS:
        por_gestor.append({
            "gestor": g,
            "ces": _build_resumen(ces[ces["GestorDetectado"] == g]),
            "procovar": _build_resumen(procovar[procovar["GestorDetectado"] == g]),
        })

    return {
        "rango": report.rango_str,
        "dias_laborales_totales": dias_totales,
        "dias_laborales_transcurridos": dias_trans,
        "dias_laborales_restantes": dias_rest,
        "resumen_ces": _build_resumen(ces),
        "resumen_procovar": _build_resumen(procovar),
        "cumplimiento": cumplimiento,
        "por_gestor": por_gestor,
    }
