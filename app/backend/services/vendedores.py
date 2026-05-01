"""Servicio de resumen completo por vendedor (todos los productos)."""
from __future__ import annotations

import pandas as pd

from core.constants import GESTORES_CONFIG, GESTORES_PERMITIDOS
from services.loader import STD_COLS, ReportData, only_valid_gestores
from services.settings_store import config_for_report


def _sum_hl(sub: pd.DataFrame, mask: pd.Series, size: str) -> float:
    return round(float(sub.loc[mask & (sub["Size"] == size), "Hectolitros"].sum()), 2)


def compute_vendedores(report: ReportData, config: dict | None = None) -> dict:
    """Resumen por vendedor: todos los productos + desglose HL Malta/Parranda."""
    eff = config_for_report(config or {}, report)
    gestores_cfg = eff["gestores"]

    df_all = only_valid_gestores(report.df)
    df_mp = df_all[df_all["IsMalta"] | df_all["IsParranda"]].copy()

    vendedores_out: list[dict] = []

    for g in GESTORES_PERMITIDOS:
        sub_all = df_all[df_all["GestorDetectado"] == g]
        sub_mp = df_mp[df_mp["GestorDetectado"] == g]

        base_cfg = GESTORES_CONFIG[g]
        g_cfg = {**base_cfg, **(gestores_cfg.get(g) or {})}

        # Totales sobre TODOS los productos
        total_importe = round(
            float(sub_all[STD_COLS["importe"]].sum()) if STD_COLS["importe"] in sub_all.columns else 0.0, 2
        )
        num_ops = (
            int(sub_all[STD_COLS["op"]].nunique())
            if STD_COLS["op"] in sub_all.columns and not sub_all.empty
            else int(len(sub_all))
        )
        num_clientes = (
            int(sub_all[STD_COLS["socio"]].nunique())
            if STD_COLS["socio"] in sub_all.columns and not sub_all.empty
            else 0
        )

        # HL Malta / Parranda
        M330  = _sum_hl(sub_mp, sub_mp["IsMalta"],    "330")
        M500  = _sum_hl(sub_mp, sub_mp["IsMalta"],    "500")
        M1500 = _sum_hl(sub_mp, sub_mp["IsMalta"],    "1500")
        P330  = _sum_hl(sub_mp, sub_mp["IsParranda"], "330")
        P500  = _sum_hl(sub_mp, sub_mp["IsParranda"], "500")
        P1500 = _sum_hl(sub_mp, sub_mp["IsParranda"], "1500")
        total_hl = round(M330 + M500 + M1500 + P330 + P500 + P1500, 2)

        cuota = float(g_cfg.get("cuota_hl", 0.0))
        cumplimiento = round((total_hl / cuota * 100) if cuota else 0.0, 2)

        # Top 10 productos por importe
        top_productos: list[dict] = []
        if (
            not sub_all.empty
            and STD_COLS["merc"] in sub_all.columns
            and STD_COLS["importe"] in sub_all.columns
        ):
            agg = (
                sub_all.groupby(STD_COLS["merc"])[STD_COLS["importe"]]
                .sum()
                .nlargest(10)
                .reset_index()
            )
            top_productos = [
                {
                    "producto": str(row[STD_COLS["merc"]]),
                    "total": round(float(row[STD_COLS["importe"]]), 2),
                }
                for _, row in agg.iterrows()
            ]

        vendedores_out.append({
            "gestor":           g,
            "nombre":           g_cfg.get("nombre", g),
            "sector":           g_cfg.get("sector", ""),
            "total_importe":    total_importe,
            "num_operaciones":  num_ops,
            "num_clientes":     num_clientes,
            "total_hectolitros": total_hl,
            "cuota_hl":         cuota,
            "cumplimiento_pct": cumplimiento,
            "malta_330":        M330,
            "malta_500":        M500,
            "malta_1500":       M1500,
            "parranda_330":     P330,
            "parranda_500":     P500,
            "parranda_1500":    P1500,
            "top_productos":    top_productos,
        })

    return {
        "rango":             report.rango_str,
        "vendedores":        vendedores_out,
        "total_importe":     round(sum(v["total_importe"]    for v in vendedores_out), 2),
        "total_hectolitros": round(sum(v["total_hectolitros"] for v in vendedores_out), 2),
        "total_operaciones": sum(v["num_operaciones"] for v in vendedores_out),
    }
