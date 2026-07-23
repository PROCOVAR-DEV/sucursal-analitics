"""Servicio de resumen completo por vendedor (todos los productos)."""
from __future__ import annotations

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS
from services.market import WEEKS, _week_of

# Formatos de cerveza para el desglose semanal por vendedor.
_FORMATOS_SEM = [
    ("Parranda", "IsParranda", "1500", "Parranda 1.5 L"),
    ("Parranda", "IsParranda", "500", "Parranda 500 ml"),
    ("Parranda", "IsParranda", "330", "Parranda 330 ml"),
    ("Malta", "IsMalta", "1500", "Malta 1.5 L"),
    ("Malta", "IsMalta", "500", "Malta 500 ml"),
    ("Malta", "IsMalta", "330", "Malta 330 ml"),
]


def _sum_hl(sub: pd.DataFrame, mask: pd.Series, size: str) -> float:
    if sub.empty:
        return 0.0
    return round(float(sub.loc[mask & (sub[STD_COLS["size"]] == size), "Hectolitros"].sum()), 2)


def _sku_semanal_vendedor(sub_mp: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """HL por formato (SKU) y por semana de calendario, para UN vendedor."""
    fec, size_col = STD_COLS["fecha"], STD_COLS["size"]
    out: list[dict] = []
    weeks_con_datos: set[str] = set()
    dv = pd.DataFrame()
    if not sub_mp.empty and fec in sub_mp.columns and "Hectolitros" in sub_mp.columns:
        dv = sub_mp.dropna(subset=[fec]).copy()
        dv["__w__"] = dv[fec].apply(_week_of)
        weeks_con_datos = set(dv["__w__"].unique())
    for prod, flag, size, label in _FORMATOS_SEM:
        by_week = {w: 0.0 for w in WEEKS}
        if not dv.empty and flag in dv.columns and size_col in dv.columns:
            mask = dv[flag].fillna(False) & (dv[size_col] == size)
            if mask.any():
                grp = dv.loc[mask].groupby("__w__")["Hectolitros"].sum()
                for w, v in grp.items():
                    if w in by_week:
                        by_week[w] = round(float(v), 2)
        out.append({"producto": prod, "formato": label, "semanal": by_week, "total": round(sum(by_week.values()), 2)})
    return out, [w for w in WEEKS if w in weeks_con_datos]


def compute_vendedores(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    com_gestor = float(eff.get("comision_gestor_pct", 0.01))
    desc_sin_pedido = float(eff.get("descuento_sin_pedido", 0.0))

    df_all = enrich_for_sucursal(report, eff)
    df_all = only_valid(df_all, keys)
    df_mp = df_all[df_all["IsMalta"] | df_all["IsParranda"]].copy() if not df_all.empty else df_all

    imp, op, socio, merc = STD_COLS["importe"], STD_COLS["op"], STD_COLS["socio"], STD_COLS["merc"]
    cant = STD_COLS["cant"]  # cantidad vendida (blisters/unidades de venta)
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
            aggs = {"total": (imp, "sum")}
            if cant in sub_all.columns:
                aggs["cantidad"] = (cant, "sum")  # cantidad vendida por producto
            # TODOS los productos (antes era top 10): el vendedor tiene que ver todo lo
            # que vende, no solo la cabeza. La tabla del front scrollea por dentro.
            agg = sub_all.groupby(merc).agg(**aggs).sort_values("total", ascending=False).reset_index()
            top_productos = [
                {
                    "producto": str(r[merc]),
                    "total": round(float(r["total"]), 2),
                    "cantidad": round(float(r.get("cantidad", 0)), 2),
                }
                for _, r in agg.iterrows()
            ]

        sku_semanal, weeks_disponibles = _sku_semanal_vendedor(sub_mp)

        vendedores_out.append({
            "gestor": g, "nombre": g_cfg.get("nombre", g), "sector": g_cfg.get("sector", ""),
            "total_importe": total_importe, "num_operaciones": num_ops, "num_clientes": num_clientes,
            "comision": comision, "sin_pedido": sin_pedido, "descuento": descuento, "comision_neta": comision_neta,
            "total_hectolitros": total_hl, "cuota_hl": cuota,
            "cumplimiento_pct": round((total_hl / cuota * 100) if cuota else 0.0, 2),
            "malta_330": M330, "malta_500": M500, "malta_1500": M1500,
            "parranda_330": P330, "parranda_500": P500, "parranda_1500": P1500,
            "top_productos": top_productos,
            # Cómo va vendiendo por SEMANA (HL por formato, semanas de calendario).
            "sku_semanal": sku_semanal, "weeks_disponibles": weeks_disponibles,
        })

    return {
        "rango": report.rango_str, "vendedores": vendedores_out,
        "total_importe": round(sum(v["total_importe"] for v in vendedores_out), 2),
        "total_hectolitros": round(sum(v["total_hectolitros"] for v in vendedores_out), 2),
        "total_operaciones": sum(v["num_operaciones"] for v in vendedores_out),
    }
