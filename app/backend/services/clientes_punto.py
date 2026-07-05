"""Servicio Clientes Punto: clientes identificados con '!!' en la Nota."""
from __future__ import annotations

from services.enrich import enrich_for_sucursal, gestor_keys
from services.loader import STD_COLS


def compute_clientes_punto(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    df = enrich_for_sucursal(report, eff)
    imp, socio, fec = STD_COLS["importe"], STD_COLS["socio"], STD_COLS["fecha"]

    if df.empty or "GestorPunto" not in df.columns:
        return {"rango": report.rango_str, "total_operaciones": 0, "total_clientes_unicos": 0,
                "total_importe": 0.0, "por_gestor": [], "filas": []}

    punto = df[df["GestorPunto"].notna()].copy()
    if fec in punto.columns:
        punto = punto.sort_values(by=[fec])

    cols_out = [c for c in [STD_COLS["op"], fec, socio, STD_COLS["merc"], STD_COLS["grupo"],
                            STD_COLS["cant"], imp, STD_COLS["suma"], STD_COLS["nota"]]
                if c in punto.columns]
    tabla = punto[cols_out].copy()
    tabla["Gestor"] = punto["GestorPunto"].values
    if fec in tabla.columns:
        tabla[fec] = tabla[fec].dt.strftime("%Y-%m-%d")

    resumen, grand = [], 0.0
    for g in keys:
        sub = punto[punto["GestorPunto"] == g]
        total = round(float(sub[imp].sum()) if imp in sub.columns else 0.0, 2)
        grand += total
        resumen.append({
            "gestor": g, "operaciones": int(len(sub)),
            "clientes_unicos": int(sub[socio].nunique()) if socio in sub.columns else int(len(sub)),
            "total_importe": total,
        })

    return {
        "rango": report.rango_str,
        "total_operaciones": int(len(punto)),
        "total_clientes_unicos": int(punto[socio].nunique()) if socio in punto.columns else int(len(punto)),
        "total_importe": round(grand, 2),
        "por_gestor": resumen,
        "filas": tabla.fillna("").to_dict(orient="records"),
    }
