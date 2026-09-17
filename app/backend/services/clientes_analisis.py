"""Análisis de clientes por vendedor.

Para cada vendedor y para la oficina completa, rankea los clientes por volumen de
ventas en dólares (mayor → menor) y desglosa, en la misma fila, cuánto compró ese
cliente de cada SKU (mercancía). Permite ver el perfil de compra de cada cliente,
qué SKU escala más/menos, los clientes más valiosos y la cartera de cada gestor.
"""
from __future__ import annotations

import pandas as pd

from core.utils import normalize_text
from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS
from services.pedidos import fetch_order_counts

SIN_NOMBRE = "(sin nombre)"
SIN_SKU = "(sin producto)"


def _clean_text(series: pd.Series, fallback: str) -> pd.Series:
    s = series.astype("string").fillna(fallback).str.strip()
    return s.mask(s.eq("") | s.str.upper().eq("NAN") | s.eq("<NA>"), fallback)


def _pivot(sub: pd.DataFrame, imp: str, socio: str, merc: str, with_gestor: bool, pedidos_map: dict | None = None) -> dict:
    """Pivote clientes×producto, ordenado por total de cliente (desc).

    `imp` es la columna que se SUMA: el importe en dólares o la cantidad por
    empaque, según lo que se pida. Todo lo demás es igual — el pivote no sabe ni
    le importa cuál de las dos está sumando, y por eso no hay dos versiones de
    esta función que puedan separarse.
    """
    empty = {"skus": [], "clientes": [], "total": 0.0, "num_clientes": 0, "num_skus": 0}
    if sub.empty or imp not in sub.columns or socio not in sub.columns or merc not in sub.columns:
        return empty
    sub = sub.copy()
    sub[socio] = _clean_text(sub[socio], SIN_NOMBRE)
    sub[merc] = _clean_text(sub[merc], SIN_SKU)
    sub[imp] = pd.to_numeric(sub[imp], errors="coerce").fillna(0.0)

    piv = sub.pivot_table(index=socio, columns=merc, values=imp, aggfunc="sum", fill_value=0.0)
    if piv.empty:
        return empty

    sku_tot = piv.sum(axis=0).sort_values(ascending=False)
    piv = piv[sku_tot.index]                       # columnas ordenadas por total desc
    cli_tot = piv.sum(axis=1).sort_values(ascending=False)

    dom_gestor: dict = {}
    if with_gestor and "GestorDetectado" in sub.columns:
        g_sum = sub.groupby([socio, "GestorDetectado"])[imp].sum()
        for cli in cli_tot.index:
            try:
                dom_gestor[cli] = str(g_sum.loc[cli].idxmax())
            except (KeyError, ValueError):
                dom_gestor[cli] = ""

    skus = [{"sku": str(s), "total": round(float(sku_tot[s]), 2)} for s in sku_tot.index]
    clientes = []
    for cli in cli_tot.index:
        row = piv.loc[cli]
        montos = {str(s): round(float(row[s]), 2) for s in sku_tot.index if float(row[s]) != 0.0}
        item = {
            "cliente": str(cli),
            "total": round(float(cli_tot[cli]), 2),
            "num_skus": int((row != 0).sum()),
            "pedidos": (pedidos_map or {}).get(normalize_text(str(cli)), 0),
            "sku_montos": montos,
        }
        if with_gestor:
            item["gestor"] = dom_gestor.get(cli, "")
        clientes.append(item)

    return {
        "skus": skus,
        "clientes": clientes,
        "total": round(float(cli_tot.sum()), 2),
        "num_clientes": int(len(cli_tot)),
        "num_skus": int(len(sku_tot)),
    }


def _fundir_ambas(piv_imp: dict, piv_cant: dict) -> dict:
    """Pone la cantidad AL LADO del importe, en la misma fila y la misma celda.

    Claudia los pedía juntos: con una pestaña para cada uno hay que mirar dos
    tablas y cruzarlas a ojo, y lo que se quiere saber —«de éste vendí mucho
    dinero pero pocas cajas»— sólo se ve con los dos números pegados.

    El ORDEN y la lista de clientes los manda el importe. Son dos rankings
    distintos y mezclarlos daría una tabla que no está ordenada por nada: el
    informe dice «clientes rankeados por ventas», así que ése es el que manda y
    la cantidad viaja de acompañante.

    Un cliente que compró pero no aparece en el pivote de cantidad —o al revés—
    sale con cero en la columna que le falte, no desaparece.
    """
    cant_por_cliente = {c["cliente"]: c for c in (piv_cant.get("clientes") or [])}
    cant_por_sku = {s["sku"]: s["total"] for s in (piv_cant.get("skus") or [])}

    skus = [{**s, "total_cantidad": round(float(cant_por_sku.get(s["sku"], 0.0)), 2)} for s in (piv_imp.get("skus") or [])]

    clientes = []
    for c in piv_imp.get("clientes") or []:
        otro = cant_por_cliente.get(c["cliente"]) or {}
        clientes.append({
            **c,
            "total_cantidad": round(float(otro.get("total", 0.0)), 2),
            "sku_cantidades": otro.get("sku_montos") or {},
        })

    return {
        **piv_imp,
        "skus": skus,
        "clientes": clientes,
        "total_cantidad": round(float(piv_cant.get("total", 0.0)), 2),
    }


def compute_clientes_analisis(
    report,
    eff: dict,
    grupos: list[str] | None = None,
    metrica: str = "importe",
) -> dict:
    """El pivote de clientes × producto, en importe o en cantidad.

    `grupos` acota a unos grupos comerciales (PARRANDA, IMPORTACIONES...). Los
    grupos no están escritos a mano en ningún sitio: salen de los datos, así que
    cuando se configure uno nuevo aparece solo en el filtro sin tocar código.

    `metrica`:
      - "importe": dólares. Es lo que había y sigue siendo lo predeterminado.
      - "cantidad": unidades POR EMPAQUE, que es como viene la columna del
        origen — no se convierte a unidades sueltas, porque el negocio cuenta
        por empaque y convertirlo daría un número que nadie usa.
      - "ambas": las dos en la misma tabla, ordenadas por importe. Lo pidió
        Claudia: con una pestaña para cada una hay que cruzarlas a ojo.
    """
    keys = gestor_keys(eff)
    df = only_valid(enrich_for_sucursal(report, eff), keys)
    imp, socio, merc = STD_COLS["importe"], STD_COLS["socio"], STD_COLS["merc"]

    # Los grupos que EXISTEN en estos datos, para que el filtro los ofrezca.
    # Se calculan ANTES de filtrar: si no, al elegir uno desaparecerían los demás
    # de la lista y no habría forma de volver.
    disponibles = (
        sorted({str(g) for g in df["GrupoComercial"].dropna().unique() if str(g).strip()})
        if "GrupoComercial" in df.columns
        else []
    )

    if grupos and "GrupoComercial" in df.columns:
        df = df[df["GrupoComercial"].astype(str).isin([str(g) for g in grupos])]

    # La columna que se suma. Si se pide cantidad y no viene esa columna, se cae
    # al importe: mejor enseñar el número de siempre que una tabla vacía sin
    # explicación.
    cant = STD_COLS["cant"]
    hay_cantidad = cant in df.columns

    if metrica == "cantidad" and hay_cantidad:
        imp = cant
        metrica_real = "cantidad"
    elif metrica == "ambas" and hay_cantidad:
        # `imp` se queda en el importe: es el que ordena y el que manda. La
        # cantidad se saca aparte y se pega al lado en `_fundir_ambas`.
        metrica_real = "ambas"
    else:
        metrica_real = "importe"

    # Cantidad de pedidos por cliente desde PEDIDO (best-effort; {} si no responde).
    pedidos_map = fetch_order_counts()

    ambas = metrica_real == "ambas"

    def pivotar(sub, with_gestor: bool) -> dict:
        piv = _pivot(sub, imp, socio, merc, with_gestor=with_gestor, pedidos_map=pedidos_map)
        if not ambas:
            return piv
        return _fundir_ambas(piv, _pivot(sub, cant, socio, merc, with_gestor=with_gestor, pedidos_map=pedidos_map))

    gestores_cfg = eff.get("gestores") or {}
    por_gestor = []
    for g in keys:
        por_gestor.append({
            "gestor": g,
            "nombre": (gestores_cfg.get(g) or {}).get("nombre", g),
            **pivotar(df[df["GestorDetectado"] == g], False),
        })

    return {
        "rango": report.rango_str,
        "periodo": eff.get("_period"),
        "grupos_disponibles": disponibles,
        "grupos": list(grupos or []),
        "metrica": metrica_real,
        "oficina": pivotar(df, True),
        "por_gestor": por_gestor,
    }
