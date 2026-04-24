"""Servicio Clientes Punto: clientes identificados con '!!' en la Nota."""
from __future__ import annotations

import pandas as pd

from core.constants import GESTORES_PERMITIDOS
from services.loader import STD_COLS, ReportData


def compute_clientes_punto(report: ReportData) -> dict:
    df = report.df
    punto = df[df["GestorPunto"].notna()].copy()

    imp = STD_COLS["importe"]
    socio = STD_COLS["socio"]
    fec = STD_COLS["fecha"]

    # Ordenar
    if fec in punto.columns:
        punto = punto.sort_values(by=[fec])

    # Filas (para tabla)
    cols_out = [c for c in [STD_COLS["op"], fec, socio, STD_COLS["merc"], STD_COLS["grupo"],
                            STD_COLS["cant"], imp, STD_COLS["suma"], STD_COLS["nota"]]
                if c in punto.columns]
    tabla = punto[cols_out].copy()
    tabla["Gestor"] = punto["GestorPunto"].values
    if fec in tabla.columns:
        tabla[fec] = tabla[fec].dt.strftime("%Y-%m-%d")

    # Resumen por gestor
    resumen = []
    grand = 0.0
    for g in GESTORES_PERMITIDOS:
        sub = punto[punto["GestorPunto"] == g]
        total = round(float(sub[imp].sum()) if imp in sub.columns else 0.0, 2)
        grand += total
        resumen.append({
            "gestor": g,
            "operaciones": int(len(sub)),
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
