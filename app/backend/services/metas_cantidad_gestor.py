"""El MISMO estudio que el de Parranda, pero para todo lo demás y en CANTIDAD.

`metas_gestor.py` contesta, por formato de cerveza y en hectolitros: cuánto lleva vendido
cada gestor en el mes contra la meta que le tocaría a estas alturas, y cuánto vendió hoy
contra su meta diaria y contra ayer. Eso es lo que se mira para saber cómo va alguien.

Del arroz, el papel o las baterías no se podía preguntar nada de eso: sus metas se ponen
por gestor en la calculadora (`metas_cantidad`) y sólo había un total contra un total. Este
módulo hace la misma cuenta con las mismas reglas, cambiando dos cosas:

  columnas   los PRODUCTOS con meta, en vez de los seis formatos
  unidad     la CANTIDAD vendida, en vez de los hectolitros

Todo lo demás se mantiene a propósito —los días laborales de la sucursal, el día de corte,
la comparación con el día anterior CON DATOS— para que las dos tablas se lean igual y una
no pueda decir una cosa y la de al lado otra.

La salida tiene la forma exacta que espera `VendorFormatoTables`: la tabla es la misma,
con otra unidad y otras columnas.
"""
from __future__ import annotations

import pandas as pd

from services.calendario import working_days, working_days_elapsed
from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS


def _pct(n, d):
    return round((n / d * 100), 2) if d else 0.0


def compute_metas_cantidad_gestor(report, eff: dict, dia: str | None = None) -> dict:
    """`dia` (YYYY-MM-DD): día de corte, igual que en el estudio de hectolitros."""
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    fec, cant, merc = STD_COLS["fecha"], STD_COLS["cant"], STD_COLS["merc"]

    # Las columnas son los productos con meta en ALGUNA persona, no en la que se está
    # mirando: así todos los gestores enseñan las mismas columnas y se pueden comparar. Sin
    # esto, cada uno tendría una tabla distinta y no se sabría si un hueco es un cero o es
    # que ese producto no le toca.
    productos: list[str] = []
    for g in keys:
        for prod in ((gestores_cfg.get(g) or {}).get("metas_cantidad") or {}):
            if prod not in productos:
                productos.append(prod)
    productos.sort()

    vacio = {
        "rango": report.rango_str, "periodo": eff.get("_period"), "formatos": productos,
        "report_date": None, "dias_mes": 0, "factor": 0.0,
        "por_gestor": [], "dias_disponibles": [], "dia_anterior": None,
    }

    if not productos:
        return vacio

    df = only_valid(enrich_for_sucursal(report, eff), keys)

    if df.empty or fec not in df.columns or merc not in df.columns:
        return vacio

    df = df.dropna(subset=[fec]).copy()

    if df.empty:
        return vacio

    report_date = df[fec].max().normalize()

    if dia:
        try:
            pedido = pd.Timestamp(dia).normalize()
            if pedido <= report_date:
                report_date = pedido
        except (ValueError, TypeError):
            pass

    dias_mes = working_days(report_date.year, report_date.month, eff)
    dias_corridos = working_days_elapsed(report_date, eff)
    factor = round(dias_corridos / dias_mes, 6) if dias_mes else 0.0

    # Sólo el mes del día de corte, como el estudio de hectolitros.
    df = df[(df[fec].dt.year == report_date.year) & (df[fec].dt.month == report_date.month)].copy()

    if df.empty:
        return {**vacio, "report_date": report_date.strftime("%Y-%m-%d"), "dias_mes": dias_mes, "factor": factor}

    # A qué producto con meta pertenece cada línea. Se cruza por NOMBRE con `contains`,
    # igual que el cumplimiento por producto de la sucursal: si aquí se cruzara distinto, el
    # mismo producto daría dos cifras según la pantalla que se abriera.
    nombres = df[merc].astype(str)
    pertenece = {p: nombres.str.contains(p, case=False, na=False) for p in productos}

    dias = sorted(df[fec].dt.normalize().unique())
    dias_disponibles = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in dias]
    anteriores = [d for d in dias if d < report_date]
    prev_date = anteriores[-1] if anteriores else None

    mes_mask = df[fec].dt.normalize() <= report_date
    dia_mask = df[fec].dt.normalize() == report_date
    ant_mask = (df[fec].dt.normalize() == prev_date) if prev_date is not None else pd.Series(False, index=df.index)
    cantidades = pd.to_numeric(df[cant], errors="coerce").fillna(0.0) if cant in df.columns else pd.Series(0.0, index=df.index)

    por_gestor = []

    for g in keys:
        suyo = df["GestorDetectado"] == g
        metas = (gestores_cfg.get(g) or {}).get("metas_cantidad") or {}

        def suma(mask_extra, p):
            return round(float(cantidades[suyo & mask_extra & pertenece[p]].sum()), 2)

        meta_total = {p: round(float(metas.get(p, 0.0)), 2) for p in productos}
        venta_acum = {p: suma(mes_mask, p) for p in productos}
        venta_dia = {p: suma(dia_mask, p) for p in productos}
        venta_ant = {p: suma(ant_mask, p) for p in productos}
        meta_acum = {p: round(meta_total[p] * factor, 2) for p in productos}
        meta_dia = {p: round(meta_total[p] / dias_mes, 2) if dias_mes else 0.0 for p in productos}

        def fila(d):
            return {**d, "TOTAL": round(sum(d.values()), 2)}

        mt, ma = fila(meta_total), fila(meta_acum)
        va, vd, vant, md = fila(venta_acum), fila(venta_dia), fila(venta_ant), fila(meta_dia)
        cols = productos + ["TOTAL"]

        por_gestor.append({
            "gestor": g,
            "nombre": (gestores_cfg.get(g) or {}).get("nombre", g),
            "mensual": {
                "meta_total": mt, "meta_acum": ma, "venta_acum": va, "venta_dia": vd,
                "delta_acum": {c: round(va[c] - ma[c], 2) for c in cols},
                "delta_acum_pct": {c: _pct(va[c] - ma[c], ma[c]) for c in cols},
                "pct_total": {c: _pct(va[c], mt[c]) for c in cols},
            },
            "diario": {
                "meta_dia": md, "venta_dia": vd, "venta_dia_ant": vant,
                "delta_vs_ant": {c: round(vd[c] - vant[c], 2) for c in cols},
                "delta_dia": {c: round(vd[c] - md[c], 2) for c in cols},
                "delta_dia_pct": {c: _pct(vd[c] - md[c], md[c]) for c in cols},
                "cumpl_dia_pct": {c: _pct(vd[c], md[c]) for c in cols},
            },
            "totales": {"meta_hl": mt["TOTAL"], "total_hl": va["TOTAL"]},
        })

    return {
        "rango": report.rango_str, "periodo": eff.get("_period"), "formatos": productos,
        "report_date": report_date.strftime("%Y-%m-%d"),
        "dias_mes": dias_mes, "factor": factor,
        "por_gestor": por_gestor,
        "dias_disponibles": dias_disponibles,
        "dia_anterior": pd.Timestamp(prev_date).strftime("%Y-%m-%d") if prev_date is not None else None,
    }
