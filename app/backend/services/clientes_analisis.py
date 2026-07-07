"""Análisis de clientes por vendedor.

Para cada vendedor y para la oficina completa, rankea los clientes por volumen de
ventas en dólares (mayor → menor) y desglosa, en la misma fila, cuánto compró ese
cliente de cada SKU (mercancía). Permite ver el perfil de compra de cada cliente,
qué SKU escala más/menos, los clientes más valiosos y la cartera de cada gestor.
"""
from __future__ import annotations

import pandas as pd

from core.utils import normalize_text
from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS
from services.pedidos import fetch_order_counts

SIN_NOMBRE = "(sin nombre)"
SIN_SKU = "(sin producto)"


def _clean_text(series: pd.Series, fallback: str) -> pd.Series:
    s = series.astype("string").fillna(fallback).str.strip()
    return s.mask(s.eq("") | s.str.upper().eq("NAN") | s.eq("<NA>"), fallback)


def _pivot(sub: pd.DataFrame, imp: str, socio: str, merc: str, with_gestor: bool, pedidos_map: dict | None = None) -> dict:
    """Pivote clientes×SKU en dólares, ordenado por total de cliente (desc)."""
    empty = {"skus": [], "clientes": [], "total": 0.0, "num_clientes": 0, "num_skus": 0}
    if sub.empty or imp not in sub.columns or socio not in sub.columns or merc not in sub.columns:
        return empty
    sub = sub.copy()
    sub[socio] = _clean_text(sub[socio], SIN_NOMBRE)
    sub[merc] = _clean_text(sub[merc], SIN_SKU)
    sub[imp] = pd.to_numeric(sub[imp], errors="coerce").fillna(0.0)

    piv = sub.pivot_table(index=socio, columns=merc, values=imp, aggfunc="sum", fill_value=0.0)
    if piv.empty:
        return empty

    sku_tot = piv.sum(axis=0).sort_values(ascending=False)
    piv = piv[sku_tot.index]                       # columnas ordenadas por total desc
    cli_tot = piv.sum(axis=1).sort_values(ascending=False)

    dom_gestor: dict = {}
    if with_gestor and "GestorDetectado" in sub.columns:
        g_sum = sub.groupby([socio, "GestorDetectado"])[imp].sum()
        for cli in cli_tot.index:
            try:
                dom_gestor[cli] = str(g_sum.loc[cli].idxmax())
            except (KeyError, ValueError):
                dom_gestor[cli] = ""

    skus = [{"sku": str(s), "total": round(float(sku_tot[s]), 2)} for s in sku_tot.index]
    clientes = []
    for cli in cli_tot.index:
        row = piv.loc[cli]
        montos = {str(s): round(float(row[s]), 2) for s in sku_tot.index if float(row[s]) != 0.0}
        item = {
            "cliente": str(cli),
            "total": round(float(cli_tot[cli]), 2),
            "num_skus": int((row != 0).sum()),
            "pedidos": (pedidos_map or {}).get(normalize_text(str(cli)), 0),
            "sku_montos": montos,
        }
        if with_gestor:
            item["gestor"] = dom_gestor.get(cli, "")
        clientes.append(item)

    return {
        "skus": skus,
        "clientes": clientes,
        "total": round(float(cli_tot.sum()), 2),
        "num_clientes": int(len(cli_tot)),
        "num_skus": int(len(sku_tot)),
    }


def compute_clientes_analisis(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    df = only_valid(enrich_for_sucursal(report, eff), keys)
    imp, socio, merc = STD_COLS["importe"], STD_COLS["socio"], STD_COLS["merc"]

    # Cantidad de pedidos por cliente desde PEDIDO (best-effort; {} si no responde).
    pedidos_map = fetch_order_counts()

    gestores_cfg = eff.get("gestores") or {}
    por_gestor = []
    for g in keys:
        piv = _pivot(df[df["GestorDetectado"] == g], imp, socio, merc, with_gestor=False, pedidos_map=pedidos_map)
        por_gestor.append({
            "gestor": g,
            "nombre": (gestores_cfg.get(g) or {}).get("nombre", g),
            **piv,
        })

    return {
        "rango": report.rango_str,
        "periodo": eff.get("_period"),
        "oficina": _pivot(df, imp, socio, merc, with_gestor=True, pedidos_map=pedidos_map),
        "por_gestor": por_gestor,
    }
