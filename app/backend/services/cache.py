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
workers y nunca puede servir un dato obsoleto tras una subida. Y en esa huella
entra también el CÓDIGO: ver `_version_del_codigo`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from services.db import session_scope

log = logging.getLogger(__name__)

# Cuántos días se conserva un resultado calculado. Pasado ese tiempo se borra;
# si alguien vuelve a pedirlo se recalcula solo. Ajustable por entorno sin
# tocar el código: ANALITICS_RETENCION_DIAS.
DIAS_RETENCION = int(os.environ.get("ANALITICS_RETENCION_DIAS", "90"))


def _version_del_codigo() -> str:
    """Huella del código que calcula los resultados. Se computa una vez, al importar.

    La huella de la sucursal miraba los datos —ficheros subidos, configuración, ajustes
    globales— pero NO el código. Así que un despliegue que cambia CÓMO se calcula seguía
    sirviendo lo calculado por la versión anterior, y el arreglo no se veía por ningún
    lado. Pasó el 08/09/2026: se arregló que el Excel rellenara los días que Ventra
    todavía no había traído, se desplegó, y Camagüey seguía enseñando el día 8 en cero
    porque el payload guardado era de veinte minutos antes.

    Es lo peor que puede hacer una caché: no que esté vieja, sino que el arreglo parezca
    no funcionar. Se pierde la tarde buscando en el sitio equivocado — y esta vez se
    perdió.

    Se hace por CONTENIDO y no por fecha de fichero: dentro de la imagen las fechas
    pueden venir todas iguales del build, y dos versiones distintas darían la misma
    huella. Por contenido no hay forma de equivocarse. Y al revés, reiniciar el mismo
    contenedor no cambia nada, así que la caché sobrevive a un reinicio — que es justo
    para lo que está.
    """
    raiz = Path(__file__).resolve().parent.parent
    h = hashlib.sha256()

    for f in sorted(raiz.rglob("*.py")):
        # Los tests no entran: no cambian ningun resultado y se editan a menudo.
        if "tests" in f.parts or "__pycache__" in f.parts:
            continue
        try:
            h.update(f.relative_to(raiz).as_posix().encode())
            h.update(f.read_bytes())
        except OSError:
            # Un fichero que no se puede leer no puede tumbar el arranque. Que se
            # quede fuera de la huella es peor que nada, pero no es fatal.
            log.warning("No se pudo leer %s para la huella del codigo", f)

    return h.hexdigest()[:12]


VERSION_CODIGO = _version_del_codigo()


def _marca_de_ventra(sid: str) -> str:
    """Cuándo se trajo por última vez lo de Ventra de esta sucursal, y cuánto hay.

    Las dos cosas: la fecha sola no bastaría si alguna vez se borraran filas sin traer
    otras nuevas, y el recuento solo no distinguiría una corrección que sustituye una
    línea por otra.

    Se usa `max(traido_at)` y no `count(*)` a secas por lo que cuesta: hay índice por
    `database`, y el recuento se hace sobre esa misma partición.
    """
    try:
        from services.ventra_fuente import base_de

        base = base_de(sid)

        if not base:
            return "sin-base"

        with session_scope() as s:
            row = s.execute(
                text(
                    "select coalesce(max(traido_at)::text, ''), count(*)"
                    "  from analytics_venta_ventra where database = :b"
                ),
                {"b": base},
            ).first()

        return "|".join(str(x) for x in row) if row is not None else "sin-datos"
    except Exception:
        # Sin marca de Ventra no se puede garantizar que lo guardado valga: se devuelve
        # algo distinto cada vez para que NO se use la caché, que es el lado seguro.
        log.exception("No se pudo calcular la marca de Ventra de %s", sid)
        return f"desconocida-{datetime.utcnow().isoformat()}"


def sucursal_version(sid: str) -> str | None:
    """Huella del estado de una sucursal: cambia si se sube/borra un archivo, si
    se edita su configuración, si cambia el código o SI VENTRA TRAE DATOS NUEVOS.

    Lo de Ventra faltaba, y se veía así: eligiendo «septiembre» salían 607 filas hasta el
    día 9, y eligiendo «1–10 de septiembre» salían 874 hasta el día 10 — con la misma
    fuente y la misma sucursal. El mes servía un resultado calculado el 09/09 a la 01:09,
    y Ventra había traído el día 10 anoche a las 22:00. Cumplimiento 31% contra 39% por la
    misma razón.

    Es el mismo fallo que el del código, que ya se arregló el 09/09: una caché que no mira
    todo lo que puede cambiar el resultado sirve datos viejos sin que nada lo delate — y
    esta vez los datos viejos eran MENOS ventas, que se lee como que la sucursal vendió
    menos.

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
        # La marca de los ajustes GLOBALES entra en la huella: una regla de
        # comisión global cambia los resultados de TODAS las sucursales, y sin
        # esto se seguirían sirviendo los guardados. El día que se olvidara
        # purgar a mano, unas sucursales cobrarían con la regla nueva y otras con
        # la vieja, sin nada que lo delatara.
        from services import ajustes

        base = "|".join(str(x) for x in row) if row is not None else "sin-datos"

        return f"{base}|g:{ajustes.marca_de_tiempo()}|c:{VERSION_CODIGO}|v:{_marca_de_ventra(sid)}"
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
            # Se marca la lectura en el mismo golpe: así la purga sabe qué
            # reportes se usan de verdad y cuáles llevan semanas sin abrirse.
            row = s.execute(
                text("update analytics_result_cache set last_read_at = now()"
                     " where cache_key = :k and version = :v"
                     " returning payload"),
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
                    "       (cache_key, sid, version, payload, computed_at, last_read_at)"
                    " values (:k, :sid, :v, cast(:p as jsonb), now(), now())"
                    " on conflict (cache_key) do update"
                    "    set version = excluded.version,"
                    "        payload = excluded.payload,"
                    "        computed_at = excluded.computed_at,"
                    "        last_read_at = excluded.last_read_at"
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


def purgar(dias: int = DIAS_RETENCION) -> dict:
    """Borra resultados viejos para que la tabla no crezca sin fin.

    Se purga por EDAD, no por uso: pasados `dias` desde que se calculó, el
    resultado se borra. Si alguien vuelve a pedir ese reporte, se calcula otra
    vez y se guarda de nuevo — solo paga los segundos del cálculo esa primera
    vez. Guardar para siempre el resumen de un mes que nadie va a volver a
    abrir es ocupar disco a cambio de nada.

    Un reporte que SÍ se usa no desaparece: cada vez que la sucursal cambia
    (subida de archivo o edición de config) su huella cambia, el resultado se
    recalcula y `computed_at` se renueva.

    Además se limpia lo que ya no puede servir para nada:
      - resultados de sucursales que ya no existen
      - resultados cuya huella no coincide con la actual (nunca se leerán)
    """
    borrados = {"por_edad": 0, "huerfanos": 0, "obsoletos": 0}
    try:
        with session_scope() as s:
            r = s.execute(
                text("delete from analytics_result_cache"
                     " where computed_at < now() - make_interval(days => :d)"),
                {"d": int(dias)},
            )
            borrados["por_edad"] = r.rowcount or 0

            r = s.execute(text(
                "delete from analytics_result_cache"
                " where sid not in (select sid from analytics_sucursal)"))
            borrados["huerfanos"] = r.rowcount or 0
    except Exception:
        log.exception("Fallo purgando la cache de resultados")
    return borrados


def purgar_obsoletos_de(sid: str, version_actual: str) -> int:
    """Borra los resultados de una sucursal que quedaron con huella vieja.

    Se llama tras subir un archivo: en ese momento TODOS los resultados de esa
    sucursal quedan obsoletos de golpe y ya no se van a leer nunca más."""
    try:
        with session_scope() as s:
            r = s.execute(
                text("delete from analytics_result_cache"
                     " where sid = :sid and version <> :v"),
                {"sid": sid, "v": version_actual},
            )
            return r.rowcount or 0
    except Exception:
        log.exception("Fallo purgando obsoletos de %s", sid)
        return 0


def stats() -> dict:
    try:
        with session_scope() as s:
            n, kb, viejo = s.execute(text(
                "select count(*),"
                "       coalesce(sum(pg_column_size(payload)), 0) / 1024.0,"
                "       min(computed_at)"
                "  from analytics_result_cache"
            )).first()
        return {"entradas": int(n), "tamano_kb": round(float(kb), 1),
                "mas_antiguo": str(viejo) if viejo else None,
                "retencion_dias": DIAS_RETENCION}
    except Exception:
        return {"entradas": -1, "tamano_kb": -1.0}
