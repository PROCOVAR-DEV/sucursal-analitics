"""Configuración editable: metas globales por defecto + metas por mes/año."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pandas as pd

from core.constants import (
    GESTORES_CONFIG,
    GESTORES_PERMITIDOS,
    META_DINERO_TOTAL,
    META_HECTOLITROS_TOTAL,
    METAS_PRODUCTOS_CES,
)


def _default_gestores() -> dict:
    return {
        g: {
            "nombre": GESTORES_CONFIG[g]["nombre"],
            "sector": GESTORES_CONFIG[g]["sector"],
            "cuota_hl": float(GESTORES_CONFIG[g]["cuota_hl"]),
            "cuota_ccc": float(GESTORES_CONFIG[g]["cuota_ccc"]),
        }
        for g in GESTORES_PERMITIDOS
    }


def default_config() -> dict:
    """Configuración por defecto (fallback cuando un mes no tiene override)."""
    return {
        "meta_hectolitros_total": float(META_HECTOLITROS_TOTAL),
        "meta_dinero_total": float(META_DINERO_TOTAL),
        "metas_productos_ces": {k: float(v) for k, v in METAS_PRODUCTOS_CES.items()},
        "gestores": _default_gestores(),
        "trabaja_sabado": False,
        # key = "YYYY-MM" → overrides parciales del mes
        "metas_mensuales": {},
    }


def period_key(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def config_for_period(cfg: dict, year: int | None, month: int | None) -> dict:
    """Devuelve la configuración efectiva para un (año, mes) concreto.

    Las metas de HL, dinero y productos CES pueden tener override mensual;
    los gestores y trabaja_sabado son globales.
    """
    base = {
        "meta_hectolitros_total": cfg.get("meta_hectolitros_total", META_HECTOLITROS_TOTAL),
        "meta_dinero_total": cfg.get("meta_dinero_total", META_DINERO_TOTAL),
        "metas_productos_ces": dict(cfg.get("metas_productos_ces") or METAS_PRODUCTOS_CES),
        "gestores": cfg.get("gestores") or _default_gestores(),
        "trabaja_sabado": bool(cfg.get("trabaja_sabado", False)),
    }
    if year is None or month is None:
        return base
    key = period_key(year, month)
    monthly = (cfg.get("metas_mensuales") or {}).get(key) or {}
    if "meta_hectolitros_total" in monthly:
        base["meta_hectolitros_total"] = float(monthly["meta_hectolitros_total"])
    if "meta_dinero_total" in monthly:
        base["meta_dinero_total"] = float(monthly["meta_dinero_total"])
    if "metas_productos_ces" in monthly and isinstance(monthly["metas_productos_ces"], dict):
        merged = dict(base["metas_productos_ces"])
        merged.update({k: float(v) for k, v in monthly["metas_productos_ces"].items()})
        base["metas_productos_ces"] = merged
    base["_period"] = key
    return base


def config_for_report(cfg: dict, report) -> dict:
    """Atajo: extrae (año, mes) del ReportData y devuelve config efectiva."""
    if report is not None and getattr(report, "date_min", None) is not None:
        d = pd.Timestamp(report.date_min)
        return config_for_period(cfg, d.year, d.month)
    return config_for_period(cfg, None, None)


class SettingsStore:
    def __init__(self, base_dir: Path):
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)
        self._path = base_dir / "settings.json"
        self._lock = threading.Lock()

    def _merge_with_defaults(self, data: dict) -> dict:
        merged = default_config()
        for k in ("meta_hectolitros_total", "meta_dinero_total", "trabaja_sabado"):
            if k in data:
                merged[k] = data[k]
        if isinstance(data.get("metas_productos_ces"), dict):
            merged["metas_productos_ces"] = {k: float(v) for k, v in data["metas_productos_ces"].items()}
        if isinstance(data.get("gestores"), dict):
            g_default = _default_gestores()
            g_stored = data["gestores"]
            merged["gestores"] = {
                g: {**g_default.get(g, {}), **(g_stored.get(g, {}) or {})}
                for g in GESTORES_PERMITIDOS
            }
        if isinstance(data.get("metas_mensuales"), dict):
            clean: dict = {}
            for k, v in data["metas_mensuales"].items():
                if isinstance(v, dict):
                    clean[k] = {
                        **({"meta_hectolitros_total": float(v["meta_hectolitros_total"])}
                           if "meta_hectolitros_total" in v else {}),
                        **({"meta_dinero_total": float(v["meta_dinero_total"])}
                           if "meta_dinero_total" in v else {}),
                        **({"metas_productos_ces":
                            {pk: float(pv) for pk, pv in v["metas_productos_ces"].items()}}
                           if isinstance(v.get("metas_productos_ces"), dict) else {}),
                    }
            merged["metas_mensuales"] = clean
        return merged

    def load(self) -> dict:
        with self._lock:
            if not self._path.exists():
                cfg = default_config()
                self._path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                return cfg
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                return default_config()
        return self._merge_with_defaults(data)

    def save(self, cfg: dict) -> dict:
        current = self.load()
        for k in ("meta_hectolitros_total", "meta_dinero_total", "trabaja_sabado"):
            if k in cfg:
                current[k] = cfg[k]
        if isinstance(cfg.get("metas_productos_ces"), dict):
            current["metas_productos_ces"] = {k: float(v) for k, v in cfg["metas_productos_ces"].items()}
        if isinstance(cfg.get("gestores"), dict):
            for g in GESTORES_PERMITIDOS:
                incoming = cfg["gestores"].get(g) or {}
                base = current["gestores"].get(g, {})
                current["gestores"][g] = {**base, **incoming}
        if isinstance(cfg.get("metas_mensuales"), dict):
            merged = dict(current.get("metas_mensuales") or {})
            for k, v in cfg["metas_mensuales"].items():
                if v is None:
                    merged.pop(k, None)
                elif isinstance(v, dict):
                    merged[k] = {**(merged.get(k) or {}), **v}
            current["metas_mensuales"] = merged
        with self._lock:
            self._path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        return current

    def save_monthly(self, key: str, monthly: dict | None) -> dict:
        """Atajo para actualizar o borrar el override de un mes."""
        return self.save({"metas_mensuales": {key: monthly}})

    def reset(self) -> dict:
        with self._lock:
            cfg = default_config()
            self._path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            return cfg


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
settings_store = SettingsStore(DATA_DIR)
