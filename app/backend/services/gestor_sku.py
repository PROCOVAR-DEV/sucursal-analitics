"""
Informe cruzado GESTOR x SKU por importe.

El informe que ya existía (`vendedores`) muestra CADA gestor con sus productos,
uno debajo de otro: para comparar quién vende más de un producto concreto hay que
ir abriendo gestor por gestor y sumando a mano.

Este devuelve lo mismo cruzado, que es como se lee de verdad:

  - `filas`: una fila por (gestor, producto) con importe, cantidad y HL. Es la
    tabla plana, con la columna de gestor que pedía Jose.
  - `matriz`: productos en filas, gestores en columnas. Cada celda es el importe.
    Sirve para ver de un vistazo quién vende qué.
  - Totales en LAS DOS direcciones: por gestor, por producto, y el gran total.
    Sin totales la tabla obliga a sumar con la calculadora.

Se apoya en el mismo enriquecido y las mismas reglas de validez que el resto de
informes (`enrich_for_sucursal` + `only_valid`), para que los números cuadren con
los de las otras pantallas. Si aquí se filtrara distinto, dos pantallas darían
cifras diferentes para lo mismo y no habría forma de saber cuál creer.
"""
from __future__ import annotations

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS


def compute_gestor_sku(
    report,
    eff: dict,
    grupos: list[str] | None = None,
    metrica: str = "importe",
) -> dict:
    """El cruce gestor × producto, en importe o en cantidad.

    Mismas dos opciones que el análisis de clientes, y a propósito: son la misma
    pregunta mirada por otro lado, así que si una pantalla filtra por grupo y la
    otra no, los dos números dejan de poderse comparar.

    `metrica` cambia lo que se SUMA y también por lo que se ORDENA. Ordenar por
    importe una tabla que enseña cantidades pondría arriba lo que más factura, no
    lo que más se mueve — y quien la lea creerá que está viendo lo segundo.
    """
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}

    imp, merc, cant = STD_COLS["importe"], STD_COLS["merc"], STD_COLS["cant"]

    df = enrich_for_sucursal(report, eff)
    df = only_valid(df, keys)

    # Los grupos que EXISTEN en estos datos, antes de filtrar: si se calcularan
    # después, al elegir uno desaparecerían los demás del filtro.
    disponibles = (
        sorted({str(g) for g in df["GrupoComercial"].dropna().unique() if str(g).strip()})
        if df is not None and not df.empty and "GrupoComercial" in df.columns
        else []
    )

    if grupos and df is not None and not df.empty and "GrupoComercial" in df.columns:
        df = df[df["GrupoComercial"].astype(str).isin([str(g) for g in grupos])]

    vacio = {
        "rango": getattr(report, "rango_str", ""),
        "filas": [], "matriz": [], "gestores": [], "productos": [],
        "totales_gestor": [], "totales_producto": [],
        "total_importe": 0.0, "total_cantidad": 0.0, "total_hectolitros": 0.0,
        "grupos_disponibles": [], "grupos": list(grupos or []), "metrica": "importe",
    }
    if df is None or df.empty or merc not in df.columns:
        return {**vacio, "grupos_disponibles": disponibles}

    # Nombre legible del gestor; si no está configurado, se usa su clave.
    def nombre_de(g: str) -> str:
        return str((gestores_cfg.get(g) or {}).get("nombre", g))

    # `GestorDetectado` la pone enrich_for_sucursal cruzando el vendedor de cada
    # linea con los alias configurados de la sucursal. Es la misma columna que usa
    # el informe de vendedores, para que los numeros cuadren entre pantallas.
    col_gestor = "GestorDetectado"
    if col_gestor not in df.columns:
        return vacio

    aggs = {"importe": (imp, "sum")}
    if cant in df.columns:
        aggs["cantidad"] = (cant, "sum")

    # La columna por la que se suma y se ordena TODO lo de abajo. Si se pide
    # cantidad y no viene esa columna, se cae al importe: mejor el número de
    # siempre que una tabla vacía sin explicación.
    medida = "cantidad" if (metrica == "cantidad" and cant in df.columns) else "importe"
    if "Hectolitros" in df.columns:
        aggs["hectolitros"] = ("Hectolitros", "sum")
    aggs["operaciones"] = (merc, "size")

    agrupado = (
        df.groupby([col_gestor, merc], dropna=False)
        .agg(**aggs)
        .reset_index()
        .sort_values(medida, ascending=False)
    )

    filas = [
        {
            "gestor": str(r[col_gestor]),
            "gestor_nombre": nombre_de(str(r[col_gestor])),
            "producto": str(r[merc]),
            "importe": round(float(r["importe"]), 2),
            "cantidad": round(float(r.get("cantidad", 0) or 0), 2),
            "hectolitros": round(float(r.get("hectolitros", 0) or 0), 2),
            "operaciones": int(r["operaciones"]),
        }
        for _, r in agrupado.iterrows()
    ]

    # Orden de columnas y filas: por importe descendente, para que lo que más pesa
    # quede arriba y a la izquierda en vez de en orden alfabético.
    tot_g = (
        agrupado.groupby(col_gestor)[medida].sum().sort_values(ascending=False)
    )
    tot_p = agrupado.groupby(merc)[medida].sum().sort_values(ascending=False)

    gestores = [{"clave": str(g), "nombre": nombre_de(str(g))} for g in tot_g.index]
    productos = [str(p) for p in tot_p.index]

    # Matriz producto x gestor. Se rellena con 0.0 lo que no tiene venta, para que
    # la tabla del front no tenga huecos y se pueda sumar sin comprobar nulos.
    pivote = agrupado.pivot_table(
        index=merc, columns=col_gestor, values=medida, aggfunc="sum", fill_value=0.0
    )
    matriz = [
        {
            "producto": str(p),
            "por_gestor": {str(g): round(float(pivote.loc[p, g]), 2) for g in tot_g.index if g in pivote.columns},
            "total": round(float(tot_p.loc[p]), 2),
        }
        for p in productos
    ]

    def suma(col: str) -> float:
        return round(float(agrupado[col].sum()), 2) if col in agrupado.columns else 0.0

    totales_gestor = []
    for g in tot_g.index:
        sub = agrupado[agrupado[col_gestor] == g]
        totales_gestor.append({
            "gestor": str(g),
            "gestor_nombre": nombre_de(str(g)),
            "importe": round(float(sub["importe"].sum()), 2),
            "cantidad": round(float(sub["cantidad"].sum()), 2) if "cantidad" in sub else 0.0,
            "hectolitros": round(float(sub["hectolitros"].sum()), 2) if "hectolitros" in sub else 0.0,
            # Lo que se está midiendo ahora (importe o cantidad). Va aparte para
            # que quien lo lea no tenga que adivinar si "importe" trae dólares o
            # empaques según cómo se pidió.
            "medida": round(float(sub[medida].sum()), 2),
            "productos_distintos": int(sub[merc].nunique()),
        })

    totales_producto = [
        {
            "producto": str(p),
            "importe": round(float(agrupado[agrupado[merc] == p]["importe"].sum()), 2),
            "medida": round(float(tot_p.loc[p]), 2),
            "gestores_que_lo_venden": int((pivote.loc[p] > 0).sum()) if p in pivote.index else 0,
        }
        for p in productos
    ]

    return {
        "rango": getattr(report, "rango_str", ""),
        "grupos_disponibles": disponibles,
        "grupos": list(grupos or []),
        "metrica": medida,
        # El total de lo que se está midiendo. `total_importe` sigue siendo el de
        # dólares siempre, para que no cambie de significado a mitad.
        "total_medida": round(float(agrupado[medida].sum()), 2),
        "filas": filas,
        "matriz": matriz,
        "gestores": gestores,
        "productos": productos,
        "totales_gestor": totales_gestor,
        "totales_producto": totales_producto,
        "total_importe": suma("importe"),
        "total_cantidad": suma("cantidad"),
        "total_hectolitros": suma("hectolitros"),
    }
