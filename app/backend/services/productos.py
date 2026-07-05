"""Servicio de Productos: cumplimiento de metas CES + resumen por grupo comercial."""
from __future__ import annotations

import calendar
from datetime import date

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS


def _resumen(df_src: pd.DataFrame) -> list[dict]:
    if df_src is None or df_src.empty or STD_COLS["merc"] not in df_src.columns:
        return []
    imp, cant = STD_COLS["importe"], STD_COLS["cant"]
    r = df_src.groupby(df_src[STD_COLS["merc"]].astype(str).str.strip()).agg(
        {imp: "sum", cant: "sum"}
    ).reset_index()
    r.columns = ["producto", "total", "cantidad"]
    r["total"] = r["total"].round(2)
    r = r[r["total"] != 0].sort_values("total", ascending=False)
    return r.to_dict(orient="records")


def dias_laborales(report, eff: dict) -> tuple[int, int, int]:
    trabaja_sabado = bool(eff.get("trabaja_sabado", False))
    trabaja_domingo = bool(eff.get("trabaja_domingo", False))
    if report is None or report.date_min is None or report.date_max is None:
        return 1, 1, 1
    wm = list("1111100")
    if trabaja_sabado:
        wm[5] = "1"
    if trabaja_domingo:
        wm[6] = "1"
    weekmask = "".join(wm)
    start = report.date_min.date().replace(day=1)
    end = report.date_max.date()
    last_day = date(end.year, end.month, calendar.monthrange(end.year, end.month)[1])
    totales = max(1, len(pd.bdate_range(start=start, end=last_day, freq="C", weekmask=weekmask)))
    trans = max(1, len(pd.bdate_range(start=start, end=end, freq="C", weekmask=weekmask)))
    rest = max(1, totales - trans)
    return totales, trans, rest


def compute_productos(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    metas = eff.get("metas_productos_ces") or {}
    groups_order = eff.get("groups_order") or []
    groups_kw = eff.get("product_groups_keywords") or {}

    def _grupo_de_producto(nombre: str) -> str:
        """Deduce el grupo de un producto por sus palabras clave (sin depender de ventas)."""
        t = str(nombre).upper()
        for grp in groups_order or groups_kw.keys():
            for kw in groups_kw.get(grp, []):
                if str(kw).upper() in t or t in str(kw).upper():
                    return grp
        return ""

    df = enrich_for_sucursal(report, eff)
    df = only_valid(df, keys)

    # CES = todo lo que NO es PARRANDA (importaciones + otros)
    if not df.empty:
        mask_parr = df["GrupoComercial"].astype(str) == "PARRANDA"
        ces = df[~mask_parr].copy()
        procovar = df[mask_parr].copy()
    else:
        ces = procovar = df

    dias_totales, dias_trans, dias_rest = dias_laborales(report, eff)

    # Cumplimiento de metas por producto: se busca en TODOS los grupos (no solo CES),
    # y se etiqueta el grupo al que pertenece cada producto con meta.
    cumplimiento: list[dict] = []
    qcol, merc = STD_COLS["cant"], STD_COLS["merc"]
    for producto, meta in metas.items():
        meta = float(meta)
        grupo = ""
        if df is None or df.empty or merc not in df.columns or qcol not in df.columns:
            real = 0.0
        else:
            mask = df[merc].astype(str).str.contains(producto, case=False, na=False)
            real = float(df.loc[mask, qcol].sum())
            if mask.any() and "GrupoComercial" in df.columns:
                grupos_match = df.loc[mask, "GrupoComercial"].astype(str)
                if not grupos_match.empty:
                    grupo = grupos_match.mode().iloc[0]
        if not grupo:
            grupo = _grupo_de_producto(producto)
        real = round(real, 2)
        deberia = round((meta / dias_totales) * dias_trans, 2)
        delta = round(real - deberia, 2)
        cumplimiento.append({
            "producto": producto, "grupo": grupo, "meta": meta, "real": real,
            "cumplimiento_pct": round((real / meta * 100) if meta else 0.0, 2),
            "deberia": deberia, "delta": delta,
            "prom_diario": round(real / dias_trans, 2),
            "necesario_por_dia": round(max(0.0, (meta - real) / dias_rest), 2),
            "estado": "ok" if delta >= 0 else ("alerta" if real >= 0.8 * deberia else "critico"),
        })

    # Resumen por grupo (para hoja Resumen y hojas por gestor)
    resumen_por_grupo: dict[str, list[dict]] = {}
    if not df.empty:
        for grp in groups_order:
            resumen_por_grupo[grp] = _resumen(df[df["GrupoComercial"].astype(str) == grp])

    por_gestor: list[dict] = []
    for g in keys:
        sub = df[df["GestorDetectado"] == g] if not df.empty else df
        grupos_g = {}
        if not df.empty:
            for grp in groups_order:
                grupos_g[grp] = _resumen(sub[sub["GrupoComercial"].astype(str) == grp])
        por_gestor.append({"gestor": g, "grupos": grupos_g})

    return {
        "rango": report.rango_str, "periodo": eff.get("_period"),
        "dias_laborales_totales": dias_totales,
        "dias_laborales_transcurridos": dias_trans,
        "dias_laborales_restantes": dias_rest,
        "resumen_ces": _resumen(ces), "resumen_procovar": _resumen(procovar),
        "resumen_por_grupo": resumen_por_grupo,
        "groups_order": groups_order,
        "cumplimiento": cumplimiento, "por_gestor": por_gestor,
    }
