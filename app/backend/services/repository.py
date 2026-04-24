"""Repositorio persistente de reportes subidos (parquet + index JSON)."""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from services.loader import ReportData, STD_COLS


DEDUPE_KEYS = [
    STD_COLS["op"],
    STD_COLS["fecha"],
    STD_COLS["socio"],
    STD_COLS["merc"],
    STD_COLS["cant"],
    STD_COLS["importe"],
]


@dataclass
class StoredUpload:
    id: str
    filename: str
    uploaded_at: str  # ISO UTC
    rango: str
    filas: int
    date_min: str | None
    date_max: str | None


class OverlapError(Exception):
    """Se lanza si el rango del archivo nuevo coincide con uno ya existente."""
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
            date_min = valid.min()
            date_max = valid.max()
    return ReportData(df=df, date_min=date_min, date_max=date_max, filename=filename)


def _df_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara el DataFrame para que parquet no falle por tipos mixtos."""
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == object:
            # convertir todo lo que no sea NaN a string para evitar mezclas int/str
            out[c] = out[c].astype("string")
    return out


def _ranges_overlap(a_min, a_max, b_min, b_max) -> bool:
    if any(v is None for v in (a_min, a_max, b_min, b_max)):
        return False
    return not (a_max < b_min or b_max < a_min)


class UploadRepository:
    def __init__(self, base_dir: Path):
        self._base = base_dir
        self._uploads_dir = base_dir / "uploads"
        self._index_path = base_dir / "index.json"
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ---------- index ----------
    def _load_index(self) -> list[dict]:
        if not self._index_path.exists():
            return []
        try:
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_index(self, items: list[dict]) -> None:
        self._index_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- parquet ----------
    def _parquet_path(self, uid: str) -> Path:
        return self._uploads_dir / f"{uid}.parquet"

    def _load_df(self, uid: str) -> pd.DataFrame:
        p = self._parquet_path(uid)
        if not p.exists():
            return pd.DataFrame()
        df = pd.read_parquet(p)
        fecha = STD_COLS["fecha"]
        if fecha in df.columns:
            df[fecha] = pd.to_datetime(df[fecha], errors="coerce")
        return df

    # ---------- consultas auxiliares ----------
    def find_conflicts(self, filename: str, date_min, date_max) -> list[dict]:
        """Devuelve uploads cuyos rangos solapan, o con el mismo nombre de archivo."""
        dmin = pd.Timestamp(date_min) if date_min is not None else None
        dmax = pd.Timestamp(date_max) if date_max is not None else None
        out: list[dict] = []
        for item in self._load_index():
            same_name = (filename and item.get("filename") == filename)
            i_min = pd.Timestamp(item["date_min"]) if item.get("date_min") else None
            i_max = pd.Timestamp(item["date_max"]) if item.get("date_max") else None
            overlap = _ranges_overlap(dmin, dmax, i_min, i_max)
            if same_name or overlap:
                out.append({
                    **item,
                    "conflict_reason": "mismo_nombre" if same_name and not overlap else
                                        ("fechas_solapadas" if overlap and not same_name else "mismo_nombre_y_fechas"),
                })
        return out

    # ---------- ops ----------
    def add(self, report: ReportData, force: bool = False) -> StoredUpload:
        conflicts = self.find_conflicts(report.filename, report.date_min, report.date_max)
        if conflicts and not force:
            names = ", ".join(f"{c['filename']} ({c['rango']})" for c in conflicts)
            raise OverlapError(
                f"Este archivo se solapa con uno ya subido: {names}. "
                f"Elimina el anterior o reenvía con force=true para sobrescribir.",
                conflicts=conflicts,
            )
        if conflicts and force:
            # Reemplazar: borrar los conflictivos antes de insertar el nuevo
            for c in conflicts:
                self.delete(c["id"])
        with self._lock:
            uid = uuid.uuid4().hex
            df = _df_for_parquet(report.df)
            df.to_parquet(self._parquet_path(uid), index=False)

            stored = StoredUpload(
                id=uid,
                filename=report.filename,
                uploaded_at=datetime.utcnow().isoformat(timespec="seconds"),
                rango=report.rango_str,
                filas=int(len(df)),
                date_min=report.date_min.isoformat() if report.date_min is not None else None,
                date_max=report.date_max.isoformat() if report.date_max is not None else None,
            )
            items = self._load_index()
            items.append(stored.__dict__)
            items.sort(key=lambda x: x.get("date_min") or "")
            self._save_index(items)
            return stored

    def list(self) -> list[StoredUpload]:
        return [StoredUpload(**x) for x in self._load_index()]

    def get(self, uid: str) -> ReportData | None:
        df = self._load_df(uid)
        if df.empty:
            return None
        item = next((x for x in self._load_index() if x["id"] == uid), None)
        filename = item["filename"] if item else uid
        return _df_to_report(df, filename=filename)

    def delete(self, uid: str) -> bool:
        with self._lock:
            items = self._load_index()
            new_items = [x for x in items if x["id"] != uid]
            if len(new_items) == len(items):
                return False
            self._save_index(new_items)
            p = self._parquet_path(uid)
            if p.exists():
                p.unlink()
            return True

    def reset(self) -> None:
        with self._lock:
            for p in self._uploads_dir.glob("*.parquet"):
                p.unlink()
            self._save_index([])

    def accumulated(self) -> ReportData | None:
        items = self._load_index()
        if not items:
            return None
        dfs = []
        for item in items:
            d = self._load_df(item["id"])
            if not d.empty:
                dfs.append(d)
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
        filename = f"Acumulado ({len(items)} archivos)"
        return _df_to_report(merged, filename=filename)


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
repository = UploadRepository(DATA_DIR)
