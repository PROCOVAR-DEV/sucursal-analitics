"""Traer de Ventra las ventas y guardarlas, para que las pantallas no dependan de la VPN.

# Por qué se guarda en vez de preguntar cada vez

Un año de una sucursal son ~50.000 líneas, al otro lado de una VPN que se cae. Pedirlo en
cada carga de pantalla es lento cuando funciona e imposible cuando no. Se trae una vez y se
guarda; los informes leen de la base.

# Dos modos

  al_dia()        los últimos días de las diez bases. Barato, se puede correr cada hora.
  recuperar(...)  el histórico, mes a mes y base a base. Se lanza a mano la primera vez.

Los dos son **idempotentes**: la clave es `(database, linea_id)` con el `id` que da Ventra,
así que repetir un tramo reescribe lo mismo encima. Eso es lo que permite cortar la
recuperación por la mitad y volver a lanzarla sin pensar.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert

from services import ventra
from services.db import VentaVentra, session_scope
from services.loader import STD_COLS

log = logging.getLogger(__name__)

# Cuántos días atrás mira el modo al día. Tres, porque una factura puede entrar en Ventra
# con un día o dos de retraso y el barrido tiene que alcanzarla.
DIAS_AL_DIA = 3


def _filas(df, base: str) -> list[dict]:
    """Del DataFrame a filas de la tabla. Las que no traen fecha se descartan.

    Sin fecha, una línea no se puede filtrar por período ni ordenar: entraría en la base
    para no salir en ningún informe, que es peor que no entrar.
    """
    if df.empty:
        return []

    filas = []

    for _, r in df.iterrows():
        fecha = r[STD_COLS["fecha"]]

        if fecha is None or (hasattr(fecha, "__class__") and str(fecha) == "NaT"):
            continue
        op = r[STD_COLS["op"]]
        filas.append(
            {
                # Ventra no manda el `id` en el DataFrame —lo deja fuera el mapeo—, así
                # que la identidad se compone de la operación y el producto, que es lo que
                # de verdad distingue una línea de otra dentro de una factura.
                "linea_id": int(r.get("_linea_id") or 0),
                "database": base,
                "fecha": fecha.to_pydatetime() if hasattr(fecha, "to_pydatetime") else fecha,
                "oper_number": "" if op is None else str(op),
                "socio": str(r[STD_COLS["socio"]] or ""),
                "mercancia": str(r[STD_COLS["merc"]] or ""),
                "grupo": str(r[STD_COLS["grupo"]] or ""),
                "cantidad": float(r[STD_COLS["cant"]] or 0),
                "importe": float(r[STD_COLS["importe"]] or 0),
                "nota": r[STD_COLS["nota"]],
                "objeto": str(r[ventra.COL_OBJETO] or ""),
                "tipo_punto": str(r[ventra.COL_TIPO_PUNTO] or ""),
                "traido_at": datetime.utcnow(),
            }
        )

    return filas


def guardar(filas: list[dict]) -> int:
    """Escribe las líneas. Repetir un tramo reescribe lo mismo, no duplica.

    `ON CONFLICT (database, linea_id) DO UPDATE` y no `DO NOTHING`: si Ventra corrige una
    factura —cambia una cantidad, anula una línea—, la corrección tiene que entrar. Con
    `DO NOTHING` nos quedaríamos con la primera versión para siempre y nadie lo notaría.
    """
    if not filas:
        return 0

    with session_scope() as s:
        # En tandas: un `INSERT` de cincuenta mil filas de una vez se come la memoria y
        # bloquea la tabla más de lo necesario.
        TANDA = 1000
        total = 0

        for i in range(0, len(filas), TANDA):
            tanda = filas[i : i + TANDA]
            stmt = pg_insert(VentaVentra).values(tanda)
            stmt = stmt.on_conflict_do_update(
                index_elements=["database", "linea_id"],
                set_={
                    c: stmt.excluded[c]
                    for c in (
                        "fecha", "oper_number", "socio", "mercancia", "grupo",
                        "cantidad", "importe", "nota", "objeto", "tipo_punto", "traido_at",
                    )
                },
            )
            s.execute(stmt)
            total += len(tanda)

    return total


def _traer(base: str, desde: date, hasta: date) -> tuple[int, int, float]:
    """Un tramo de una base. Devuelve (guardadas, sin vendedor, importe sin vendedor)."""
    crudas = ventra.ventas_crudas(base, desde, hasta)
    df = ventra.a_dataframe(crudas, base=base)

    # El `id` de Ventra es la identidad de la línea y `a_dataframe` no lo lleva: se pega
    # aquí, en el mismo orden, filtrando igual que allí.
    ids = [c.get("id") for c in crudas
           if c.get("operType") is None or int(c["operType"]) == ventra.OPER_TYPE_VENTA]
    if not df.empty and len(ids) == len(df):
        df = df.assign(_linea_id=ids)

    n = guardar(_filas(df, base))
    sin_v, importe_sin_v = ventra.sin_vendedor(df)

    return n, sin_v, importe_sin_v


def al_dia(dias: int = DIAS_AL_DIA) -> dict[str, int]:
    """Los últimos días de todas las bases. Es lo que corre solo, cada hora."""
    hasta = date.today()
    desde = hasta - timedelta(days=dias)
    salida: dict[str, int] = {}

    for b in ventra.bases():
        nombre = b["database"]
        try:
            n, sin_v, imp = _traer(nombre, desde, hasta)
            salida[nombre] = n
            aviso = f" · {sin_v} sin vendedor ({imp:.2f})" if sin_v else ""
            log.info("[ventra] %s: %d lineas %s..%s%s", nombre, n, desde, hasta, aviso)
        except ventra.VentraNoDisponible as e:
            # Una base que falla no para las demás: puede ser que esté caída, y las otras
            # nueve sucursales no tienen por qué quedarse sin datos por eso.
            salida[nombre] = -1
            log.warning("[ventra] %s fallo: %s", nombre, e)

    return salida


def _meses(desde: date, hasta: date):
    """Los tramos de un mes entre dos fechas. Ventra no pagina: hay que trocear."""
    cur = date(desde.year, desde.month, 1)

    while cur <= hasta:
        sig = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
        yield max(cur, desde), min(sig - timedelta(days=1), hasta)
        cur = sig


def recuperar(desde: date, hasta: date | None = None, base: str | None = None) -> int:
    """El histórico, mes a mes y base a base.

    Se hace así y no de un tirón porque Ventra no pagina —sólo acepta `limit`— y porque un
    tramo que falla tiene que poder reintentarse solo, sin arrastrar a los demás.
    """
    hasta = hasta or date.today()
    objetivo = [{"database": base}] if base else ventra.bases()
    total = 0

    for b in objetivo:
        nombre = b["database"]

        for ini, fin in _meses(desde, hasta):
            try:
                n, sin_v, imp = _traer(nombre, ini, fin)
                total += n
                aviso = f" · {sin_v} sin vendedor ({imp:.2f})" if sin_v else ""
                log.info("[ventra] %s %s: %d lineas%s", nombre, ini.strftime("%Y-%m"), n, aviso)
            except ventra.VentraNoDisponible as e:
                log.warning("[ventra] %s %s fallo: %s", nombre, ini.strftime("%Y-%m"), e)

    return total


def bucle(cada_s: int = 3600, dias: int = DIAS_AL_DIA) -> None:
    """Trae lo de los últimos días, cada hora, para siempre.

    Es un bucle y no una tarea programada porque Dokploy no expone programaciones por
    API: teniéndolo dentro, el worker se despliega como cualquier otra aplicación.

    Nunca revienta. Ventra está al otro lado de una VPN que se cae, y un worker que se
    muere en el primer fallo deja de traer datos hasta que alguien lo mira — que suele
    ser cuando alguien pregunta por qué los informes están viejos.
    """
    import time

    # Margen al arrancar: durante el despliegue la VPN puede no estar lista, y un fallo
    # en el primer segundo no dice nada de si esto funciona.
    time.sleep(int(os.environ.get("VENTRA_ESPERA_INICIAL_S", "60")))

    while True:
        try:
            r = al_dia(dias)
            vivas = {k: v for k, v in r.items() if v >= 0}
            caidas = [k for k, v in r.items() if v < 0]
            log.info(
                "[ventra] %d lineas de %d bases%s",
                sum(vivas.values()), len(vivas),
                f" · fallaron {', '.join(caidas)}" if caidas else "",
            )
        except Exception as e:  # noqa: BLE001
            log.exception("[ventra] la pasada fallo entera: %s", e)
        time.sleep(cada_s)


if __name__ == "__main__":  # pragma: no cover
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    p = argparse.ArgumentParser(description="Traer las ventas de Ventra")
    p.add_argument("--desde", help="AAAA-MM-DD: recupera el histórico desde esa fecha")
    p.add_argument("--hasta", help="AAAA-MM-DD (por defecto, hoy)")
    p.add_argument("--base", help="una sola base de Ventra (por defecto, todas)")
    p.add_argument("--dias", type=int, default=DIAS_AL_DIA, help="modo al día")
    p.add_argument("--bucle", action="store_true", help="quedarse corriendo cada hora")
    p.add_argument("--cada", type=int, default=3600, help="segundos entre pasadas")
    a = p.parse_args()

    if a.bucle:
        log.info("[ventra] worker en marcha: cada %d s, %d dias atras", a.cada, a.dias)
        bucle(a.cada, a.dias)
    elif a.desde:
        n = recuperar(
            date.fromisoformat(a.desde),
            date.fromisoformat(a.hasta) if a.hasta else None,
            a.base,
        )
        log.info("recuperacion terminada: %d lineas", n)
    else:
        log.info("al dia: %s", al_dia(a.dias))
