"""Servicio de resumen completo por vendedor (todos los productos)."""
from __future__ import annotations

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS


def _sum_hl(sub: pd.DataFrame, mask: pd.Series, size: str) -> float:
    if sub.empty:
        return 0.0
    return round(float(sub.loc[mask & (sub[STD_COLS["size"]] == size), "Hectolitros"].sum()), 2)


def compute_vendedores(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    com_gestor = float(eff.get("comision_gestor_pct", 0.01))
    desc_sin_pedido = float(eff.get("descuento_sin_pedido", 0.0))

    df_all = enrich_for_sucursal(report, eff)
    df_all = only_valid(df_all, keys)
    df_mp = df_all[df_all["IsMalta"] | df_all["IsParranda"]].copy() if not df_all.empty else df_all

    imp, op, socio, merc = STD_COLS["importe"], STD_COLS["op"], STD_COLS["socio"], STD_COLS["merc"]
    vendedores_out: list[dict] = []

    for g in keys:
        g_cfg = gestores_cfg.get(g, {})
        sub_all = df_all[df_all["GestorDetectado"] == g] if not df_all.empty else df_all
        sub_mp = df_mp[df_mp["GestorDetectado"] == g] if not df_mp.empty else df_mp

        total_importe = round(float(sub_all[imp].sum()) if imp in sub_all.columns and not sub_all.empty else 0.0, 2)
        num_ops = int(sub_all[op].nunique()) if op in sub_all.columns and not sub_all.empty else int(len(sub_all))
        num_clientes = int(sub_all[socio].nunique()) if socio in sub_all.columns and not sub_all.empty else 0

        M330, M500, M1500 = (_sum_hl(sub_mp, sub_mp["IsMalta"], s) for s in ("330", "500", "1500")) if not sub_mp.empty else (0.0, 0.0, 0.0)
        P330, P500, P1500 = (_sum_hl(sub_mp, sub_mp["IsParranda"], s) for s in ("330", "500", "1500")) if not sub_mp.empty else (0.0, 0.0, 0.0)
        total_hl = round(M330 + M500 + M1500 + P330 + P500 + P1500, 2)
        cuota = float(g_cfg.get("cuota_hl", 0.0))

        comision = round(total_importe * com_gestor, 2)
        sin_pedido = int(sub_all["SinPedido"].sum()) if ("SinPedido" in sub_all.columns and not sub_all.empty) else 0
        descuento = round(sin_pedido * desc_sin_pedido, 2)
        comision_neta = round(comision - descuento, 2)

        top_productos: list[dict] = []
        if not sub_all.empty and merc in sub_all.columns and imp in sub_all.columns:
            agg = sub_all.groupby(merc)[imp].sum().nlargest(10).reset_index()
            top_productos = [{"producto": str(r[merc]), "total": round(float(r[imp]), 2)} for _, r in agg.iterrows()]

        vendedores_out.append({
            "gestor": g, "nombre": g_cfg.get("nombre", g), "sector": g_cfg.get("sector", ""),
            "total_importe": total_importe, "num_operaciones": num_ops, "num_clientes": num_clientes,
            "comision": comision, "sin_pedido": sin_pedido, "descuento": descuento, "comision_neta": comision_neta,
            "total_hectolitros": total_hl, "cuota_hl": cuota,
            "cumplimiento_pct": round((total_hl / cuota * 100) if cuota else 0.0, 2),
            "malta_330": M330, "malta_500": M500, "malta_1500": M1500,
            "parranda_330": P330, "parranda_500": P500, "parranda_1500": P1500,
            "top_productos": top_productos,
        })

    return {
        "rango": report.rango_str, "vendedores": vendedores_out,
        "total_importe": round(sum(v["total_importe"] for v in vendedores_out), 2),
        "total_hectolitros": round(sum(v["total_hectolitros"] for v in vendedores_out), 2),
        "total_operaciones": sum(v["num_operaciones"] for v in vendedores_out),
    }
