"""Si la base de clientes CRECE o sólo se reordena.

La app sabe decir cuánto se vendió, a quién y de qué. No sabe decir **quién dejó de
comprar** — y eso es lo que se pierde sin que nadie lo note: el importe del mes puede
quedar igual mientras por debajo entran cinco clientes y se van otros cinco más grandes.

Cuatro estados, comparando el periodo elegido con el ANTERIOR de la misma longitud:

  nuevo       compró ahora y nunca antes, en todo lo que hay cargado
  recuperado  compró ahora, no compró en el periodo anterior, pero sí alguna vez
  mantenido   compró en los dos
  perdido     compró en el anterior y ahora no

Y dentro de los mantenidos, los que SE ESTÁN APAGANDO: siguen comprando pero bastante
menos que antes. Es el paso anterior a irse y no se ve en ningún sitio — un cliente que
baja de 800 a 300 sigue apareciendo en todas las listas de ventas, con menos importe, y
nadie lo lee como una señal. Cuando se convierte en «perdido» ya es tarde.

«Perdido» es el que importa y el único que no se ve en ninguna otra pantalla: los otros
tres aparecen, de una forma u otra, en cualquier lista de ventas. Un cliente que deja de
comprar no aparece en ningún sitio precisamente porque no aparece.

Por eso se devuelven los NOMBRES de los perdidos y no sólo cuántos son: un número no se
puede llamar por teléfono.

El periodo anterior se calcula por longitud, no por mes natural: si se está mirando del 1
al 10, el anterior son los diez días de antes. Comparar diez días contra un mes entero
diría que se perdió media cartera.
"""
from __future__ import annotations

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS

# Cuántos nombres se devuelven de cada lista. Son para llamar por teléfono, no para
# exportar: con veinte por gestor ya hay trabajo para una semana.
TOPE_NOMBRES = 20

# Cuánto tiene que bajar un cliente para llamarlo «apagándose». El 30% porque por debajo
# es ruido normal —un mes con una semana mala baja un 20% sin que pase nada— y por encima
# ya no es casualidad.
CAIDA = 0.30


def compute_movimiento_clientes(report_completo, eff: dict, desde, hasta,
                                grupos: list[str] | None = None) -> dict:
    """`desde`/`hasta` son las fechas del periodo que se está mirando (Timestamps).

    Recibe el informe COMPLETO, no el ya filtrado: hace falta lo anterior para saber qué
    es nuevo y qué se perdió, y eso no está en el recorte.
    """
    keys = gestor_keys(eff)
    fec, socio, imp = STD_COLS["fecha"], STD_COLS["socio"], STD_COLS["importe"]
    gestores_cfg = eff.get("gestores") or {}

    vacio = {
        "rango_actual": None, "rango_anterior": None, "dias": 0,
        "grupos_disponibles": [], "grupos": [], "por_gestor": [], "oficina": None,
    }

    if report_completo is None or report_completo.df.empty:
        return vacio

    df = only_valid(enrich_for_sucursal(report_completo, eff), keys)

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

    ini = pd.Timestamp(desde).normalize()
    fin = pd.Timestamp(hasta).normalize()
    dias = max(1, (fin - ini).days + 1)
    ini_ant = ini - pd.Timedelta(days=dias)
    fin_ant = ini - pd.Timedelta(days=1)

    d = df[fec].dt.normalize()
    ahora = df[(d >= ini) & (d <= fin)]
    antes = df[(d >= ini_ant) & (d <= fin_ant)]
    # «Nunca antes» se mide contra TODO lo cargado, no contra el periodo anterior: un
    # cliente que compró en enero y vuelve en septiembre no es nuevo, es recuperado, y
    # tratarlo de nuevo inflaría el crecimiento con gente de toda la vida.
    historico = df[d < ini]

    def bloque(sub_ahora, sub_antes, sub_hist, nombre, meta=None):
        clientes_ahora = set(sub_ahora[socio].dropna().astype(str))
        clientes_antes = set(sub_antes[socio].dropna().astype(str))
        clientes_hist = set(sub_hist[socio].dropna().astype(str))

        nuevos = clientes_ahora - clientes_hist
        recuperados = (clientes_ahora - clientes_antes) - nuevos
        mantenidos = clientes_ahora & clientes_antes
        perdidos = clientes_antes - clientes_ahora

        def importe_de(sub, quienes):
            if not quienes:
                return 0.0
            return round(float(sub.loc[sub[socio].astype(str).isin(quienes), imp].sum()), 2)

        # LOS QUE SE APAGAN: compran en los dos periodos, pero bastante menos.
        #
        # Se compara cada cliente CONSIGO MISMO entre los dos periodos. Sale la lista de
        # los que más importe han dejado de traer, no los que más porcentaje han bajado:
        # uno que pasa de 10 a 4 baja un 60% y da igual; uno que pasa de 5.000 a 3.000
        # baja un 40% y son dos mil pesos.
        apagandose = []

        if mantenidos:
            act = sub_ahora[sub_ahora[socio].astype(str).isin(mantenidos)].groupby(
                sub_ahora[socio].astype(str))[imp].sum()
            ant = sub_antes[sub_antes[socio].astype(str).isin(mantenidos)].groupby(
                sub_antes[socio].astype(str))[imp].sum()

            for cliente in mantenidos:
                a = float(ant.get(cliente, 0.0))
                b = float(act.get(cliente, 0.0))

                if a <= 0 or b >= a * (1 - CAIDA):
                    continue

                apagandose.append({
                    "cliente": cliente,
                    "antes": round(a, 2),
                    "ahora": round(b, 2),
                    "baja": round(a - b, 2),
                    "baja_pct": round((a - b) / a * 100, 2),
                })

            apagandose.sort(key=lambda c: c["baja"], reverse=True)

        # De los perdidos importa CUÁNTO se dejó de vender, no cuántos son: perder tres
        # clientes pequeños no es lo mismo que perder uno grande.
        por_perdido = (
            sub_antes[sub_antes[socio].astype(str).isin(perdidos)]
            .groupby(sub_antes[socio].astype(str))[imp].sum().sort_values(ascending=False)
            if perdidos else pd.Series(dtype=float)
        )

        return {
            "gestor": nombre,
            "nombre": meta or nombre,
            "nuevos": len(nuevos), "recuperados": len(recuperados),
            "mantenidos": len(mantenidos), "perdidos": len(perdidos),
            "clientes_ahora": len(clientes_ahora), "clientes_antes": len(clientes_antes),
            "importe_ahora": round(float(sub_ahora[imp].sum()), 2),
            "importe_antes": round(float(sub_antes[imp].sum()), 2),
            "importe_nuevos": importe_de(sub_ahora, nuevos),
            "importe_recuperados": importe_de(sub_ahora, recuperados),
            # Lo que compraban los perdidos en el periodo anterior: es lo que falta ahora.
            "importe_perdido": round(float(por_perdido.sum()), 2) if len(por_perdido) else 0.0,
            "lista_perdidos": [
                {"cliente": c, "compraba": round(float(v), 2)}
                for c, v in por_perdido.head(TOPE_NOMBRES).items()
            ],
            "lista_nuevos": sorted(nuevos)[:TOPE_NOMBRES],
            "apagandose": len(apagandose),
            "importe_apagado": round(sum(c["baja"] for c in apagandose), 2),
            "lista_apagandose": apagandose[:TOPE_NOMBRES],
        }

    por_gestor = [
        bloque(
            ahora[ahora["GestorDetectado"] == g],
            antes[antes["GestorDetectado"] == g],
            historico[historico["GestorDetectado"] == g],
            g,
            (gestores_cfg.get(g) or {}).get("nombre", g),
        )
        for g in keys
    ]
    # De peor a mejor: lo primero que hay que ver es quién está perdiendo cartera.
    por_gestor.sort(key=lambda b: b["importe_perdido"], reverse=True)

    return {
        "rango_actual": f"{ini.strftime('%d/%m/%Y')} - {fin.strftime('%d/%m/%Y')}",
        "rango_anterior": f"{ini_ant.strftime('%d/%m/%Y')} - {fin_ant.strftime('%d/%m/%Y')}",
        "dias": dias,
        "grupos_disponibles": grupos_disponibles,
        "grupos": pedidos,
        "por_gestor": por_gestor,
        "oficina": bloque(ahora, antes, historico, "OFICINA", "Toda la oficina"),
    }
