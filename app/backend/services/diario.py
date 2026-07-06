"""Servicio Diario: meta diaria vs. real por día, con comparación contra el día
anterior (incluye el último día del mes previo). Global o por vendedor."""
from __future__ import annotations

import calendar

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS


def _pct(n, d):
    return round((n / d * 100), 2) if d else 0.0


def _working_days(year: int, month: int, eff: dict) -> int:
    wm = list("1111100")
    if eff.get("trabaja_sabado"):
        wm[5] = "1"
    if eff.get("trabaja_domingo"):
        wm[6] = "1"
    last = calendar.monthrange(year, month)[1]
    rng = pd.bdate_range(start=f"{year}-{month:02d}-01", end=f"{year}-{month:02d}-{last:02d}", freq="C", weekmask="".join(wm))
    return max(1, len(rng))


def compute_diario(report, eff: dict, mes: str | None = None, gestor: str | None = None) -> dict:
    keys = gestor_keys(eff)
    df = only_valid(enrich_for_sucursal(report, eff), keys)
    imp, fec, socio = STD_COLS["importe"], STD_COLS["fecha"], STD_COLS["socio"]
    if gestor:
        df = df[df["GestorDetectado"].astype(str).str.upper() == str(gestor).upper()].copy()

    # Mes objetivo (del estudio): el indicado, o el del último día con datos.
    if not df.empty and fec in df.columns:
        df = df.dropna(subset=[fec]).copy()
    if mes:
        y, m = int(mes[:4]), int(mes[5:7])
    elif not df.empty:
        d = df[fec].max()
        y, m = d.year, d.month
    else:
        y = m = None

    dias_totales = _working_days(y, m, eff) if y else 1
    if gestor:
        gcfg = (eff.get("gestores") or {}).get(str(gestor).upper()) or {}
        meta_hl_total = float(gcfg.get("cuota_hl", 0.0))
    else:
        meta_hl_total = float(eff.get("meta_hectolitros_total") or 0.0)
    meta_dia_hl = round(meta_hl_total / dias_totales, 2) if dias_totales else 0.0

    empty = {
        "rango": report.rango_str, "periodo": mes, "gestor": gestor, "vendedores": keys,
        "dias": [], "meta_dia_hl": meta_dia_hl, "meta_hl_total": meta_hl_total,
        "dias_laborales_totales": dias_totales,
        "totales": {"importe": 0.0, "hectolitros": 0.0, "operaciones": 0, "dias": 0},
        "mejor_dia": None, "promedio_dia_importe": 0.0,
    }
    if df.empty or fec not in df.columns:
        return empty

    df["__dia__"] = df[fec].dt.normalize()
    hl_col = "Hectolitros" if "Hectolitros" in df.columns else None

    # Serie de TODOS los días (para el Δ vs día anterior, incluye el mes previo).
    all_days = {}
    for dia, sub in df.groupby("__dia__"):
        all_days[pd.Timestamp(dia)] = round(float(sub[hl_col].sum()) if hl_col else 0.0, 2)
    ordered = sorted(all_days.keys())
    prev_of = {d: (ordered[i - 1] if i > 0 else None) for i, d in enumerate(ordered)}

    dias_out = []
    for dia in ordered:
        ts = pd.Timestamp(dia)
        if y and (ts.year != y or ts.month != m):
            continue  # solo el mes objetivo en la salida
        sub = df[df["__dia__"] == dia]
        importe = round(float(sub[imp].sum()) if imp in sub.columns else 0.0, 2)
        hl = all_days[dia]
        ops = int(len(sub))
        clientes = int(sub[socio].nunique()) if socio in sub.columns else ops
        pd_ = prev_of[dia]
        vs_ant = None if pd_ is None else round(hl - all_days[pd_], 2)
        delta_meta = round(hl - meta_dia_hl, 2)
        dias_out.append({
            "fecha": ts.strftime("%Y-%m-%d"), "dia_semana": _dow_es(ts),
            "importe": importe, "hectolitros": hl, "operaciones": ops, "clientes": clientes,
            "meta_hl": meta_dia_hl, "delta_meta_hl": delta_meta, "cumplimiento_pct": _pct(hl, meta_dia_hl),
            "vs_anterior_hl": vs_ant, "fecha_anterior": pd_.strftime("%Y-%m-%d") if pd_ is not None else None,
            "estado": "ok" if delta_meta >= 0 else ("alerta" if hl >= 0.8 * meta_dia_hl else "critico"),
        })

    tot_imp = round(sum(d["importe"] for d in dias_out), 2)
    tot_hl = round(sum(d["hectolitros"] for d in dias_out), 2)
    tot_ops = int(sum(d["operaciones"] for d in dias_out))
    ndias = len(dias_out)
    mejor = max(dias_out, key=lambda d: d["importe"]) if dias_out else None

    return {
        "rango": report.rango_str, "periodo": mes, "gestor": gestor, "vendedores": keys,
        "dias": dias_out, "meta_dia_hl": meta_dia_hl, "meta_hl_total": meta_hl_total,
        "dias_laborales_totales": dias_totales,
        "totales": {"importe": tot_imp, "hectolitros": tot_hl, "operaciones": tot_ops, "dias": ndias},
        "mejor_dia": mejor, "promedio_dia_importe": round(tot_imp / ndias, 2) if ndias else 0.0,
    }


_DOW = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _dow_es(ts: pd.Timestamp) -> str:
    return _DOW[int(ts.dayofweek)]
