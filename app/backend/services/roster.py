"""
Quién cuenta en un mes: la baja de un gestor, con fecha.

Aparte de `sucursal_store` porque ahí dentro todo toca la base de datos y esto no
toca nada — son dos líneas de regla y así se pueden probar sin levantar Postgres.
"""
from __future__ import annotations


def filtrar_por_baja(gestores: dict | None, periodo: str | None) -> dict:
    """Quita del roster a los que ya estaban de baja en ese mes.

    `periodo` es `AAAA-MM`. Sin periodo no se filtra a nadie: el acumulado quiere el
    histórico entero.

    **Por qué no vale `activo: false`.** Esa bandera es global y apaga al vendedor en
    TODOS los meses, así que uno que se va desaparece también de los informes de
    cuando sí vendía — y esos informes ya se miraron, se discutieron y se pagaron.
    Eso no es dar de baja, es reescribir el pasado.

    `baja_desde` es el mes A PARTIR DEL CUAL deja de contar, ese incluido. Antes
    sigue entero: sus ventas, su cuota y su comisión. Desde él no aparece, y —lo que
    de verdad importa— **no se le reparte plan de un mes que no va a trabajar**. Su
    trozo de la meta se redistribuye solo entre los que quedan, porque sus ventas
    tampoco entran ya en el denominador.

    Lo pidió Jose el 17/09/2026 por el caso de Amsale: ya no es de Procovar pero
    vendió los primeros días del mes, y esas ventas son reales.
    """
    if not gestores:
        return {}
    if not periodo:
        return dict(gestores)

    return {
        k: g for k, g in gestores.items()
        if not str((g or {}).get("baja_desde") or "").strip() or str(g["baja_desde"]).strip() > periodo
    }


def quien_recibe(roster: dict | None, marcados=()) -> set:
    """Quién se lleva plan este mes. **Devolver un conjunto vacío es una respuesta.**

    Tres formas de quedar fuera, y las tres tienen que sacar a la persona del
    DENOMINADOR, no sólo de recibir: si se le quita el plan pero se le deja abajo en
    la división, su parte se evapora y la suma deja de ser la meta global.

      · `sin_meta` en la configuración del gestor
      · `baja_desde` (ya aplicado por `filtrar_por_baja` al armar el roster del mes)
      · la casilla «EN EL MES» de la pantalla, que llega en `marcados`

    Vive aquí y no en el endpoint porque el endpoint no se puede probar sin FastAPI, y
    una copia del criterio en las pruebas deja de auditar lo que dice auditar en cuanto
    alguien toca el original. Esto ya se rompió cuatro veces por caminos distintos.

    **Vacío significa vacío**: quien llame decide si eso es un error o no reparte a
    nadie, pero nunca «entonces reparte entre todos» — ése fue exactamente el cuarto
    agujero, y medía 3.275 HL de 4.156.
    """
    reciben = {g for g, cfg in (roster or {}).items() if not (cfg or {}).get("sin_meta")}
    pedidos = {g for g in (marcados or ()) if g}
    return reciben & pedidos if pedidos else reciben
