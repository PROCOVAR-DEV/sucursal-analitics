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
