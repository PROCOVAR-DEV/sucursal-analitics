"""Servicio de Ranking: general, semanal y diario acumulado (por importe)."""
from __future__ import annotations

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS


def _week_label(ts: pd.Timestamp) -> str:
    monday = ts - pd.Timedelta(days=ts.dayofweek)
    friday = monday + pd.Timedelta(days=4)
    return f"{monday.strftime('%d/%m')} - {friday.strftime('%d/%m')}"


def _week_start(ts: pd.Timestamp) -> pd.Timestamp:
    return (ts - pd.Timedelta(days=ts.dayofweek)).normalize()


def compute_ranking(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    df = enrich_for_sucursal(report, eff)
    df = only_valid(df, keys)
    imp, fec = STD_COLS["importe"], STD_COLS["fecha"]

    if df.empty or fec not in df.columns or imp not in df.columns:
        return {"rango": report.rango_str, "general": [], "semanal": [], "diario": []}

    df = df.dropna(subset=[fec]).copy()
    df["__semana__"] = df[fec].apply(_week_label)
    df["__semana_start__"] = df[fec].apply(_week_start)

    general = (
        df.groupby("GestorDetectado")[imp].sum()
        .reindex(keys, fill_value=0.0).round(2)
        .sort_values(ascending=False).reset_index()
    )
    general.columns = ["vendedor", "ventas"]
    general.insert(0, "posicion", range(1, len(general) + 1))

    semanal = (
        df.groupby(["__semana_start__", "__semana__", "GestorDetectado"])[imp]
        .sum().round(2).reset_index()
    )
    semanal.columns = ["__sort__", "semana", "vendedor", "ventas"]
    if not semanal.empty:
        semanal["posicion"] = semanal.groupby("semana")["ventas"].rank(ascending=False, method="min").astype(int)
        semanal = semanal.sort_values(["__sort__", "posicion"]).drop(columns=["__sort__"])

    dias = sorted(df[fec].dt.normalize().unique())
    acum: list[dict] = []
    for d in dias:
        corte = df[df[fec].dt.normalize() <= d]
        tot = corte.groupby("GestorDetectado")[imp].sum().round(2)
        for g in keys:
            acum.append({"fecha": pd.Timestamp(d).strftime("%Y-%m-%d"), "vendedor": g,
                         "acumulado": round(float(tot.get(g, 0.0)), 2)})
    diario = pd.DataFrame(acum)
    if not diario.empty:
        diario["posicion"] = diario.groupby("fecha")["acumulado"].rank(ascending=False, method="min").astype(int)

    return {
        "rango": report.rango_str,
        "general": general.to_dict(orient="records"),
        "semanal": semanal.to_dict(orient="records"),
        "diario": diario.to_dict(orient="records") if not diario.empty else [],
    }
