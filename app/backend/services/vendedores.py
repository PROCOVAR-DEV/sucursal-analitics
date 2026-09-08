"""Servicio de resumen completo por vendedor (todos los productos)."""
from __future__ import annotations

import pandas as pd

from services.comisiones import comision_de
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


def compute_vendedores(report, eff: dict, grupos: list[str] | None = None) -> dict:
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    com_gestor = float(eff.get("comision_gestor_pct", 0.01))
    reglas_com = eff.get("reglas_comision") or []
    periodo = eff.get("_period") or ""
    desc_sin_pedido = float(eff.get("descuento_sin_pedido", 0.0))
    # El mismo 10% que en Ventas, leído del mismo sitio. Si aquí se calculara distinto,
    # la misma persona cobraría dos cifras según la pantalla que abriera.
    com_super = float(eff.get("comision_supervisor_pct", 0.10))
    # El supervisor no se paga a sí mismo: ver `_quien_supervisa` en ventas.py.
    from services.ventas import _quien_supervisa
    supervisor_key = _quien_supervisa(eff, keys, gestores_cfg)

    df_all = enrich_for_sucursal(report, eff)
    df_all = only_valid(df_all, keys)

    # Los grupos que hay, ANTES de filtrar: calculados despues, elegir uno dejaria la
    # lista con un solo elemento y no habria forma de volver a los otros.
    grupos_disponibles = (
        sorted(x for x in df_all["GrupoComercial"].dropna().astype(str).unique() if x)
        if "GrupoComercial" in df_all.columns and not df_all.empty else []
    )

    # LA VISTA se filtra por grupo; LA COMISION no.
    #
    # Toda esta pantalla se movia solo con Parranda y Malta, y lo que se pide es poder
    # mirar cualquier familia — o todas— por vendedor. Pero una comision no se paga por
    # familia: se paga sobre lo que la persona vendio, entero. Calcularla sobre el grupo
    # elegido daria una cifra mas baja que parece lo que cobra y no lo es, y de eso no se
    # vuelve: quien la vea una vez ya no se fia de ninguna.
    #
    # Asi que las ventas, los clientes y los productos salen de `df_vista`, y la comision
    # sigue saliendo de `df_all`. `comision_sobre_todo` avisa a la pantalla de que la
    # cifra de dinero no cuadra a proposito con la de arriba.
    pedidos = [str(g).upper() for g in (grupos or []) if str(g).strip()]
    if pedidos and "GrupoComercial" in df_all.columns and not df_all.empty:
        df_vista = df_all[df_all["GrupoComercial"].astype(str).str.upper().isin(pedidos)].copy()
    else:
        df_vista = df_all

    df_mp = df_vista[df_vista["IsMalta"] | df_vista["IsParranda"]].copy() if not df_vista.empty else df_vista

    imp, op, socio, merc = STD_COLS["importe"], STD_COLS["op"], STD_COLS["socio"], STD_COLS["merc"]
    cant = STD_COLS["cant"]  # cantidad vendida (blisters/unidades de venta)

    # Lo que vendió la OFICINA de cada producto. Se calcula una vez y sirve para lo único
    # que convierte una cifra suelta en un juicio: «de todo el arroz que se vendió aquí,
    # él puso el 18%». Sin eso, "vendió 619 de arroz" no dice si es mucho o poco.
    oficina_por_producto = (
        df_vista.groupby(merc)[imp].sum().to_dict()
        if (not df_vista.empty and merc in df_vista.columns and imp in df_vista.columns) else {}
    )

    vendedores_out: list[dict] = []

    for g in keys:
        g_cfg = gestores_cfg.get(g, {})
        # `sub_todo` es TODO lo suyo (la comision sale de aqui); `sub_all` es lo que se
        # esta mirando. Sin filtro de grupo son el mismo dato.
        sub_todo = df_all[df_all["GestorDetectado"] == g] if not df_all.empty else df_all
        sub_all = df_vista[df_vista["GestorDetectado"] == g] if not df_vista.empty else df_vista
        sub_mp = df_mp[df_mp["GestorDetectado"] == g] if not df_mp.empty else df_mp

        total_importe = round(float(sub_all[imp].sum()) if imp in sub_all.columns and not sub_all.empty else 0.0, 2)
        num_ops = int(sub_all[op].nunique()) if op in sub_all.columns and not sub_all.empty else int(len(sub_all))
        num_clientes = int(sub_all[socio].nunique()) if socio in sub_all.columns and not sub_all.empty else 0
        # Las familias que NO son cerveza no se miden en hectolitros: el arroz, el papel
        # o una batería se cuentan en unidades. Sin esta cifra, al mirar esas familias la
        # pantalla solo podía enseñar dinero, y "cuánto vendió" no es solo cuánto cobró.
        total_cantidad = round(float(pd.to_numeric(sub_all[cant], errors="coerce").fillna(0).sum()), 2) \
            if (cant in sub_all.columns and not sub_all.empty) else 0.0

        M330, M500, M1500 = (_sum_hl(sub_mp, sub_mp["IsMalta"], s) for s in ("330", "500", "1500")) if not sub_mp.empty else (0.0, 0.0, 0.0)
        P330, P500, P1500 = (_sum_hl(sub_mp, sub_mp["IsParranda"], s) for s in ("330", "500", "1500")) if not sub_mp.empty else (0.0, 0.0, 0.0)
        total_hl = round(M330 + M500 + M1500 + P330 + P500 + P1500, 2)
        cuota = float(g_cfg.get("cuota_hl", 0.0))

        com = comision_de(sub_todo, com_gestor, reglas_com, periodo)
        comision = com["comision"]
        sin_pedido = int(sub_todo["SinPedido"].sum()) if ("SinPedido" in sub_todo.columns and not sub_todo.empty) else 0
        descuento = round(sin_pedido * desc_sin_pedido, 2)
        # Lo del supervisor sale de aquí, igual que en Ventas. Y a él no se le
        # descuenta: lo que vende es suyo entero.
        es_supervisor = g == supervisor_key
        comision_supervisor = 0.0 if es_supervisor else round(comision * com_super, 2)
        comision_neta = round(comision - comision_supervisor - descuento, 2)

        # Cada producto, con lo que hace falta para saber QUÉ hizo con él.
        #
        # Antes eran tres columnas: nombre, importe y cantidad. Con eso se ve cuánto
        # facturó y nada más — no si lo vendió a un cliente o a treinta, ni si repitió, ni
        # a qué precio, ni si en ese producto es de los que tiran o de los que no. Que es
        # justo lo que hay que saber para hablar con la persona.
        top_productos: list[dict] = []
        if not sub_all.empty and merc in sub_all.columns and imp in sub_all.columns:
            aggs = {"total": (imp, "sum")}
            if cant in sub_all.columns:
                aggs["cantidad"] = (cant, "sum")  # cantidad vendida por producto
            if op in sub_all.columns:
                aggs["operaciones"] = (op, "nunique")
            if socio in sub_all.columns:
                aggs["clientes"] = (socio, "nunique")
            if "Hectolitros" in sub_all.columns:
                aggs["hectolitros"] = ("Hectolitros", "sum")
            if "GrupoComercial" in sub_all.columns:
                aggs["grupo"] = ("GrupoComercial", "first")
            # TODOS los productos (antes era top 10): el vendedor tiene que ver todo lo
            # que vende, no solo la cabeza. La tabla del front scrollea por dentro.
            agg = sub_all.groupby(merc).agg(**aggs).sort_values("total", ascending=False).reset_index()
            for _, r in agg.iterrows():
                nombre = str(r[merc])
                tot = round(float(r["total"]), 2)
                qty = round(float(r.get("cantidad", 0) or 0), 2)
                de_oficina = float(oficina_por_producto.get(nombre, 0.0))
                top_productos.append({
                    "producto": nombre,
                    "grupo": str(r.get("grupo", "") or ""),
                    "total": tot,
                    "cantidad": qty,
                    "hectolitros": round(float(r.get("hectolitros", 0) or 0), 2),
                    "operaciones": int(r.get("operaciones", 0) or 0),
                    "clientes": int(r.get("clientes", 0) or 0),
                    # Precio medio: delata un descuento que no cuadra o una unidad mal
                    # cargada mucho antes de que se note en el total.
                    "precio_medio": round(tot / qty, 2) if qty else 0.0,
                    # Cuánto pesa este producto en LO SUYO.
                    "pct_del_gestor": round(tot / total_importe * 100, 2) if total_importe else 0.0,
                    # Y cuánto puso él de lo que vendió la oficina de ese producto.
                    "pct_de_la_oficina": round(tot / de_oficina * 100, 2) if de_oficina else 0.0,
                })

        # Cómo se reparte lo suyo entre familias. Con «todos los grupos» puestos, esto es
        # lo que contesta «¿qué hizo?» de un vistazo: uno que vende 90% cerveza y otro que
        # lo reparte en cuatro familias no hacen el mismo trabajo aunque facturen igual.
        por_grupo: list[dict] = []
        if not sub_all.empty and "GrupoComercial" in sub_all.columns:
            g_aggs = {"importe": (imp, "sum")}
            if cant in sub_all.columns:
                g_aggs["cantidad"] = (cant, "sum")
            if "Hectolitros" in sub_all.columns:
                g_aggs["hectolitros"] = ("Hectolitros", "sum")
            if socio in sub_all.columns:
                g_aggs["clientes"] = (socio, "nunique")
            if merc in sub_all.columns:
                g_aggs["productos"] = (merc, "nunique")
            gg = sub_all.groupby("GrupoComercial").agg(**g_aggs).sort_values("importe", ascending=False).reset_index()
            por_grupo = [
                {
                    "grupo": str(r["GrupoComercial"]),
                    "importe": round(float(r["importe"]), 2),
                    "cantidad": round(float(r.get("cantidad", 0) or 0), 2),
                    "hectolitros": round(float(r.get("hectolitros", 0) or 0), 2),
                    "clientes": int(r.get("clientes", 0) or 0),
                    "productos": int(r.get("productos", 0) or 0),
                    "pct": round(float(r["importe"]) / total_importe * 100, 2) if total_importe else 0.0,
                }
                for _, r in gg.iterrows()
            ]

        sku_semanal, weeks_disponibles = _sku_semanal_vendedor(sub_mp)

        vendedores_out.append({
            "gestor": g, "nombre": g_cfg.get("nombre", g), "sector": g_cfg.get("sector", ""),
            "total_importe": total_importe, "total_cantidad": total_cantidad,
            "num_operaciones": num_ops, "num_clientes": num_clientes,
            "comision": comision, "sin_pedido": sin_pedido, "descuento": descuento,
            "comision_supervisor": comision_supervisor, "es_supervisor": es_supervisor,
            "comision_neta": comision_neta,
            "total_hectolitros": total_hl, "cuota_hl": cuota,
            "cumplimiento_pct": round((total_hl / cuota * 100) if cuota else 0.0, 2),
            "malta_330": M330, "malta_500": M500, "malta_1500": M1500,
            "parranda_330": P330, "parranda_500": P500, "parranda_1500": P1500,
            "top_productos": top_productos, "por_grupo": por_grupo,
            # Cómo va vendiendo por SEMANA (HL por formato, semanas de calendario).
            "sku_semanal": sku_semanal, "weeks_disponibles": weeks_disponibles,
        })

    # Lo que el supervisor cobra de los demás: la suma de lo que se le descontó a cada
    # gestor. Va en SU ficha, aparte de su comisión propia, para que se lea "esto es lo
    # mío y esto es lo del equipo" en vez de un número mezclado que no se puede
    # comprobar.
    fila_super = next((v for v in vendedores_out if v.get("es_supervisor")), None)
    if fila_super is not None:
        del_equipo = round(sum(v["comision_supervisor"] for v in vendedores_out), 2)
        fila_super["comision_de_los_gestores"] = del_equipo
        fila_super["comision_total_supervisor"] = round(
            fila_super["comision_neta"] + del_equipo, 2
        )

    return {
        "rango": report.rango_str, "vendedores": vendedores_out,
        "total_importe": round(sum(v["total_importe"] for v in vendedores_out), 2),
        "total_hectolitros": round(sum(v["total_hectolitros"] for v in vendedores_out), 2),
        "total_operaciones": sum(v["num_operaciones"] for v in vendedores_out),
        "grupos_disponibles": grupos_disponibles,
        "grupos": pedidos,
        # La pantalla tiene que poder decir que el dinero de la comision no cuadra con
        # las ventas de arriba, y por que. Callarlo seria peor que no filtrar.
        "comision_sobre_todo": bool(pedidos),
    }
