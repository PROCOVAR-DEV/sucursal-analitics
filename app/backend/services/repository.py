"""Repositorio persistente de reportes subidos, aislado por sucursal (parquet + index)."""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from services.loader import ReportData, STD_COLS


DEDUPE_KEYS = [STD_COLS["op"], STD_COLS["fecha"], STD_COLS["socio"],
               STD_COLS["merc"], STD_COLS["cant"], STD_COLS["importe"]]


@dataclass
class StoredUpload:
    id: str
    filename: str
    uploaded_at: str
    rango: str
    filas: int
    date_min: str | None
    date_max: str | None


class OverlapError(Exception):
    def __init__(self, message: str, conflicts: list[dict]):
        super().__init__(message)
        self.conflicts = conflicts


def _df_to_report(df: pd.DataFrame, filename: str) -> ReportData:
    fecha = STD_COLS["fecha"]
    date_min = date_max = None
    if fecha in df.columns:
        valid = pd.to_datetime(df[fecha], errors="coerce").dropna()
        valid = valid[valid.dt.year >= 2000]
        if not valid.empty:
            date_min, date_max = valid.min(), valid.max()
    return ReportData(df=df, date_min=date_min, date_max=date_max, filename=filename)


def _df_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].astype("string")
    return out


def _ranges_overlap(a_min, a_max, b_min, b_max) -> bool:
    if any(v is None for v in (a_min, a_max, b_min, b_max)):
        return False
    return not (a_max < b_min or b_max < a_min)


class UploadRepository:
    def __init__(self, base_dir: Path):
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ---------- rutas por sucursal ----------
    def _suc_dir(self, sid: str) -> Path:
        d = self._base / "uploads" / sid
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _index_path(self, sid: str) -> Path:
        return self._suc_dir(sid) / "index.json"

    def _parquet_path(self, sid: str, uid: str) -> Path:
        return self._suc_dir(sid) / f"{uid}.parquet"

    def _load_index(self, sid: str) -> list[dict]:
        p = self._index_path(sid)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_index(self, sid: str, items: list[dict]) -> None:
        self._index_path(sid).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_df(self, sid: str, uid: str) -> pd.DataFrame:
        p = self._parquet_path(sid, uid)
        if not p.exists():
            return pd.DataFrame()
        df = pd.read_parquet(p)
        fecha = STD_COLS["fecha"]
        if fecha in df.columns:
            df[fecha] = pd.to_datetime(df[fecha], errors="coerce")
        return df

    # ---------- conflictos ----------
    def find_conflicts(self, sid: str, filename: str, date_min, date_max) -> list[dict]:
        dmin = pd.Timestamp(date_min) if date_min is not None else None
        dmax = pd.Timestamp(date_max) if date_max is not None else None
        out: list[dict] = []
        for item in self._load_index(sid):
            same_name = bool(filename and item.get("filename") == filename)
            i_min = pd.Timestamp(item["date_min"]) if item.get("date_min") else None
            i_max = pd.Timestamp(item["date_max"]) if item.get("date_max") else None
            overlap = _ranges_overlap(dmin, dmax, i_min, i_max)
            if same_name or overlap:
                out.append({**item, "conflict_reason": "mismo_nombre" if same_name and not overlap else
                            ("fechas_solapadas" if overlap and not same_name else "mismo_nombre_y_fechas")})
        return out

    # ---------- ops ----------
    def add(self, sid: str, report: ReportData, force: bool = False) -> StoredUpload:
        conflicts = self.find_conflicts(sid, report.filename, report.date_min, report.date_max)
        if conflicts and not force:
            names = ", ".join(f"{c['filename']} ({c['rango']})" for c in conflicts)
            raise OverlapError(
                f"Este archivo se solapa con uno ya subido: {names}. "
                f"Elimina el anterior o reenvía con force=true para sobrescribir.", conflicts=conflicts)
        if conflicts and force:
            for c in conflicts:
                self.delete(sid, c["id"])
        with self._lock:
            uid = uuid.uuid4().hex
            df = _df_for_parquet(report.df)
            df.to_parquet(self._parquet_path(sid, uid), index=False)
            stored = StoredUpload(
                id=uid, filename=report.filename,
                uploaded_at=datetime.utcnow().isoformat(timespec="seconds"),
                rango=report.rango_str, filas=int(len(df)),
                date_min=report.date_min.isoformat() if report.date_min is not None else None,
                date_max=report.date_max.isoformat() if report.date_max is not None else None)
            items = self._load_index(sid)
            items.append(stored.__dict__)
            items.sort(key=lambda x: x.get("date_min") or "")
            self._save_index(sid, items)
            return stored

    def list(self, sid: str) -> list[StoredUpload]:
        return [StoredUpload(**x) for x in self._load_index(sid)]

    def get(self, sid: str, uid: str) -> ReportData | None:
        df = self._load_df(sid, uid)
        if df.empty:
            return None
        item = next((x for x in self._load_index(sid) if x["id"] == uid), None)
        return _df_to_report(df, filename=item["filename"] if item else uid)

    def delete(self, sid: str, uid: str) -> bool:
        with self._lock:
            items = self._load_index(sid)
            new_items = [x for x in items if x["id"] != uid]
            if len(new_items) == len(items):
                return False
            self._save_index(sid, new_items)
            p = self._parquet_path(sid, uid)
            if p.exists():
                p.unlink()
            return True

    def reset(self, sid: str) -> None:
        with self._lock:
            d = self._suc_dir(sid)
            for p in d.glob("*.parquet"):
                p.unlink()
            self._save_index(sid, [])

    def accumulated(self, sid: str) -> ReportData | None:
        items = self._load_index(sid)
        if not items:
            return None
        dfs = [self._load_df(sid, it["id"]) for it in items]
        dfs = [d for d in dfs if not d.empty]
        if not dfs:
            return None
        merged = pd.concat(dfs, ignore_index=True)
        keys = [k for k in DEDUPE_KEYS if k in merged.columns]
        if keys:
            merged = merged.drop_duplicates(subset=keys, keep="last")
        sort_keys = [c for c in [STD_COLS["fecha"], STD_COLS["op"]] if c in merged.columns]
        if sort_keys:
            merged = merged.sort_values(by=sort_keys)
        merged = merged.reset_index(drop=True)
        return _df_to_report(merged, filename=f"Acumulado ({len(items)} archivos)")


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
repository = UploadRepository(DATA_DIR)
