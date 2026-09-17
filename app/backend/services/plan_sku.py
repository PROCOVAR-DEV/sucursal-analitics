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
    por_cabeza: set[str] | None = None,
) -> dict:
    """Reparte la meta global de cada SKU entre los vendedores.

    `ventas_anterior`: {gestor: {formato: HL vendidos el mes anterior}}
    `metas_globales`:  {formato: HL que hay que vender este mes, en total}

    Devuelve el plan por gestor, los totales del mes anterior (que es lo que
    hace auditable el reparto) y `sin_base`: los formatos que NO se pudieron
    repartir.
    """
    # Los formatos que se piden, MÁS cualquiera que traiga meta y no esté en la lista.
    #
    # Antes `formatos` mandaba y punto, así que una meta de un formato que no estuviera
    # en esa lista se evaporaba sin aparecer siquiera en `sin_base` — la misma forma del
    # fallo que ya salió cuatro veces: dinero que no se reparte y nadie lo ve.
    base = list(formatos) if formatos else sorted(
        {f for g in ventas_anterior.values() for f in g}
    )
    fmts = base + [f for f in sorted(metas_globales) if f not in base]

    # Las devoluciones (ventas negativas) NO restan del reparto.
    #
    # Sin esto, a quien devolvió más de lo que vendió le salía un plan NEGATIVO —«vende
    # menos 25 HL»— y el resto se repartía de más para compensar. Una devolución es un
    # hecho contable, no una parte negativa de un objetivo: cuenta como cero.
    def venta(g: str, f: str) -> float:
        return max(0.0, _num((ventas_anterior.get(g) or {}).get(f)))

    totales = {f: round(sum(venta(g, f) for g in ventas_anterior), 4) for f in fmts}

    por_gestor: dict[str, dict[str, float]] = {g: {} for g in ventas_anterior}
    sin_base: list[str] = []

    for f in fmts:
        meta = _num(metas_globales.get(f))
        total = totales.get(f, 0.0)

        # Una meta NEGATIVA no es cero: es imposible. Antes `meta > 0` la dejaba caer
        # sin dejar rastro — 200 HL tragados por un signo de menos al teclear.
        if meta < 0:
            sin_base.append(f)
            for g in por_gestor:
                por_gestor[g][f] = 0.0
            continue

        """
        NADIE vendió ese formato el mes pasado, y aun así hay meta: se reparte POR CABEZA.

        No es 0 × algo, es 0 ÷ 0 — en Excel sale `#¡DIV/0!`. No hay proporción que
        aplicar, así que antes se dejaba en cero y se avisaba. Pero eso deja los HL
        **sin dueño**: la suma de los planes ya no da la meta global y la sucursal
        arranca el mes debiendo un objetivo que no está en la meta de nadie.

        Decisión de Sidney (17/09/2026): repartirlos a partes iguales entre los
        comerciales, excepto los que no llevan cuota. Lo segundo ya está resuelto —
        quien llega aquí en `ventas_anterior` es exactamente quien recibe, porque los
        `sin_meta`, los de baja y los desmarcados salieron antes (`roster.quien_recibe`).
        Por eso aquí NO hay ningún nombre propio, y no puede haberlo: un nombre escrito
        en la fórmula se pudre el día que esa persona cambie de puesto.

        Se sigue avisando, porque un reparto por cabeza no es lo mismo que un reparto
        por ventas y quien planifica tiene que saber cuál está mirando.
        """
        """
        POR CABEZA: automático cuando no hay base, y A MANO cuando la base no vale.

        Lo segundo lo pidió Sidney con un caso concreto: p500 se vendió, pero 1,02 HL
        entre toda la sucursal. Repartir un objetivo de 403 «según la parte que tuviste»
        con esa base le daba el 100 % al único que vendió — 1,02 HL convertidos en 403.
        Técnicamente hay base; en la práctica no dice nada.

        No hay un múltiplo mágico a partir del cual una base «deja de valer», y
        inventármelo sería poner una regla de negocio en el código con mi criterio. Así
        que la decisión va donde vive: quien planifica marca ese formato y se reparte
        por cabeza ese mes. El mes siguiente puede ser otro formato, u otro criterio, y
        no hay que tocar nada.
        """
        forzado = f in (por_cabeza or set())

        if meta > 0 and (total <= 0 or forzado):
            if total <= 0:
                sin_base.append(f)
            cuantos = len(por_gestor)
            if cuantos:
                parte = round(meta / cuantos, 2)
                fila = {g: parte for g in por_gestor}
                resto = round(meta - parte * cuantos, 2)
                if resto:
                    mayor = sorted(fila)[0]
                    fila[mayor] = round(fila[mayor] + resto, 2)
                for g, v in fila.items():
                    por_gestor[g][f] = v
                continue

        if not (meta > 0 and total > 0):
            for g in por_gestor:
                por_gestor[g][f] = 0.0
            continue

        crudo = {g: venta(g, f) / total * meta for g in ventas_anterior}
        fila = {g: round(v, 2) for g, v in crudo.items()}

        """
        EL REDONDEO NO PUEDE PERDER HECTOLITROS.

        Redondeando celda a celda, tres vendedores iguales con una meta de 100 se
        llevan 33,33 cada uno: 99,99, y falta un céntimo. Sobre una sucursal real el
        descuadre medido era de hasta 0,06 HL — poco, pero es la misma familia de
        fallo que ya costó cientos: la suma de los planes deja de ser la meta.

        El sobrante se le da al que más lleva, que es a quien menos le mueve la aguja.
        """
        resto = round(meta - sum(fila.values()), 2)
        if resto and fila:
            mayor = max(fila, key=lambda g: (fila[g], g))
            fila[mayor] = round(fila[mayor] + resto, 2)

        for g, v in fila.items():
            por_gestor[g][f] = v

    """
    CUÁNTAS VECES hay que multiplicar lo del mes pasado para llegar a la meta.

    No cambia ningún número: es el dato que hace visible el caso de Javier. Vendió
    1,02 HL de p500 —todo lo que se vendió de ese formato— así que se llevó los 403
    de meta: multiplicar por 395. La cuenta está bien; lo que no sirve es el número.

    Se devuelve en crudo y sin umbral a propósito. Decidir a partir de cuántas veces
    algo «no vale» es una regla de negocio, y esa no me toca inventarla: la pantalla
    avisa, y si algún día hay que bloquear, el umbral lo pone quien planifica.
    """
    multiplicadores = {
        f: round(_num(metas_globales.get(f)) / totales[f], 1)
        for f in fmts
        if totales.get(f, 0.0) > 0 and _num(metas_globales.get(f)) > 0
    }

    return {
        "formatos": fmts,
        "multiplicadores": multiplicadores,
        # Los que se repartieron a partes iguales, por lo que sea: porque no había base
        # o porque quien planifica lo marcó. La pantalla lo dice, para que nadie
        # confunda un reparto por cabeza con uno por ventas.
        "por_cabeza": sorted(set(sin_base) | {f for f in fmts if f in (por_cabeza or set()) and _num(metas_globales.get(f)) > 0}),
        "por_gestor": por_gestor,
        "totales_anterior": totales,
        "metas_globales": {f: round(_num(metas_globales.get(f)), 2) for f in fmts},
        "total_por_gestor": {g: round(sum(fila.values()), 2) for g, fila in por_gestor.items()},
        "sin_base": sin_base,
    }
