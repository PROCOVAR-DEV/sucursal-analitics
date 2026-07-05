"""Servicio de Ventas / Supervisor (hectolitros MALTA/PARRANDA + mix por grupo)."""
from __future__ import annotations

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS


def _sum_hl(sub: pd.DataFrame, mask: pd.Series, size: str) -> float:
    if sub.empty:
        return 0.0
    return round(float(sub.loc[mask & (sub[STD_COLS["size"]] == size), "Hectolitros"].sum()), 2)


def compute_ventas(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    groups_order = eff.get("groups_order") or []
    units_pp = {str(k): float(v) for k, v in (eff.get("units_per_pallet") or {}).items()}
    meta_total = float(eff["meta_hectolitros_total"])
    meta_dinero = float(eff["meta_dinero_total"])
    com_gestor = float(eff.get("comision_gestor_pct", 0.01))
    com_super = float(eff.get("comision_supervisor_pct", 0.10))
    desc_sin_pedido = float(eff.get("descuento_sin_pedido", 0.0))

    df_all = enrich_for_sucursal(report, eff)
    df_all = only_valid(df_all, keys)
    df_mp = df_all[df_all["IsMalta"] | df_all["IsParranda"]].copy() if not df_all.empty else df_all

    imp = STD_COLS["importe"]
    cant = STD_COLS["cant"]
    gestores_out: list[dict] = []
    supervisor_rows: list[dict] = []

    for g in keys:
        g_cfg = gestores_cfg.get(g, {})
        sub_all = df_all[df_all["GestorDetectado"] == g] if not df_all.empty else df_all
        sub = df_mp[df_mp["GestorDetectado"] == g] if not df_mp.empty else df_mp

        total_importe = round(float(sub_all[imp].sum()) if imp in sub_all.columns else 0.0, 2)
        M330, M500, M1500 = (_sum_hl(sub, sub["IsMalta"], s) for s in ("330", "500", "1500")) if not sub.empty else (0.0, 0.0, 0.0)
        P330, P500, P1500 = (_sum_hl(sub, sub["IsParranda"], s) for s in ("330", "500", "1500")) if not sub.empty else (0.0, 0.0, 0.0)
        total_hl = round(M330 + M500 + M1500 + P330 + P500 + P1500, 2)

        cuota = float(g_cfg.get("cuota_hl", 0.0))
        cumplimiento = round((total_hl / cuota * 100) if cuota else 0.0, 2)
        comision = round(total_importe * com_gestor, 2)

        # Ventas sin pedido (Nota con V- y sin P-) → descuento a la comisión
        sin_pedido = int(sub_all["SinPedido"].sum()) if ("SinPedido" in sub_all.columns and not sub_all.empty) else 0
        importe_sin_pedido = round(float(sub_all.loc[sub_all["SinPedido"], imp].sum()) if ("SinPedido" in sub_all.columns and imp in sub_all.columns and not sub_all.empty) else 0.0, 2)
        descuento = round(sin_pedido * desc_sin_pedido, 2)
        comision_neta = round(comision - descuento, 2)

        # Mix por grupo comercial ($)
        mix = {}
        if not sub_all.empty and imp in sub_all.columns:
            grp_sum = sub_all.groupby("GrupoComercial")[imp].sum()
            for grp in groups_order:
                mix[grp] = round(float(grp_sum.get(grp, 0.0)), 2)

        # Conversión blisters/pallets
        conv: list[dict] = []
        if not sub.empty:
            for prod, mask in (("MALTA", sub["IsMalta"]), ("PARRANDA", sub["IsParranda"])):
                for size in ("330", "500", "1500"):
                    sel = sub[mask & (sub[STD_COLS["size"]] == size)]
                    if sel.empty:
                        continue
                    blisters = float(sel[cant].fillna(0).sum()) if cant in sel.columns else 0.0
                    units = units_pp.get(size, 0)
                    conv.append({
                        "producto": prod.capitalize(), "tamano": size,
                        "blisters": round(blisters, 2),
                        "pallets": round(blisters / units, 2) if units else 0.0,
                        "hectolitros": _sum_hl(sub, mask, size),
                    })

        gestores_out.append({
            "gestor": g, "nombre": g_cfg.get("nombre", g), "sector": g_cfg.get("sector", ""),
            "agencia": g_cfg.get("agencia", ""),
            "total_importe": total_importe, "comision": comision,
            "sin_pedido": sin_pedido, "importe_sin_pedido": importe_sin_pedido,
            "descuento": descuento, "comision_neta": comision_neta,
            "total_hectolitros": total_hl, "cuota_hl": cuota, "cumplimiento_pct": cumplimiento,
            "malta_330": M330, "malta_500": M500, "malta_1500": M1500,
            "parranda_330": P330, "parranda_500": P500, "parranda_1500": P1500,
            "mix": mix, "conversion": conv,
        })
        supervisor_rows.append({
            "gestor": g, "total_venta": total_importe, "comision": comision,
            "mix": mix,
            "M330": M330, "M500": M500, "M1500": M1500,
            "P330": P330, "P500": P500, "P1500": P1500,
            "total_hectolitros": total_hl,
        })

    total_hl = round(sum(r["total_hectolitros"] for r in supervisor_rows), 2)
    total_importe = round(sum(r["total_venta"] for r in supervisor_rows), 2)
    total_comision = round(sum(r["comision"] for r in supervisor_rows), 2)
    total_sin_pedido = int(sum(g["sin_pedido"] for g in gestores_out))
    total_descuento = round(sum(g["descuento"] for g in gestores_out), 2)
    total_comision_neta = round(total_comision - total_descuento, 2)

    return {
        "rango": report.rango_str, "periodo": eff.get("_period"),
        "supervisor_nombre": eff.get("supervisor_nombre"),
        "meta_hectolitros": meta_total, "meta_dinero": meta_dinero,
        "total_hectolitros": total_hl, "total_importe": total_importe,
        "total_comision_gestores": total_comision,
        "comision_supervisor": round(total_comision * com_super, 2),
        "total_sin_pedido": total_sin_pedido, "total_descuento_sin_pedido": total_descuento,
        "total_comision_neta": total_comision_neta, "descuento_sin_pedido": desc_sin_pedido,
        "cumplimiento_pct": round((total_hl / meta_total * 100) if meta_total else 0.0, 2),
        "cumplimiento_dinero_pct": round((total_importe / meta_dinero * 100) if meta_dinero else 0.0, 2),
        "groups_order": groups_order,
        "gestores": gestores_out, "supervisor": supervisor_rows,
    }
