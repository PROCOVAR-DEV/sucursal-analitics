"""Caché de payloads calculados, con invalidación por versión de sucursal.

El Resumen recalculaba TODO en cada carga: leer las filas de la sucursal a un
DataFrame, deduplicar, ordenar y volver a computar ventas, productos, ranking y
análisis de clientes. Con las 27k filas actuales, la vista de "todas las
sucursales" tardaba ~13.5s medidos, y dos peticiones idénticas seguidas
tardaban lo mismo porque no había ningún cacheo.

Nada de ese resultado cambia entre peticiones salvo que se suba/borre un
archivo o se toque la configuración de la sucursal. Así que se cachea el
payload ya calculado y se invalida SOLO cuando esos datos cambian de verdad.

La versión se deriva de la BASE DE DATOS, no de un contador en memoria: así
sigue siendo correcta aunque el backend corra con varios procesos (gunicorn con
workers) o se reinicie, y nunca se sirve un dato viejo tras subir un archivo.
"""

from __future__ import annotations

import copy
import threading

from sqlalchemy import text

from services.db import session_scope

# Se guarda una copia del valor, no la referencia: quien lo reciba puede
# modificarlo sin corromper lo cacheado.
_LOCK = threading.Lock()
_CACHE: dict[tuple, tuple[str, object]] = {}
_MAX_ENTRADAS = 256


def sucursal_version(sid: str) -> str:
    """Huella del estado de una sucursal. Cambia si se sube/borra un archivo o
    si se edita su configuración (metas, gestores, parámetros)."""
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
        # Si la consulta de versión falla, se devuelve una versión única para
        # que NO se use la caché: mejor recalcular que servir algo obsoleto.
        return f"error-{threading.get_ident()}-{len(_CACHE)}"


def get_or_compute(key: tuple, sid: str, fn):
    """Devuelve el valor cacheado si la sucursal no ha cambiado; si no, ejecuta
    `fn()`, lo guarda y lo devuelve."""
    version = sucursal_version(sid)

    with _LOCK:
        entrada = _CACHE.get(key)
        if entrada is not None and entrada[0] == version:
            return copy.deepcopy(entrada[1])

    # El cálculo se hace FUERA del lock: dos peticiones concurrentes pueden
    # calcular lo mismo una vez cada una, pero no se bloquean entre sí.
    valor = fn()

    with _LOCK:
        if len(_CACHE) >= _MAX_ENTRADAS:
            _CACHE.clear()
        _CACHE[key] = (version, copy.deepcopy(valor))
    return valor


def invalidate_all() -> None:
    """Vacía la caché entera. No hace falta para el flujo normal (la versión ya
    invalida sola); está para pruebas y para el endpoint de reset."""
    with _LOCK:
        _CACHE.clear()


def stats() -> dict:
    with _LOCK:
        return {"entradas": len(_CACHE), "maximo": _MAX_ENTRADAS}
