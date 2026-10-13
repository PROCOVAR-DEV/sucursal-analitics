"""Copia de una sola vez: las metas de `analytics_sucursal.config` a la base del CRM.

    python copiar_metas_al_crm.py --dry-run   # enseña qué copiaría, no escribe
    python copiar_metas_al_crm.py             # copia y comprueba leyendo de vuelta

Necesita DATABASE_URL (Analytics) y CRM_METAS_DATABASE_URL (CRM). Lee el JSONB crudo,
no a través de SucursalStore, que con la variable puesta ya leería del CRM.

Idempotente: cada sucursal queda en el CRM EXACTAMENTE como está en Analytics (lo que
sobra allí se borra), así que repetirla no duplica nada. Por lo mismo, NO se corre
después de que alguien haya editado metas directamente en el CRM: las pisaría.

Sale con código 1 si algo no cuadra: dos sucursales con el mismo código, o una que al
leerla de vuelta no da lo mismo que se escribió.
"""
from __future__ import annotations

import argparse
import copy
import sys

from services import metas_crm
from services.db import Sucursal, session_scope


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="enseña lo que copiaría sin escribir")
    args = ap.parse_args(argv)

    if not metas_crm.activo():
        print("Falta CRM_METAS_DATABASE_URL.", file=sys.stderr)
        return 2

    with session_scope() as s:
        filas = [(r.sid, copy.deepcopy(r.config or {})) for r in s.query(Sucursal).order_by(Sucursal.sid)]

    # Dos slugs con el mismo código (habana y la-habana) se pisarían en el CRM.
    por_codigo: dict[str, list[str]] = {}
    for sid, _ in filas:
        por_codigo.setdefault(metas_crm.codigo(sid), []).append(sid)
    choques = {c: sids for c, sids in por_codigo.items() if len(sids) > 1}
    if choques:
        print(f"ERROR: sucursales con el mismo código en el CRM: {choques}. No se copia nada.", file=sys.stderr)
        return 1

    fallos = 0
    for sid, cfg in filas:
        parte, avisos = metas_crm.separar(cfg)
        meses = parte["metas_mensuales"]
        print(f"{sid} -> {metas_crm.codigo(sid)}: base {'sí' if 'metas' in parte else 'no'}, "
              f"{len(parte['gestores'])} gestores con cuota base, {len(meses)} meses, "
              f"{sum(len(m.get('gestores') or {}) for m in meses.values())} cuotas de gestor en meses")
        for a in avisos:
            print(f"   AVISO, no cabe y no se copia: {a}")
        if args.dry_run:
            continue
        metas_crm.guardar(sid, parte)
        if metas_crm.leer(sid) != parte:
            print(f"   ERROR: {sid} leída de vuelta del CRM no da lo mismo", file=sys.stderr)
            fallos += 1

    print("(--dry-run: no se ha escrito nada)" if args.dry_run else
          f"Copiadas {len(filas) - fallos} de {len(filas)} sucursales.")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
