"""Cumplimiento por vendedor y general, por FORMATO (P1500/P500/P330/M1500/M330),
replicando las tablas del algoritmo por gestor: resumen mensual (acumulado) y
resumen diario (meta día vs venta día). Sirve para sacar y seguir metas diarias."""
from __future__ import annotations

import calendar

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS

# Orden de formatos como el reporte (incluye M500).
DEFAULT_FORMATOS = ["P1500", "P500", "P330", "M1500", "M500", "M330"]


def _fmt_code(producto: str, size) -> str | None:
    if size is None or str(size) == "nan" or str(size) == "<NA>":
        return None
    t = str(producto).upper()
    if "PARRANDA" in t:
        pre = "P"
    elif "MALTA" in t or "GUAJIRA" in t:
        pre = "M"
    else:
        return None
    return f"{pre}{size}"


def _meta_code(code_key: str) -> str | None:
    """'PARRANDA-1500' -> 'P1500', 'MALTA-330' -> 'M330'."""
    idx = code_key.rfind("-")
    if idx < 0:
        return None
    prod, size = code_key[:idx].upper(), code_key[idx + 1:]
    if "PARRANDA" in prod:
        return f"P{size}"
    if "MALTA" in prod or "GUAJIRA" in prod:
        return f"M{size}"
    return None


def _pct(n, d):
    return round((n / d * 100), 2) if d else 0.0


def compute_metas_gestor(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    df = only_valid(enrich_for_sucursal(report, eff), keys)
    imp, fec, cant, merc = STD_COLS["importe"], STD_COLS["fecha"], STD_COLS["cant"], STD_COLS["merc"]
    gestores_cfg = eff.get("gestores") or {}
    comision_pct = float(eff.get("comision_gestor_pct", 0.01) or 0.0)

    # Siempre las 6 columnas estándar + cualquier formato extra en metas.
    formatos = list(DEFAULT_FORMATOS)
    for g in keys:
        for ck in (gestores_cfg.get(g) or {}).get("metas_formato", {}):
            mc = _meta_code(ck)
            if mc and mc not in formatos:
                formatos.append(mc)

    empty = {
        "rango": report.rango_str, "periodo": eff.get("_period"), "formatos": formatos,
        "report_date": None, "dias_mes": 0, "factor": 0.0,
        "por_gestor": [], "general": [], "total_general": None, "desglose_dia": {},
    }
    if df.empty or fec not in df.columns:
        return empty
    df = df.dropna(subset=[fec]).copy()
    if df.empty:
        return empty

    report_date = df[fec].max().normalize()
    dias_mes = calendar.monthrange(report_date.year, report_date.month)[1]
    factor = round(report_date.day / dias_mes, 6)

    # Código de formato por fila; solo bebidas (Malta/Parranda), como el reporte.
    df["__code__"] = [_fmt_code(m, s) for m, s in zip(df[merc], df.get(STD_COLS["size"], pd.Series([None] * len(df), index=df.index)))]
    df = df[df["__code__"].isin(formatos)].copy()
    # El estudio es del ÚLTIMO día subido: se limita a su mes.
    df = df[(df[fec].dt.year == report_date.year) & (df[fec].dt.month == report_date.month)].copy()
    if df.empty:
        return {**empty, "report_date": report_date.strftime("%Y-%m-%d"), "dias_mes": dias_mes, "factor": factor}
    month_mask = df[fec].dt.normalize() <= report_date
    day_mask = df[fec].dt.normalize() == report_date
    # Día anterior con datos (para la comparativa).
    prev_days = sorted(d for d in df[fec].dt.normalize().unique() if d < report_date)
    prev_date = prev_days[-1] if prev_days else None
    day_prev_mask = (df[fec].dt.normalize() == prev_date) if prev_date is not None else pd.Series(False, index=df.index)
    hl = "Hectolitros"

    def meta_de(g):
        mf = (gestores_cfg.get(g) or {}).get("metas_formato", {}) or {}
        out = {f: 0.0 for f in formatos}
        for ck, val in mf.items():
            mc = _meta_code(ck)
            if mc in out:
                out[mc] += float(val)
        return out

    por_gestor, general_rows = [], []
    for g in keys:
        sub = df[df["GestorDetectado"] == g]
        meta_total = meta_de(g)
        meta_total_tot = float((gestores_cfg.get(g) or {}).get("cuota_hl", 0.0)) or round(sum(meta_total.values()), 2)

        venta_acum = {f: round(float(sub.loc[month_mask & (sub["__code__"] == f), hl].sum()), 2) for f in formatos}
        venta_dia = {f: round(float(sub.loc[day_mask & (sub["__code__"] == f), hl].sum()), 2) for f in formatos}
        venta_ant = {f: round(float(sub.loc[day_prev_mask & (sub["__code__"] == f), hl].sum()), 2) for f in formatos}
        meta_acum = {f: round(meta_total[f] * factor, 2) for f in formatos}
        meta_dia = {f: round(meta_total[f] / dias_mes, 2) for f in formatos}

        va_tot = round(sum(venta_acum.values()), 2)
        vd_tot = round(sum(venta_dia.values()), 2)
        vant_tot = round(sum(venta_ant.values()), 2)
        ma_tot = round(meta_total_tot * factor, 2)
        md_tot = round(meta_total_tot / dias_mes, 2)

        def rowify(d, tot):
            return {**{f: d[f] for f in formatos}, "TOTAL": tot}

        mensual = {
            "meta_total": rowify(meta_total, round(meta_total_tot, 2)),
            "meta_acum": rowify(meta_acum, ma_tot),
            "venta_acum": rowify(venta_acum, va_tot),
            "venta_dia": rowify(venta_dia, vd_tot),
            "delta_acum": rowify({f: round(venta_acum[f] - meta_acum[f], 2) for f in formatos}, round(va_tot - ma_tot, 2)),
            "delta_acum_pct": rowify({f: _pct(venta_acum[f] - meta_acum[f], meta_acum[f]) for f in formatos}, _pct(va_tot - ma_tot, ma_tot)),
            "pct_total": rowify({f: _pct(venta_acum[f], meta_total[f]) for f in formatos}, _pct(va_tot, meta_total_tot)),
        }
        diario = {
            "meta_dia": rowify(meta_dia, md_tot),
            "venta_dia": rowify(venta_dia, vd_tot),
            "venta_dia_ant": rowify(venta_ant, vant_tot),
            "delta_vs_ant": rowify({f: round(venta_dia[f] - venta_ant[f], 2) for f in formatos}, round(vd_tot - vant_tot, 2)),
            "delta_dia": rowify({f: round(venta_dia[f] - meta_dia[f], 2) for f in formatos}, round(vd_tot - md_tot, 2)),
            "delta_dia_pct": rowify({f: _pct(venta_dia[f] - meta_dia[f], meta_dia[f]) for f in formatos}, _pct(vd_tot - md_tot, md_tot)),
            "cumpl_dia_pct": rowify({f: _pct(venta_dia[f], meta_dia[f]) for f in formatos}, _pct(vd_tot, md_tot)),
        }

        total_importe = round(float(sub[imp].sum()) if imp in sub.columns else 0.0, 2)
        total_hl = round(float(sub[hl].sum()), 2)
        total_blisters = round(float(sub[cant].sum()) if cant in sub.columns else 0.0, 2)
        total_pallets = round(float(sub["Pallets"].sum()) if "Pallets" in sub.columns else 0.0, 2)
        totales = {
            "total_importe": total_importe, "comision": round(total_importe * comision_pct, 2),
            "total_blisters": total_blisters, "total_pallets": total_pallets,
            "total_hl": total_hl, "meta_hl": round(meta_total_tot, 2),
            "delta_hl": round(total_hl - meta_total_tot, 2), "cumpl_hl_pct": _pct(total_hl, meta_total_tot),
        }
        por_gestor.append({
            "gestor": g, "nombre": (gestores_cfg.get(g) or {}).get("nombre", g),
            "mensual": mensual, "diario": diario, "totales": totales,
        })
        general_rows.append({
            "gestor": g, "total_importe": total_importe, "comision": totales["comision"],
            "total_blisters": total_blisters, "total_pallets": total_pallets, "total_hl": total_hl,
            "meta_hl": round(meta_total_tot, 2), "delta_hl": totales["delta_hl"], "cumpl_hl_pct": totales["cumpl_hl_pct"],
            "venta_acum": va_tot, "meta_acum": ma_tot, "cumpl_acum_pct": _pct(va_tot, ma_tot),
            "venta_dia": vd_tot, "meta_dia": md_tot, "cumpl_dia_pct": _pct(vd_tot, md_tot),
        })

    # TOTAL GENERAL
    def s(k):
        return round(sum(r[k] for r in general_rows), 2)
    total_general = None
    if general_rows:
        tg = {k: s(k) for k in ["total_importe", "comision", "total_blisters", "total_pallets", "total_hl", "meta_hl", "delta_hl", "venta_acum", "meta_acum", "venta_dia", "meta_dia"]}
        tg["gestor"] = "TOTAL GENERAL"
        tg["cumpl_hl_pct"] = _pct(tg["total_hl"], tg["meta_hl"])
        tg["cumpl_acum_pct"] = _pct(tg["venta_acum"], tg["meta_acum"])
        tg["cumpl_dia_pct"] = _pct(tg["venta_dia"], tg["meta_dia"])
        total_general = tg

    # Desglose del día por formato (todos los gestores)
    desglose_dia = {f: round(float(df.loc[day_mask & (df["__code__"] == f), hl].sum()), 2) for f in formatos}
    desglose_dia["TOTAL"] = round(sum(desglose_dia.values()), 2)

    return {
        "rango": report.rango_str, "periodo": eff.get("_period"), "formatos": formatos,
        "report_date": report_date.strftime("%Y-%m-%d"),
        "report_date_ant": prev_date.strftime("%Y-%m-%d") if prev_date is not None else None,
        "dias_mes": dias_mes, "factor": factor,
        "por_gestor": por_gestor, "general": general_rows, "total_general": total_general,
        "desglose_dia": desglose_dia,
    }
