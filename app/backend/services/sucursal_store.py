"""Almacén de sucursales: toda la configuración dinámica del sistema.

Cada sucursal tiene su propia config (gestores, metas, parámetros, overrides
mensuales). Todo es editable en caliente desde la API. Se persiste en un único
JSON (`data/sucursales.json`).
"""
from __future__ import annotations

import json
import re
import threading
import unicodedata
from pathlib import Path

import pandas as pd

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
        # Roster + metas por vendedor del mes: si el mes define gestores, SOLO esos
        # vendedores existen ese mes (un gestor que entró después no sale en meses
        # anteriores). Se combinan identidad global + cuotas/metas del mes.
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
    def __init__(self, base_dir: Path):
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)
        self._path = base_dir / "sucursales.json"
        self._lock = threading.RLock()
        self._ensure_seed()

    # ---------- persistencia ----------
    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {s["id"]: s for s in data} if isinstance(data, list) else data
        except Exception:
            return {}

    def _write(self, data: dict) -> None:
        self._path.write_text(
            json.dumps(list(data.values()), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _ensure_seed(self) -> None:
        with self._lock:
            data = self._read()
            if not data:
                suc = default_sucursal_config("Camagüey", sid="camaguey", seed_gestores=True)
                self._write({suc["id"]: suc})

    # ---------- sucursales ----------
    def list(self) -> list[dict]:
        with self._lock:
            return sorted(self._read().values(), key=lambda s: s.get("nombre", ""))

    def list_summary(self) -> list[dict]:
        return [
            {"id": s["id"], "nombre": s["nombre"],
             "gestores": len([g for g in (s.get("gestores") or {}).values() if g.get("activo", True)])}
            for s in self.list()
        ]

    def get(self, sid: str) -> dict | None:
        with self._lock:
            return self._read().get(sid)

    def exists(self, sid: str) -> bool:
        return self.get(sid) is not None

    def create(self, nombre: str, seed_gestores: bool = False) -> dict:
        with self._lock:
            data = self._read()
            sid = slugify(nombre)
            base = sid
            i = 2
            while sid in data:
                sid = f"{base}-{i}"
                i += 1
            suc = default_sucursal_config(nombre, sid=sid, seed_gestores=seed_gestores)
            data[sid] = suc
            self._write(data)
            return suc

    def update(self, sid: str, patch: dict) -> dict | None:
        """Actualiza campos de nivel superior: nombre, supervisor_nombre, metas,
        parametros, metas_mensuales (merge superficial e inteligente)."""
        with self._lock:
            data = self._read()
            suc = data.get(sid)
            if suc is None:
                return None
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
            data[sid] = suc
            self._write(data)
            return suc

    def delete(self, sid: str) -> bool:
        with self._lock:
            data = self._read()
            if sid not in data:
                return False
            del data[sid]
            self._write(data)
            return True

    # ---------- gestores (CRUD dinámico) ----------
    def upsert_gestor(self, sid: str, clave: str, cfg: dict) -> dict | None:
        with self._lock:
            data = self._read()
            suc = data.get(sid)
            if suc is None:
                return None
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
            data[sid] = suc
            self._write(data)
            return suc

    def rename_gestor(self, sid: str, clave: str, nueva_clave: str) -> dict | None:
        with self._lock:
            data = self._read()
            suc = data.get(sid)
            if suc is None:
                return None
            gestores = suc.setdefault("gestores", {})
            clave = str(clave).upper().strip()
            nueva_clave = str(nueva_clave).upper().strip()
            if clave in gestores and nueva_clave and nueva_clave != clave:
                gestores[nueva_clave] = gestores.pop(clave)
                data[sid] = suc
                self._write(data)
            return suc

    def delete_gestor(self, sid: str, clave: str) -> dict | None:
        with self._lock:
            data = self._read()
            suc = data.get(sid)
            if suc is None:
                return None
            suc.get("gestores", {}).pop(str(clave).upper().strip(), None)
            data[sid] = suc
            self._write(data)
            return suc

    def reset(self, sid: str) -> dict | None:
        """Restaura metas y parámetros por defecto (mantiene gestores y nombre)."""
        with self._lock:
            data = self._read()
            suc = data.get(sid)
            if suc is None:
                return None
            suc["metas"] = default_metas()
            suc["parametros"] = default_parametros()
            suc["metas_mensuales"] = {}
            data[sid] = suc
            self._write(data)
            return suc


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
sucursal_store = SucursalStore(DATA_DIR)
