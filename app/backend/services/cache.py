"""Resultados precalculados, guardados en Postgres.

El Resumen recalculaba TODO en cada carga: leer las filas de la sucursal a un
DataFrame, deduplicar, ordenar y volver a computar ventas, productos, ranking y
análisis de clientes. Con las 27k filas actuales, la vista de "todas las
sucursales" tardaba ~14s medidos, y dos peticiones idénticas seguidas tardaban
lo mismo.

Nada de ese resultado cambia entre peticiones salvo que se suba/borre un archivo
o se toque la configuración de la sucursal. Así que se guarda el payload ya
calculado en la tabla `analytics_result_cache` y se recalcula SOLO cuando esos
datos cambian de verdad.

**Por qué en Postgres y no en memoria:** sobrevive a reinicios y despliegues, lo
comparten todos los procesos y réplicas, y no ocupa RAM del servidor. Es además
la base del motor de reportes: aquí es donde acaban los valores precalculados.

La invalidación se basa en una *huella* de la sucursal derivada de la propia
base de datos (no de un contador en memoria), así que es correcta con varios
workers y nunca puede servir un dato obsoleto tras una subida.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

from services.db import session_scope

log = logging.getLogger(__name__)


def sucursal_version(sid: str) -> str | None:
    """Huella del estado de una sucursal: cambia si se sube/borra un archivo o
    si se edita su configuración (metas, gestores, parámetros).

    Devuelve None si no se pudo calcular; en ese caso NO se usa la caché
    (mejor recalcular que arriesgarse a servir algo viejo)."""
    try:
        with session_scope() as s:
            row = s.execute(
                text(
                    "select s.updated_at, count(u.id), coalesce(max(u.uploaded_at), ''),"
                    "       coalesce(sum(u.filas), 0)"
                    "  from analytics_sucursal s"
                    "  left join analytics_upload u on u.sid = s.sid"
                    " where s.sid = :sid"
                    " group by s.updated_at"
                ),
                {"sid": sid},
            ).first()
        return "|".join(str(x) for x in row) if row is not None else "sin-datos"
    except Exception:
        log.exception("No se pudo calcular la version de la sucursal %s", sid)
        return None


def get_or_compute(key: tuple, sid: str, fn):
    """Devuelve el resultado guardado si la sucursal no ha cambiado; si no,
    ejecuta `fn()`, lo guarda en Postgres y lo devuelve."""
    version = sucursal_version(sid)
    if version is None:
        return fn()  # sin huella fiable no se cachea nada

    cache_key = "|".join(str(k) for k in key)

    try:
        with session_scope() as s:
            row = s.execute(
                text("select payload from analytics_result_cache"
                     " where cache_key = :k and version = :v"),
                {"k": cache_key, "v": version},
            ).first()
        if row is not None:
            return row[0]
    except Exception:
        log.exception("Fallo leyendo la cache de %s; se recalcula", cache_key)

    valor = fn()

    try:
        with session_scope() as s:
            # Una fila por clave: al recalcular se pisa la anterior, así la
            # tabla no crece con versiones viejas.
            s.execute(
                text(
                    "insert into analytics_result_cache"
                    "       (cache_key, sid, version, payload, computed_at)"
                    " values (:k, :sid, :v, cast(:p as jsonb), now())"
                    " on conflict (cache_key) do update"
                    "    set version = excluded.version,"
                    "        payload = excluded.payload,"
                    "        computed_at = excluded.computed_at"
                ),
                {"k": cache_key, "sid": sid, "v": version,
                 "p": json.dumps(valor, default=str)},
            )
    except Exception:
        log.exception("Fallo guardando la cache de %s", cache_key)

    return valor


def invalidate_sucursal(sid: str) -> int:
    """Borra los resultados de una sucursal. No hace falta en el flujo normal
    (la huella ya invalida sola); está para el reset y para pruebas."""
    try:
        with session_scope() as s:
            r = s.execute(text("delete from analytics_result_cache where sid = :sid"),
                          {"sid": sid})
            return r.rowcount or 0
    except Exception:
        log.exception("Fallo invalidando la cache de %s", sid)
        return 0


def stats() -> dict:
    try:
        with session_scope() as s:
            n, kb = s.execute(text(
                "select count(*), coalesce(sum(pg_column_size(payload)), 0) / 1024.0"
                "  from analytics_result_cache"
            )).first()
        return {"entradas": int(n), "tamano_kb": round(float(kb), 1)}
    except Exception:
        return {"entradas": -1, "tamano_kb": -1.0}
