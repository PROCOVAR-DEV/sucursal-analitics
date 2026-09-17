"""
El plan de cada vendedor POR SKU, repartido según lo que vendió el mes pasado.

Hasta ahora la calculadora sembraba a todos los gestores con la MISMA tabla de
formatos —una copia del plan de Camagüey escrita en el código— así que dos
vendedores con metas distintas (558,76 y 554,55 HL) salían con el mismo desglose
y el mismo total, 232. El plan por SKU no se repartía: se copiaba.

La regla que usa Procovar, y que se llevaba a mano en una hoja:

    plan(vendedor, sku) = venta(vendedor, sku, mes anterior)
                          ─────────────────────────────────  ×  meta_global(sku)
                          venta(TODOS, sku, mes anterior)

Es **por SKU**, no por vendedor: el denominador es lo que se vendió de ESE
formato entre todos, y el multiplicador es la meta global de ESE formato. Un
vendedor que el mes pasado movió el 12,7 % del Parranda 1.5 L se lleva el 12,7 %
de la meta de Parranda 1.5 L, aunque su peso en el total de la oficina sea otro.

Comprobado contra la hoja de septiembre de 2026, celda por celda:

    Gari     P1500   171,90 / 1356,03 × 3168 = 401,60
    Gari     M1500    52,20 /  352,17 ×  792 = 117,39
    Gari     M330     11,10 /   81,68 ×  196 =  26,64
    Tadyslai P1500   169,56 / 1356,03 × 3168 = 396,13
    Claudia  M1500    58,05 /  352,17 ×  792 = 130,55

La meta del vendedor NO se decide aparte: es la suma de sus planes por SKU. En la
hoja, los totales que salen de esta cuenta son exactamente las metas que ya están
guardadas (Gari 545,63 · Tadyslai 558,76 · Claudia 554,55).
"""
from __future__ import annotations


def _num(v) -> float:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return 0.0
    return n if n == n and n not in (float("inf"), float("-inf")) else 0.0


def repartir_plan_sku(
    ventas_anterior: dict[str, dict[str, float]],
    metas_globales: dict[str, float],
    formatos: list[str] | None = None,
) -> dict:
    """Reparte la meta global de cada SKU entre los vendedores.

    `ventas_anterior`: {gestor: {formato: HL vendidos el mes anterior}}
    `metas_globales`:  {formato: HL que hay que vender este mes, en total}

    Devuelve el plan por gestor, los totales del mes anterior (que es lo que
    hace auditable el reparto) y `sin_base`: los formatos que NO se pudieron
    repartir.
    """
    fmts = list(formatos) if formatos else sorted(
        {f for g in ventas_anterior.values() for f in g} | set(metas_globales)
    )

    totales = {
        f: round(sum(_num((ventas_anterior.get(g) or {}).get(f)) for g in ventas_anterior), 4)
        for f in fmts
    }

    por_gestor: dict[str, dict[str, float]] = {}
    sin_base: list[str] = []

    for f in fmts:
        meta = _num(metas_globales.get(f))
        total = totales.get(f, 0.0)

        # NADIE vendió ese formato el mes pasado y aun así hay meta.
        #
        # No hay proporción que repartir —cualquier reparto sería inventado— así que se
        # deja en cero y se DICE, para que quien planifica lo meta a mano. Repartirlo por
        # partes iguales parecería un dato calculado y nadie volvería a mirarlo.
        if meta > 0 and total <= 0:
            sin_base.append(f)

    for g, ventas in ventas_anterior.items():
        fila: dict[str, float] = {}
        for f in fmts:
            meta = _num(metas_globales.get(f))
            total = totales.get(f, 0.0)
            v = _num((ventas or {}).get(f))
            fila[f] = round(v / total * meta, 2) if (meta > 0 and total > 0) else 0.0
        por_gestor[g] = fila

    return {
        "formatos": fmts,
        "por_gestor": por_gestor,
        "totales_anterior": totales,
        "metas_globales": {f: round(_num(metas_globales.get(f)), 2) for f in fmts},
        "total_por_gestor": {g: round(sum(fila.values()), 2) for g, fila in por_gestor.items()},
        "sin_base": sin_base,
    }
