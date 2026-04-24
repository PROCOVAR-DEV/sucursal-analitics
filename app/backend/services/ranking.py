"""Servicio de Ranking: general, semanal y diario acumulado."""
from __future__ import annotations

import pandas as pd

from core.constants import GESTORES_PERMITIDOS
from services.loader import STD_COLS, ReportData, only_valid_gestores


def _week_label(ts: pd.Timestamp) -> str:
    monday = ts - pd.Timedelta(days=ts.dayofweek)
    friday = monday + pd.Timedelta(days=4)
    return f"{monday.strftime('%d/%m')} - {friday.strftime('%d/%m')}"


def _week_start(ts: pd.Timestamp) -> pd.Timestamp:
    return (ts - pd.Timedelta(days=ts.dayofweek)).normalize()


def compute_ranking(report: ReportData) -> dict:
    df = only_valid_gestores(report.df).copy()
    imp = STD_COLS["importe"]
    fec = STD_COLS["fecha"]

    if fec not in df.columns or imp not in df.columns:
        return {"rango": report.rango_str, "general": [], "semanal": [], "diario": []}

    df = df.dropna(subset=[fec])
    df["__semana__"] = df[fec].apply(_week_label)
    df["__semana_start__"] = df[fec].apply(_week_start)

    # GENERAL
    general = (
        df.groupby("GestorDetectado")[imp].sum()
        .reindex(GESTORES_PERMITIDOS, fill_value=0.0)
        .round(2)
        .sort_values(ascending=False)
        .reset_index()
    )
    general.columns = ["vendedor", "ventas"]
    general.insert(0, "posicion", range(1, len(general) + 1))

    # SEMANAL
    semanal = (
        df.groupby(["__semana_start__", "__semana__", "GestorDetectado"])[imp]
        .sum().round(2).reset_index()
    )
    semanal.columns = ["__sort__", "semana", "vendedor", "ventas"]
    semanal["posicion"] = semanal.groupby("semana")["ventas"].rank(ascending=False, method="min").astype(int)
    semanal = semanal.sort_values(["__sort__", "posicion"]).drop(columns=["__sort__"])

    # DIARIO (acumulado progresivo)
    dias = sorted(df[fec].dt.normalize().unique())
    acum: list[dict] = []
    for d in dias:
        corte = df[df[fec].dt.normalize() <= d]
        tot = corte.groupby("GestorDetectado")[imp].sum().round(2)
        for g in GESTORES_PERMITIDOS:
            acum.append({
                "fecha": pd.Timestamp(d).strftime("%Y-%m-%d"),
                "vendedor": g,
                "acumulado": round(float(tot.get(g, 0.0)), 2),
            })
    diario = pd.DataFrame(acum)
    if not diario.empty:
        diario["posicion"] = diario.groupby("fecha")["acumulado"].rank(ascending=False, method="min").astype(int)

    return {
        "rango": report.rango_str,
        "general": general.to_dict(orient="records"),
        "semanal": semanal.to_dict(orient="records"),
        "diario": diario.to_dict(orient="records") if not diario.empty else [],
    }
