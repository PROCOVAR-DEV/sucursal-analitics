"""Servicio de Ventas / Supervisor (hectolitros MALTA/PARRANDA + mix por grupo)."""
from __future__ import annotations

import pandas as pd

from services.comisiones import comision_de
from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS


def _sum_hl(sub: pd.DataFrame, mask: pd.Series, size: str) -> float:
    if sub.empty:
        return 0.0
    return round(float(sub.loc[mask & (sub[STD_COLS["size"]] == size), "Hectolitros"].sum()), 2)


def _quien_supervisa(eff: dict, keys, gestores_cfg: dict) -> str | None:
    """Cuál de los gestores es el supervisor, o None si ninguno.

    Primero la marca explícita en su ficha; después, por compatibilidad, que su nombre
    sea el `supervisor_nombre` de la sucursal. Lo segundo es lo que ya había, y sin
    ello habría que ir a marcar a diez supervisores antes de que un solo número
    saliera bien.
    """
    for g in keys:
        if (gestores_cfg.get(g) or {}).get("es_supervisor"):
            return g

    nombre_super = str(eff.get("supervisor_nombre") or "").strip().upper()
    if not nombre_super:
        return None
    for g in keys:
        cfg = gestores_cfg.get(g) or {}
        if str(cfg.get("nombre", g)).strip().upper() == nombre_super:
            return g
    return None


def compute_ventas(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    groups_order = eff.get("groups_order") or []
    units_pp = {str(k): float(v) for k, v in (eff.get("units_per_pallet") or {}).items()}
    meta_total = float(eff["meta_hectolitros_total"])
    meta_dinero = float(eff["meta_dinero_total"])
    com_gestor = float(eff.get("comision_gestor_pct", 0.01))
    reglas_com = eff.get("reglas_comision") or []
    periodo = eff.get("_period") or ""
    com_super = float(eff.get("comision_supervisor_pct", 0.10))
    # Quién es el supervisor. Él no paga el 10%: lo COBRA.
    #
    # Se marca en su ficha de gestor (`es_supervisor`). Y si nadie lo marcó, se acepta
    # que su nombre coincida con el `supervisor_nombre` de la sucursal, que es como
    # estaba puesto hasta ahora — así funciona sin tener que ir a tocar la
    # configuración de las diez sucursales antes de que los números salgan bien.
    supervisor_key = _quien_supervisa(eff, keys, gestores_cfg)
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
        # Con reglas por producto la comisión ya no es un porcentaje sobre el
        # total: cada línea puede llevar el suyo. Sin reglas el resultado es
        # idéntico al de antes (total_importe * com_gestor).
        com = comision_de(sub_all, com_gestor, reglas_com, periodo)
        comision = com["comision"]

        # Ventas sin pedido (Nota con V- y sin P-) → descuento a la comisión
        sin_pedido = int(sub_all["SinPedido"].sum()) if ("SinPedido" in sub_all.columns and not sub_all.empty) else 0
        importe_sin_pedido = round(float(sub_all.loc[sub_all["SinPedido"], imp].sum()) if ("SinPedido" in sub_all.columns and imp in sub_all.columns and not sub_all.empty) else 0.0, 2)
        descuento = round(sin_pedido * desc_sin_pedido, 2)

        # Lo del supervisor SALE de la comisión del gestor.
        #
        # Se calculaba y se enseñaba, pero no se le restaba a nadie: el supervisor
        # cobraba su 10% y los gestores seguían cobrando la comisión entera, así que
        # la suma de lo que se pagaba era mayor que la comisión generada. Se descuenta
        # aquí, gestor a gestor, y no del total: redondear una vez sobre la suma da un
        # número distinto que redondear cada parte, y lo que cobra cada uno tiene que
        # cuadrar con lo que se le descontó a cada uno.
        # Al supervisor NO se le descuenta: lo que vende es suyo entero, y encima se
        # lleva el 10% de lo que ganan los demás. Descontárselo era cobrarle su propia
        # comisión.
        es_supervisor = g == supervisor_key
        comision_supervisor = 0.0 if es_supervisor else round(comision * com_super, 2)
        comision_neta = round(comision - comision_supervisor - descuento, 2)

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
            "comision_detalle": com["detalle"],
            "sin_pedido": sin_pedido, "importe_sin_pedido": importe_sin_pedido,
            "descuento": descuento,
            # Lo que se le va al supervisor, en su propia columna: un neto más bajo
            # sin decir por qué es lo que hace que alguien piense que le robaron.
            "comision_supervisor": comision_supervisor,
            "es_supervisor": es_supervisor,
            "comision_neta": comision_neta,
            "total_hectolitros": total_hl, "cuota_hl": cuota, "cumplimiento_pct": cumplimiento,
            "malta_330": M330, "malta_500": M500, "malta_1500": M1500,
            "parranda_330": P330, "parranda_500": P500, "parranda_1500": P1500,
            "mix": mix, "conversion": conv,
        })
        supervisor_rows.append({
            "gestor": g, "total_venta": total_importe, "comision": comision,
            "comision_supervisor": comision_supervisor,
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
    # La comisión del supervisor es la SUMA de lo que se le quitó a cada gestor, no un
    # porcentaje del total: si se calculara aparte, por redondeo saldría un céntimo
    # distinto de lo descontado y el cuadre no daría.
    total_comision_supervisor = round(sum(g["comision_supervisor"] for g in gestores_out), 2)
    total_comision_neta = round(sum(g["comision_neta"] for g in gestores_out), 2)

    # Lo que cobra el supervisor: lo suyo limpio MÁS el 10% de cada gestor. Se suma
    # aquí y no en su fila para que su fila siga diciendo lo que vendió él —mezclarlo
    # dejaría su comisión propia imposible de leer.
    fila_super = next((x for x in gestores_out if x.get("es_supervisor")), None)
    if fila_super is not None:
        fila_super["comision_de_los_gestores"] = total_comision_supervisor
        fila_super["comision_total_supervisor"] = round(
            fila_super["comision_neta"] + total_comision_supervisor, 2
        )

    return {
        "rango": report.rango_str, "periodo": eff.get("_period"),
        "supervisor_nombre": eff.get("supervisor_nombre"),
        "supervisor_gestor": supervisor_key,
        "meta_hectolitros": meta_total, "meta_dinero": meta_dinero,
        "total_hectolitros": total_hl, "total_importe": total_importe,
        "total_comision_gestores": total_comision,
        "comision_supervisor": total_comision_supervisor,
        "comision_supervisor_pct": com_super,
        "total_sin_pedido": total_sin_pedido, "total_descuento_sin_pedido": total_descuento,
        "total_comision_neta": total_comision_neta, "descuento_sin_pedido": desc_sin_pedido,
        "cumplimiento_pct": round((total_hl / meta_total * 100) if meta_total else 0.0, 2),
        "cumplimiento_dinero_pct": round((total_importe / meta_dinero * 100) if meta_dinero else 0.0, 2),
        "groups_order": groups_order,
        "gestores": gestores_out, "supervisor": supervisor_rows,
    }
