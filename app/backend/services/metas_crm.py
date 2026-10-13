"""Las metas de venta viven en la base del CRM (Jose, 13/10/2026).

«La base de datos del CRM es la que tiene las metas, y se manejan desde Analytics.»
Las pantallas no cambian: la calculadora y Configuración → Metas siguen escribiendo
lo mismo. Lo que cambia es DÓNDE se guarda. Con `CRM_METAS_DATABASE_URL` puesta, la
parte de metas de cada sucursal se lee y se escribe en `procovar_crm` (tablas
`metas_venta_*`, migración 026 del CRM), directo con SQL y con un usuario que sólo
puede tocar esas tablas. No pasa por la API del CRM. Sin la variable, todo sigue en
`analytics_sucursal.config` como siempre.

Qué es META y se mueve (todo lo demás se queda en Analytics):

    metas                          totales base de la sucursal, metas_productos_ces, formatos
    metas_mensuales[AAAA-MM]       lo mismo por mes, más el roster del mes con sus cuotas
    gestores[CLAVE].cuota_hl/...   cuota_hl, cuota_ccc, metas_formato, metas_cantidad

La identidad del gestor (nombre, alias, agencia, baja, sin_meta, supervisor) es del
roster de Analytics y NO se mueve: casa las ventas de Ventra, no es una meta.

Analytics sigue guardando también su copia en el JSONB (`SucursalStore._persist`
escribe la config entera, como antes). La que manda al LEER es la del CRM; la copia
sólo está para poder volver atrás quitando la variable.

Modelo y despliegue: `docs/2026-10-13-metas-en-la-base-del-crm.md` del CRM.
"""
from __future__ import annotations

import os
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from services.db import _conectar_reintentando

# Slug de Analytics -> código de sucursal de Accesos / CRM. Las que no tienen código
# (Moa, Palma Soriano, cualquiera que se dé de alta) van con su slug tal cual.
CODIGO_SUCURSAL = {
    "camaguey": "CAM",
    "granma": "GR",
    "guantanamo": "GTO",
    "habana": "HAB",
    "la-habana": "HAB",
    "holguin": "HOL",
    "sancti-spiritus": "SS",
    "santiago-de-cuba": "STG",
    "las-tunas": "TUN",
}

TOTALES = ("meta_hectolitros_total", "meta_dinero_total", "meta_ccc_total")
CLAVES_GESTOR = ("cuota_hl", "cuota_ccc", "metas_formato", "metas_cantidad")
_PERIODO = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")

# (tabla, clave primaria, columnas de valor). En este orden se insertan; al revés se borran.
_TABLAS = (
    ("metas_venta_sucursal", ("sucursal", "periodo"),
     ("meta_hectolitros_total", "meta_dinero_total", "meta_ccc_total", "formatos")),
    ("metas_venta_producto", ("sucursal", "periodo", "producto"), ("cantidad",)),
    ("metas_venta_gestor", ("sucursal", "periodo", "gestor"),
     ("cuota_hl", "cuota_ccc", "metas_formato_fijadas", "metas_cantidad_fijadas")),
    ("metas_venta_gestor_formato", ("sucursal", "periodo", "gestor", "formato"), ("hectolitros",)),
    ("metas_venta_gestor_producto", ("sucursal", "periodo", "gestor", "producto"), ("cantidad",)),
)


def _url() -> str:
    return os.environ.get("CRM_METAS_DATABASE_URL", "").strip()


def activo() -> bool:
    return bool(_url())


def codigo(sid: str) -> str:
    return CODIGO_SUCURSAL.get(sid, sid)


_ENGINES: dict = {}


def _engine():
    url = _url()
    if url not in _ENGINES:
        # psycopg2 escrito a mano, por lo mismo que en services/db.py.
        _ENGINES[url] = create_engine(
            make_url(url).set(drivername="postgresql+psycopg2"),
            creator=lambda: _conectar_reintentando(url),
            pool_pre_ping=True,
            future=True,
        )
    return _ENGINES[url]


# ------------------------------------------------------------------ forma canónica

def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mapa(d) -> dict:
    return {str(k): _num(v) for k, v in (d or {}).items() if _num(v) is not None}


def _gestor(g: dict) -> dict:
    out = {k: _num(g[k]) for k in ("cuota_hl", "cuota_ccc") if _num(g.get(k)) is not None}
    for k in ("metas_formato", "metas_cantidad"):
        # Presente aunque esté vacío: en un mes, `{}` es «sin desglose» y no tenerlo es
        # «el de la base» (ver `config_for_period`).
        if isinstance(g.get(k), dict):
            out[k] = _mapa(g[k])
    return out


def separar(suc: dict) -> tuple[dict, list[str]]:
    """La parte de metas de una config de Analytics, en la forma en que la devuelve `leer`.

    Devuelve también lo que NO cabe en el modelo (claves desconocidas, meses mal
    escritos), para que la copia lo enseñe en vez de perderlo callando.
    """
    avisos: list[str] = []
    parte: dict = {"metas_mensuales": {}, "gestores": {}}

    m = suc.get("metas")
    if isinstance(m, dict):
        base = {k: _num(m[k]) for k in TOTALES if _num(m.get(k)) is not None}
        base["metas_productos_ces"] = _mapa(m.get("metas_productos_ces"))
        base["formatos"] = [str(f) for f in (m.get("formatos") or [])]
        parte["metas"] = base
        avisos += [f"metas.{k}" for k in m if k not in (*TOTALES, "metas_productos_ces", "formatos")]

    for clave, g in (suc.get("gestores") or {}).items():
        cg = _gestor(g or {})
        if cg:
            parte["gestores"][clave] = cg

    for per, mes in (suc.get("metas_mensuales") or {}).items():
        if not _PERIODO.fullmatch(str(per)) or not isinstance(mes, dict):
            avisos.append(f"metas_mensuales.{per}")
            continue
        out = {k: _num(mes[k]) for k in TOTALES if _num(mes.get(k)) is not None}
        prods = _mapa(mes.get("metas_productos_ces"))
        if prods:
            out["metas_productos_ces"] = prods
        gs = {}
        for clave, ov in (mes.get("gestores") or {}).items():
            if not isinstance(ov, dict):
                avisos.append(f"metas_mensuales.{per}.gestores.{clave}")
                continue
            gs[clave] = _gestor(ov)  # vacío también: estar en el roster del mes ya es dato
            avisos += [f"metas_mensuales.{per}.gestores.{clave}.{k}" for k in ov if k not in CLAVES_GESTOR]
        if gs:
            out["gestores"] = gs
        avisos += [f"metas_mensuales.{per}.{k}" for k in mes
                   if k not in (*TOTALES, "metas_productos_ces", "gestores")]
        parte["metas_mensuales"][per] = out
    return parte, avisos


def juntar(suc: dict, parte: dict) -> dict:
    """La config de Analytics con las metas sustituidas por las del CRM."""
    out = {k: v for k, v in suc.items() if k not in ("metas", "metas_mensuales")}
    out["gestores"] = {c: {k: v for k, v in (g or {}).items() if k not in CLAVES_GESTOR}
                       for c, g in (suc.get("gestores") or {}).items()}
    if "metas" in parte:
        out["metas"] = parte["metas"]
    out["metas_mensuales"] = parte["metas_mensuales"]
    for c, g in parte["gestores"].items():
        # Una cuota base de alguien que ya no está en el roster no resucita a nadie.
        if c in out["gestores"]:
            out["gestores"][c].update(g)
    return out


# ------------------------------------------------------------------ base del CRM

def leer(sid: str) -> dict:
    s = codigo(sid)
    with _engine().connect() as c:
        def q(tabla: str, cols: str):
            return c.execute(text(f"select periodo, {cols} from {tabla} where sucursal = :s"), {"s": s}).mappings().all()

        sucs = q("metas_venta_sucursal", "meta_hectolitros_total, meta_dinero_total, meta_ccc_total, formatos")
        prods = q("metas_venta_producto", "producto, cantidad")
        gests = q("metas_venta_gestor", "gestor, cuota_hl, cuota_ccc, metas_formato_fijadas, metas_cantidad_fijadas")
        fmts = q("metas_venta_gestor_formato", "gestor, formato, hectolitros")
        cants = q("metas_venta_gestor_producto", "gestor, producto, cantidad")

    parte: dict = {"metas_mensuales": {}, "gestores": {}}

    def periodo(p: str) -> dict:
        return parte["metas"] if p == "" else parte["metas_mensuales"].setdefault(p, {})

    def gestores(p: str) -> dict:
        return parte["gestores"] if p == "" else periodo(p).setdefault("gestores", {})

    for r in sucs:
        d = {k: float(r[k]) for k in TOTALES if r[k] is not None}
        if r["periodo"] == "":
            parte["metas"] = {**d, "metas_productos_ces": {}, "formatos": list(r["formatos"] or [])}
        else:
            parte["metas_mensuales"][r["periodo"]] = d
    for r in prods:
        periodo(r["periodo"]).setdefault("metas_productos_ces", {})[r["producto"]] = float(r["cantidad"])
    for r in gests:
        g = {k: float(r[k]) for k in ("cuota_hl", "cuota_ccc") if r[k] is not None}
        if r["metas_formato_fijadas"]:
            g["metas_formato"] = {}
        if r["metas_cantidad_fijadas"]:
            g["metas_cantidad"] = {}
        gestores(r["periodo"])[r["gestor"]] = g
    for filas, campo, col, val in ((fmts, "metas_formato", "formato", "hectolitros"),
                                   (cants, "metas_cantidad", "producto", "cantidad")):
        for r in filas:
            gestores(r["periodo"])[r["gestor"]].setdefault(campo, {})[r[col]] = float(r[val])
    return parte


def _filas(s: str, parte: dict) -> dict[str, list[dict]]:
    filas: dict[str, list[dict]] = {t: [] for t, _, _ in _TABLAS}

    def periodo(p: str, d: dict) -> None:
        filas["metas_venta_sucursal"].append({
            "sucursal": s, "periodo": p, **{k: d.get(k) for k in TOTALES},
            "formatos": list(d.get("formatos") or []) if p == "" else None,
        })
        filas["metas_venta_producto"] += [
            {"sucursal": s, "periodo": p, "producto": k, "cantidad": v}
            for k, v in (d.get("metas_productos_ces") or {}).items()]

    def gestores(p: str, gs: dict) -> None:
        for c, g in gs.items():
            filas["metas_venta_gestor"].append({
                "sucursal": s, "periodo": p, "gestor": c,
                "cuota_hl": g.get("cuota_hl"), "cuota_ccc": g.get("cuota_ccc"),
                "metas_formato_fijadas": "metas_formato" in g,
                "metas_cantidad_fijadas": "metas_cantidad" in g,
            })
            filas["metas_venta_gestor_formato"] += [
                {"sucursal": s, "periodo": p, "gestor": c, "formato": k, "hectolitros": v}
                for k, v in (g.get("metas_formato") or {}).items()]
            filas["metas_venta_gestor_producto"] += [
                {"sucursal": s, "periodo": p, "gestor": c, "producto": k, "cantidad": v}
                for k, v in (g.get("metas_cantidad") or {}).items()]

    if "metas" in parte:
        periodo("", parte["metas"])
    gestores("", parte["gestores"])
    for p, d in parte["metas_mensuales"].items():
        periodo(p, d)
        gestores(p, d.get("gestores") or {})
    return filas


def guardar(sid: str, parte: dict) -> None:
    """Deja en el CRM exactamente `parte` para esa sucursal, en una transacción.

    Borra lo que ya no está e inserta o actualiza lo demás. Una fila que no cambia no
    se toca, así `updated_at` y `row_version` dicen algo de verdad.
    """
    s = codigo(sid)
    filas = _filas(s, parte)
    with _engine().begin() as c:
        # Dos guardados de la misma sucursal a la vez se esperan en vez de pisarse.
        c.execute(text("select pg_advisory_xact_lock(hashtext(:k))"), {"k": "metas_venta:" + s})
        for tabla, claves, _ in reversed(_TABLAS):
            nuevas = {tuple(f[k] for k in claves) for f in filas[tabla]}
            viejas = c.execute(text(f"select {', '.join(claves)} from {tabla} where sucursal = :s"), {"s": s}).all()
            sobran = [dict(zip(claves, v)) for v in map(tuple, viejas) if v not in nuevas]
            if sobran:
                c.execute(text(f"delete from {tabla} where " + " and ".join(f"{k} = :{k}" for k in claves)), sobran)
        for tabla, claves, valores in _TABLAS:
            if not filas[tabla]:
                continue
            cols = claves + valores
            c.execute(text(
                f"insert into {tabla} ({', '.join(cols)}) values ({', '.join(':' + k for k in cols)})"
                f" on conflict ({', '.join(claves)}) do update set "
                + ", ".join(f"{v} = excluded.{v}" for v in valores)
                + f" where ({', '.join(f'{tabla}.{v}' for v in valores)})"
                f" is distinct from ({', '.join('excluded.' + v for v in valores)})"
            ), filas[tabla])


def borrar(sid: str) -> None:
    guardar(sid, {"metas_mensuales": {}, "gestores": {}})
