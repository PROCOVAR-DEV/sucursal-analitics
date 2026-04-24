"""Servicio de Ventas / Supervisor (Hectolitros por MALTA y PARRANDA).

Produce totales por gestor, desglose por producto/tamaño, conversión a
blisters y pallets y KPIs de cumplimiento vs cuota.
"""
from __future__ import annotations

import pandas as pd

from core.constants import (
    GESTORES_CONFIG,
    GESTORES_PERMITIDOS,
    META_HECTOLITROS_TOTAL,
    UNITS_PER_PALLET,
)
from services.loader import STD_COLS, ReportData, only_valid_gestores


def _sum_hl(sub: pd.DataFrame, mask: pd.Series, size: str) -> float:
    return round(float(sub.loc[mask & (sub["Size"] == size), "Hectolitros"].sum()), 2)


def compute_ventas(report: ReportData) -> dict:
    """Calcula el resumen de ventas en hectolitros por gestor (MALTA / PARRANDA)."""
    df = only_valid_gestores(report.df)
    df = df[df["IsMalta"] | df["IsParranda"]].copy()

    gestores_out: list[dict] = []
    supervisor_rows: list[dict] = []

    for g in GESTORES_PERMITIDOS:
        sub = df[df["GestorDetectado"] == g]
        cfg = GESTORES_CONFIG[g]

        total_importe = round(float(sub[STD_COLS["importe"]].sum()) if STD_COLS["importe"] in sub.columns else 0.0, 2)
        M330  = _sum_hl(sub, sub["IsMalta"], "330")
        M500  = _sum_hl(sub, sub["IsMalta"], "500")
        M1500 = _sum_hl(sub, sub["IsMalta"], "1500")
        P330  = _sum_hl(sub, sub["IsParranda"], "330")
        P500  = _sum_hl(sub, sub["IsParranda"], "500")
        P1500 = _sum_hl(sub, sub["IsParranda"], "1500")
        total_hl = round(M330 + M500 + M1500 + P330 + P500 + P1500, 2)

        cuota = cfg["cuota_hl"]
        cumplimiento = round((total_hl / cuota * 100) if cuota else 0.0, 2)

        # Conversión blisters/pallets
        conv: list[dict] = []
        for prod, mask in (("MALTA", sub["IsMalta"]), ("PARRANDA", sub["IsParranda"])):
            for size in ("330", "500", "1500"):
                sel = sub[mask & (sub["Size"] == size)]
                if sel.empty:
                    continue
                blisters = float(sel[STD_COLS["cant"]].fillna(0).sum()) if STD_COLS["cant"] in sel.columns else 0.0
                units = UNITS_PER_PALLET.get((prod, size), 0)
                pallets = round(blisters / units, 2) if units else 0.0
                conv.append({
                    "producto": prod.capitalize(),
                    "tamano": size,
                    "blisters": round(blisters, 2),
                    "pallets": pallets,
                    "hectolitros": _sum_hl(sub, mask, size),
                })

        gestores_out.append({
            "gestor": g,
            "nombre": cfg["nombre"],
            "sector": cfg["sector"],
            "total_importe": total_importe,
            "total_hectolitros": total_hl,
            "cuota_hl": cuota,
            "cumplimiento_pct": cumplimiento,
            "malta_330": M330, "malta_500": M500, "malta_1500": M1500,
            "parranda_330": P330, "parranda_500": P500, "parranda_1500": P1500,
            "conversion": conv,
        })

        supervisor_rows.append({
            "Gestor": g,
            "Total Venta": total_importe,
            "M330": M330, "P330": P330, "P500": P500, "P1500": P1500,
            "Total Hectolitros": total_hl,
        })

    total_general_hl = round(sum(r["Total Hectolitros"] for r in supervisor_rows), 2)
    total_general_importe = round(sum(r["Total Venta"] for r in supervisor_rows), 2)

    return {
        "rango": report.rango_str,
        "meta_hectolitros": META_HECTOLITROS_TOTAL,
        "total_hectolitros": total_general_hl,
        "total_importe": total_general_importe,
        "cumplimiento_pct": round((total_general_hl / META_HECTOLITROS_TOTAL * 100) if META_HECTOLITROS_TOTAL else 0.0, 2),
        "gestores": gestores_out,
        "supervisor": supervisor_rows,
    }
