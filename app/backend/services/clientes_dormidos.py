"""Quién lleva sin comprar, y de quién depende cada vendedor.

Son las dos preguntas que quedan después de «quién entró y quién se fue», y ninguna se
puede contestar con una lista de ventas — las dos van de lo que NO pasó.

# Dormidos

«Perdido» compara dos periodos y depende de dónde se pongan los cortes: quien compra cada
cinco semanas sale perdido un mes y recuperado al siguiente, sin que haya pasado nada. Los
DÍAS SIN COMPRAR no dependen de ningún corte — cuarenta y siete días son cuarenta y siete
días—, y se leen contra lo que ese cliente suele tardar.

Por eso cada uno se compara con SU propio ritmo y no con un número igual para todos: un
cliente que compra cada quince días y lleva veinte está empezando a irse; otro que compra
cada dos meses y lleva veinte no tiene nada de raro. Un umbral único marcaría al segundo y
dejaría pasar al primero, que es justo al revés de lo que hace falta.

# Concentración

Cuánto de lo que vende cada uno depende de sus cinco mayores clientes. No es un problema
en sí —siempre hay clientes grandes— pero un vendedor con el 70% en cinco nombres tiene un
riesgo que no se ve en ninguna otra cifra: su mes entero depende de que no se caiga uno.
"""
from __future__ import annotations

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS

TOPE_NOMBRES = 25
# Cuántos clientes miran arriba para la concentración. Cinco porque es lo que cabe en la
# cabeza de quien la lee: "estos cinco son la mitad de tu mes".
CABEZA = 5
# Mínimo de compras para poder hablar de "su ritmo". Con una sola no hay intervalo, y con
# dos el intervalo es una casualidad.
COMPRAS_PARA_RITMO = 3


def compute_clientes_dormidos(report, eff: dict, grupos: list[str] | None = None) -> dict:
    keys = gestor_keys(eff)
    fec, socio, imp = STD_COLS["fecha"], STD_COLS["socio"], STD_COLS["importe"]
    gestores_cfg = eff.get("gestores") or {}

    vacio = {
        "hasta": None, "grupos_disponibles": [], "grupos": [],
        "por_gestor": [], "totales": None,
    }

    if report is None or report.df.empty:
        return vacio

    df = only_valid(enrich_for_sucursal(report, eff), keys)

    if df.empty or fec not in df.columns or socio not in df.columns:
        return vacio

    df = df.dropna(subset=[fec]).copy()

    if df.empty:
        return vacio

    grupos_disponibles = (
        sorted(x for x in df["GrupoComercial"].dropna().astype(str).unique() if x)
        if "GrupoComercial" in df.columns else []
    )
    pedidos = [str(g).upper() for g in (grupos or []) if str(g).strip()]

    if pedidos and "GrupoComercial" in df.columns:
        df = df[df["GrupoComercial"].astype(str).str.upper().isin(pedidos)].copy()

    if df.empty:
        return {**vacio, "grupos_disponibles": grupos_disponibles, "grupos": pedidos}

    # El "hoy" del estudio es el último día CON DATOS, no la fecha de la máquina: si Ventra
    # no ha traído lo de hoy, medir contra hoy diría que todo el mundo lleva un día más sin
    # comprar de los que lleva.
    hasta = df[fec].max().normalize()
    df["__dia__"] = df[fec].dt.normalize()
    nombres = df[socio].astype(str)

    filas = []

    for gestor, sub in df.groupby(df["GestorDetectado"].astype(str)):
        if gestor not in keys:
            continue

        s_nombres = sub[socio].astype(str)
        dormidos = []
        total_gestor = float(sub[imp].sum())

        for cliente, compras in sub.groupby(s_nombres):
            dias_compra = sorted(compras["__dia__"].unique())
            ultima = pd.Timestamp(dias_compra[-1])
            sin_comprar = int((hasta - ultima).days)

            # Su ritmo: la mediana de lo que tarda entre compra y compra. Mediana y no
            # media porque una parada larga de agosto arrastraría la media y haría parecer
            # normal cualquier silencio.
            if len(dias_compra) >= COMPRAS_PARA_RITMO:
                huecos = pd.Series(dias_compra).diff().dropna().dt.days
                ritmo = float(huecos.median()) if len(huecos) else None
            else:
                ritmo = None

            # Dormido = lleva MÁS DEL DOBLE de lo que suele tardar. El doble y no el
            # simple: pasarse un día de su ritmo no es irse, es un martes.
            umbral = (ritmo * 2) if ritmo else None
            if umbral is None or sin_comprar <= umbral:
                continue

            dormidos.append({
                "cliente": cliente,
                "dias_sin_comprar": sin_comprar,
                "suele_tardar": round(ritmo, 1),
                "ultima_compra": ultima.strftime("%Y-%m-%d"),
                "compraba": round(float(compras[imp].sum()), 2),
                "compras": len(dias_compra),
            })

        dormidos.sort(key=lambda c: c["compraba"], reverse=True)

        # Concentración: qué parte del total del gestor son sus cinco mayores.
        por_cliente = sub.groupby(s_nombres)[imp].sum().sort_values(ascending=False)
        cabeza = float(por_cliente.head(CABEZA).sum())

        filas.append({
            "gestor": gestor,
            "nombre": (gestores_cfg.get(gestor) or {}).get("nombre", gestor),
            "clientes": int(por_cliente.size),
            "dormidos": len(dormidos),
            "importe_dormido": round(sum(c["compraba"] for c in dormidos), 2),
            "concentracion_pct": round(cabeza / total_gestor * 100, 2) if total_gestor else 0.0,
            "cabeza": [
                {"cliente": c, "importe": round(float(v), 2)}
                for c, v in por_cliente.head(CABEZA).items()
            ],
            "lista": dormidos[:TOPE_NOMBRES],
        })

    filas.sort(key=lambda f: f["importe_dormido"], reverse=True)

    return {
        "hasta": hasta.strftime("%Y-%m-%d"),
        "grupos_disponibles": grupos_disponibles,
        "grupos": pedidos,
        "por_gestor": filas,
        "totales": {
            "dormidos": sum(f["dormidos"] for f in filas),
            "importe_dormido": round(sum(f["importe_dormido"] for f in filas), 2),
            "clientes": sum(f["clientes"] for f in filas),
        },
    }
