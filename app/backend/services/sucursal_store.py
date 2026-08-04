"""Almacén de sucursales: toda la configuración dinámica del sistema.

Cada sucursal tiene su propia config (gestores, metas, parámetros, overrides
mensuales). Todo es editable en caliente desde la API. Se persiste en un único
JSON (`data/sucursales.json`).
"""
from __future__ import annotations

import copy
import json
import logging
import re
import threading
import unicodedata
from pathlib import Path

import pandas as pd

from services.db import session_scope, Sucursal
from core.constants import (
    COMISION_GESTOR_PCT,
    COMISION_SUPERVISOR_PCT,
    CURVA_VENTA,
    DEFAULT_GESTORES,
    FRECUENCIA,
    GROUPS_ORDER,
    META_CCC_TOTAL,
    META_DINERO_TOTAL,
    META_HECTOLITROS_TOTAL,
    METAS_PRODUCTOS_CES,
    PRODUCT_GROUPS_KEYWORDS,
    SIZE_MULT,
    SIZES,
    UNITS_PER_PALLET,
)


log = logging.getLogger(__name__)


def slugify(name: str) -> str:
    t = unicodedata.normalize("NFKD", str(name))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t or "sucursal"


def default_parametros() -> dict:
    return {
        "size_mult": {k: float(v) for k, v in SIZE_MULT.items()},
        "units_per_pallet": {k: int(v) for k, v in UNITS_PER_PALLET.items()},
        "sizes": list(SIZES),
        "comision_gestor_pct": COMISION_GESTOR_PCT,
        "comision_supervisor_pct": COMISION_SUPERVISOR_PCT,
        "descuento_sin_pedido": 0.0,   # $ a descontar por cada venta sin pedido (Nota con V- y sin P-)
        # Reglas de comisión por producto/grupo con vigencia por mes. Vacío = solo
        # se aplica `comision_gestor_pct` a todo, que es el comportamiento de
        # siempre. Ver services/comisiones.py.
        "reglas_comision": [],
        "trabaja_sabado": False,
        "trabaja_domingo": False,
        "curva_venta": dict(CURVA_VENTA),
        "frecuencia": dict(FRECUENCIA),
        "product_groups_keywords": {k: list(v) for k, v in PRODUCT_GROUPS_KEYWORDS.items()},
        "groups_order": list(GROUPS_ORDER),
    }


def default_metas() -> dict:
    return {
        "meta_hectolitros_total": float(META_HECTOLITROS_TOTAL),
        "meta_dinero_total": float(META_DINERO_TOTAL),
        "meta_ccc_total": float(META_CCC_TOTAL),
        "metas_productos_ces": {k: float(v) for k, v in METAS_PRODUCTOS_CES.items()},
    }


def default_sucursal_config(nombre: str, sid: str | None = None, seed_gestores: bool = True) -> dict:
    sid = sid or slugify(nombre)
    gestores = {
        k: {
            "nombre": v["nombre"], "agencia": v["agencia"], "sector": v["sector"],
            "cuota_hl": float(v["cuota_hl"]), "cuota_ccc": float(v["cuota_ccc"]),
            "aliases": list(v.get("aliases", [])), "activo": True,
        }
        for k, v in (DEFAULT_GESTORES.items() if seed_gestores else [])
    }
    return {
        "id": sid,
        "nombre": nombre,
        "supervisor_nombre": nombre,
        "gestores": gestores,
        "metas": default_metas(),
        "parametros": default_parametros(),
        "metas_mensuales": {},   # "YYYY-MM" -> override parcial de metas
    }


def period_key(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def config_for_period(suc: dict, year: int | None, month: int | None) -> dict:
    """Aplana la config de una sucursal para un (año, mes) concreto.

    Devuelve un dict con claves planas que consumen los servicios de negocio.
    Solo las metas admiten override mensual; gestores y parámetros son globales.
    """
    metas = dict(suc.get("metas") or default_metas())
    params = {**default_parametros(), **(suc.get("parametros") or {})}

    # Las reglas de comisión son la suma de las GLOBALES (valen para todas las
    # sucursales) y las propias. Se juntan aquí, en el único sitio por el que
    # pasa toda la configuración, para que ningún servicio pueda quedarse con la
    # mitad: uno que leyera solo las propias calcularía comisiones distintas del
    # de al lado sin que nada lo delatara.
    #
    # Cada una lleva marcado su ámbito, que es lo que decide quién manda cuando
    # dos apuntan a lo mismo (ver services/comisiones.py).
    try:
        from services import ajustes
        from services.comisiones import AMBITO_GLOBAL, AMBITO_SUCURSAL

        globales = [{**r, "ambito": AMBITO_GLOBAL} for r in ajustes.reglas_comision_globales()]
        propias = [{**r, "ambito": AMBITO_SUCURSAL} for r in (params.get("reglas_comision") or [])]
        params["reglas_comision"] = globales + propias
    except Exception:  # pragma: no cover - si falla, se sigue con las propias
        log.exception("No se pudieron leer las reglas de comisión globales")
    eff = {
        "id": suc.get("id"),
        "nombre": suc.get("nombre"),
        "supervisor_nombre": suc.get("supervisor_nombre") or suc.get("nombre"),
        "gestores": suc.get("gestores") or {},
        "meta_hectolitros_total": float(metas.get("meta_hectolitros_total", META_HECTOLITROS_TOTAL)),
        "meta_dinero_total": float(metas.get("meta_dinero_total", META_DINERO_TOTAL)),
        "meta_ccc_total": float(metas.get("meta_ccc_total", META_CCC_TOTAL)),
        "metas_productos_ces": dict(metas.get("metas_productos_ces") or METAS_PRODUCTOS_CES),
        **params,
        "_period": None,
    }
    if year is not None and month is not None:
        key = period_key(year, month)
        monthly = (suc.get("metas_mensuales") or {}).get(key) or {}
        if "meta_hectolitros_total" in monthly:
            eff["meta_hectolitros_total"] = float(monthly["meta_hectolitros_total"])
        if "meta_dinero_total" in monthly:
            eff["meta_dinero_total"] = float(monthly["meta_dinero_total"])
        if "meta_ccc_total" in monthly:
            eff["meta_ccc_total"] = float(monthly["meta_ccc_total"])
        if isinstance(monthly.get("metas_productos_ces"), dict):
            merged = dict(eff["metas_productos_ces"])
            merged.update({k: float(v) for k, v in monthly["metas_productos_ces"].items()})
            eff["metas_productos_ces"] = merged
        # Roster + metas por vendedor del mes: el mes puede fijar cuotas/metas por
        # vendedor. Se combinan identidad global + cuotas/metas del mes.
        if isinstance(monthly.get("gestores"), dict) and monthly["gestores"]:
            global_g = eff["gestores"] or {}
            roster: dict = {}
            for clave, ov in monthly["gestores"].items():
                base = dict(global_g.get(clave) or {"nombre": clave})
                if isinstance(ov, dict):
                    if "cuota_hl" in ov:
                        base["cuota_hl"] = float(ov["cuota_hl"])
                    if "cuota_ccc" in ov:
                        base["cuota_ccc"] = float(ov["cuota_ccc"])
                    if isinstance(ov.get("metas_formato"), dict):
                        base["metas_formato"] = {str(k): float(v) for k, v in ov["metas_formato"].items()}
                base["activo"] = True
                roster[clave] = base
            # Un gestor ACTIVO en el global pero ausente del roster del mes (ej. se
            # agregó después de fijar las metas del mes — como un supervisor que también
            # vende) igual debe aparecer y que se le atribuyan sus ventas. Se suma con su
            # config global (sin meta del mes) en vez de quedar invisible en todas las
            # vistas por vendedor. Las metas del mes siguen aplicando a los del roster.
            for clave, gv in global_g.items():
                if clave not in roster and (gv or {}).get("activo", True):
                    base = dict(gv)
                    base["activo"] = True
                    roster[clave] = base
            eff["gestores"] = roster
        eff["_period"] = key
    return eff


def config_accumulated(suc: dict, months: list) -> dict:
    """Config efectiva ACUMULADA sobre varios meses: suma las metas de cada mes
    (cuota por vendedor, totales y productos) y une los rosters. Así el acumulado
    global no muestra la meta de un solo mes."""
    months = sorted(set((int(y), int(m)) for y, m in months))
    if not months:
        return config_for_period(suc, None, None)
    if len(months) == 1:
        return config_for_period(suc, months[0][0], months[0][1])
    effs = [config_for_period(suc, y, m) for (y, m) in months]
    base = dict(effs[0])
    base["meta_hectolitros_total"] = round(sum(e["meta_hectolitros_total"] for e in effs), 2)
    base["meta_dinero_total"] = round(sum(e["meta_dinero_total"] for e in effs), 2)
    base["meta_ccc_total"] = round(sum(e["meta_ccc_total"] for e in effs), 2)
    prod: dict = {}
    for e in effs:
        for k, v in (e.get("metas_productos_ces") or {}).items():
            prod[k] = round(prod.get(k, 0.0) + float(v), 2)
    base["metas_productos_ces"] = prod
    gest: dict = {}
    for e in effs:
        for k, gv in (e.get("gestores") or {}).items():
            if k not in gest:
                gest[k] = {**gv, "cuota_hl": 0.0, "cuota_ccc": 0.0}
            gest[k]["cuota_hl"] = round(gest[k]["cuota_hl"] + float(gv.get("cuota_hl", 0)), 2)
            gest[k]["cuota_ccc"] = round(gest[k]["cuota_ccc"] + float(gv.get("cuota_ccc", 0)), 2)
    base["gestores"] = gest
    base["_period"] = None
    base["_accumulated"] = True
    base["_meses"] = len(months)
    return base


def config_for_report(suc: dict, report) -> dict:
    if report is not None and getattr(report, "date_min", None) is not None:
        months = report_months(report)
        if months:
            return config_accumulated(suc, months)
        d = pd.Timestamp(report.date_min)
        return config_for_period(suc, d.year, d.month)
    return config_for_period(suc, None, None)


def report_months(report) -> list:
    """Meses (año, mes) presentes en el reporte."""
    try:
        fechas = pd.to_datetime(report.df["Fecha"], errors="coerce").dropna()
        return sorted({(int(d.year), int(d.month)) for d in fechas})
    except Exception:
        return []


class SucursalStore:
    """Config de sucursales sobre postgres (tabla analytics_sucursal, config en JSONB).

    Interfaz idéntica a la versión JSON: los métodos devuelven el MISMO dict de config
    (con claves `id`, `nombre`, `supervisor_nombre`, `gestores`, `metas`, `parametros`,
    `metas_mensuales`). La lógica de merge se conserva exacta; solo cambia el I/O.
    """

    def __init__(self, base_dir: Path | str | None = None):
        # base_dir se conserva por compat; ya NO se usa (la config vive en postgres).
        self._ensure_seed()

    # ---------- helpers ----------
    @staticmethod
    def _to_dict(row: Sucursal) -> dict:
        # id y nombre viven en columnas; el resto en config (JSONB). Se re-arma el dict
        # completo tal como lo esperaban los consumidores de la versión JSON.
        # deepcopy: si se compartieran los dicts anidados con row.config, una mutación
        # in-place (ej. suc["metas"][x]=...) también tocaría el snapshot "viejo" de
        # SQLAlchemy y NO se detectaría el cambio → no se guardaría.
        return {**copy.deepcopy(row.config or {}), "id": row.sid, "nombre": row.nombre}

    def _persist(self, s, sid: str, suc: dict) -> None:
        nombre = suc.get("nombre", suc.get("id", sid))
        body = {k: v for k, v in suc.items() if k not in ("id", "nombre")}
        row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
        if row is None:
            s.add(Sucursal(sid=sid, nombre=nombre, config=body))
        else:
            row.nombre = nombre
            row.config = body

    def _ensure_seed(self) -> None:
        with session_scope() as s:
            if s.query(Sucursal).count() == 0:
                suc = default_sucursal_config("Camagüey", sid="camaguey", seed_gestores=True)
                self._persist(s, "camaguey", suc)

    # ---------- sucursales ----------
    def list(self) -> list[dict]:
        with session_scope() as s:
            rows = s.query(Sucursal).all()
            out = [self._to_dict(r) for r in rows]
        return sorted(out, key=lambda x: x.get("nombre", ""))

    def list_summary(self) -> list[dict]:
        return [
            {"id": s["id"], "nombre": s["nombre"],
             "gestores": len([g for g in (s.get("gestores") or {}).values() if g.get("activo", True)])}
            for s in self.list()
        ]

    def get(self, sid: str) -> dict | None:
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            return self._to_dict(row) if row else None

    def exists(self, sid: str) -> bool:
        return self.get(sid) is not None

    def create(self, nombre: str, seed_gestores: bool = False) -> dict:
        with session_scope() as s:
            existing = {r[0] for r in s.query(Sucursal.sid).all()}
            sid = slugify(nombre)
            base = sid
            i = 2
            while sid in existing:
                sid = f"{base}-{i}"
                i += 1
            suc = default_sucursal_config(nombre, sid=sid, seed_gestores=seed_gestores)
            self._persist(s, sid, suc)
        return self.get(sid)

    def update(self, sid: str, patch: dict) -> dict | None:
        """Actualiza campos de nivel superior: nombre, supervisor_nombre, metas,
        parametros, metas_mensuales (merge superficial e inteligente)."""
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            if row is None:
                return None
            suc = self._to_dict(row)
            for k in ("nombre", "supervisor_nombre"):
                if k in patch and patch[k]:
                    suc[k] = patch[k]
            if isinstance(patch.get("metas"), dict):
                suc.setdefault("metas", default_metas())
                for mk, mv in patch["metas"].items():
                    if mk == "metas_productos_ces" and isinstance(mv, dict):
                        suc["metas"]["metas_productos_ces"] = {k: float(v) for k, v in mv.items()}
                    elif mv is not None:
                        suc["metas"][mk] = float(mv)
            if isinstance(patch.get("parametros"), dict):
                suc.setdefault("parametros", default_parametros())
                suc["parametros"].update(patch["parametros"])
            if isinstance(patch.get("metas_mensuales"), dict):
                mm = dict(suc.get("metas_mensuales") or {})
                for k, v in patch["metas_mensuales"].items():
                    if v is None:
                        mm.pop(k, None)
                    elif isinstance(v, dict):
                        cur = dict(mm.get(k) or {})
                        for kk, vv in v.items():
                            if kk == "gestores" and isinstance(vv, dict):
                                cg = {gk: dict(gv) for gk, gv in (cur.get("gestores") or {}).items()}
                                for clave, ov in vv.items():
                                    cg[clave] = {**(cg.get(clave) or {}), **ov}
                                cur["gestores"] = cg
                            elif kk == "metas_productos_ces" and isinstance(vv, dict):
                                cur["metas_productos_ces"] = {**(cur.get("metas_productos_ces") or {}), **vv}
                            else:
                                cur[kk] = vv
                        mm[k] = cur
                suc["metas_mensuales"] = mm
            self._persist(s, sid, suc)
        return self.get(sid)

    def delete(self, sid: str) -> bool:
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            if row is None:
                return False
            s.delete(row)
            return True

    # ---------- gestores (CRUD dinámico) ----------
    def upsert_gestor(self, sid: str, clave: str, cfg: dict) -> dict | None:
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            if row is None:
                return None
            suc = self._to_dict(row)
            clave = str(clave).upper().strip()
            gestores = suc.setdefault("gestores", {})
            existing = gestores.get(clave, {})
            gestores[clave] = {
                "nombre": cfg.get("nombre", existing.get("nombre", clave)),
                "agencia": cfg.get("agencia", existing.get("agencia", suc.get("nombre", ""))),
                "sector": cfg.get("sector", existing.get("sector", "")),
                "cuota_hl": float(cfg.get("cuota_hl", existing.get("cuota_hl", 0.0))),
                "cuota_ccc": float(cfg.get("cuota_ccc", existing.get("cuota_ccc", 0.0))),
                "aliases": list(cfg.get("aliases", existing.get("aliases", []))),
                "activo": bool(cfg.get("activo", existing.get("activo", True))),
                "metas_formato": {
                    str(k): float(v)
                    for k, v in (cfg.get("metas_formato", existing.get("metas_formato", {})) or {}).items()
                },
            }
            self._persist(s, sid, suc)
        return self.get(sid)

    def rename_gestor(self, sid: str, clave: str, nueva_clave: str) -> dict | None:
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            if row is None:
                return None
            suc = self._to_dict(row)
            gestores = suc.setdefault("gestores", {})
            clave = str(clave).upper().strip()
            nueva_clave = str(nueva_clave).upper().strip()
            if clave in gestores and nueva_clave and nueva_clave != clave:
                gestores[nueva_clave] = gestores.pop(clave)
                self._persist(s, sid, suc)
        return self.get(sid)

    def delete_gestor(self, sid: str, clave: str) -> dict | None:
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            if row is None:
                return None
            suc = self._to_dict(row)
            suc.get("gestores", {}).pop(str(clave).upper().strip(), None)
            self._persist(s, sid, suc)
        return self.get(sid)

    # ------------------------------------------------- reglas de comisión (CRUD)
    #
    # Las reglas viven dentro de `parametros` porque son configuración de la
    # sucursal como cualquier otra, y así viajan solas en el export/import y en
    # el reset. No se les hace tabla propia: son pocas, se leen enteras siempre,
    # y una tabla obligaría a un JOIN en cada cálculo para nada.

    def reglas_comision(self, sid: str) -> list[dict]:
        suc = self.get(sid) or {}
        return list((suc.get("parametros") or {}).get("reglas_comision") or [])

    def guardar_reglas_comision(self, sid: str, reglas: list[dict]) -> dict | None:
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            if row is None:
                return None
            suc = self._to_dict(row)
            suc.setdefault("parametros", {})["reglas_comision"] = list(reglas)
            self._persist(s, sid, suc)
        return self.get(sid)

    def reset(self, sid: str) -> dict | None:
        """Restaura metas y parámetros por defecto (mantiene gestores y nombre)."""
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            if row is None:
                return None
            suc = self._to_dict(row)
            suc["metas"] = default_metas()
            suc["parametros"] = default_parametros()
            suc["metas_mensuales"] = {}
            self._persist(s, sid, suc)
        return self.get(sid)


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
sucursal_store = SucursalStore(DATA_DIR)
