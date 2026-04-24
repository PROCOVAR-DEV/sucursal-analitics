"""Acumulador persistente de reportes diarios.

Guarda un consolidado CSV en disco para que cada nueva carga se sume al
histórico y sobreviva reinicios del backend.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
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
    STD_COLS["nota"],
]


@dataclass
class AccumulationResult:
    report: ReportData
    added_rows: int
    total_rows: int
    total_files: int


class DailyAccumulator:
    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._csv_path = self._base_dir / "acumulado.csv"
        self._meta_path = self._base_dir / "meta.json"
        self._lock = threading.Lock()

    def _load_df(self) -> pd.DataFrame:
        if not self._csv_path.exists():
            return pd.DataFrame()
        df = pd.read_csv(self._csv_path)
        fecha_col = STD_COLS["fecha"]
        if fecha_col in df.columns:
            df[fecha_col] = pd.to_datetime(df[fecha_col], errors="coerce")
        return df

    def _save_df(self, df: pd.DataFrame) -> None:
        df.to_csv(self._csv_path, index=False, encoding="utf-8-sig")

    def _load_meta(self) -> dict:
        if not self._meta_path.exists():
            return {"total_files": 0}
        try:
            return json.loads(self._meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {"total_files": 0}

    def _save_meta(self, meta: dict) -> None:
        self._meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _to_report(df: pd.DataFrame, filename: str) -> ReportData:
        date_min = date_max = None
        fecha_col = STD_COLS["fecha"]
        if fecha_col in df.columns and not df.empty:
            valid_dates = pd.to_datetime(df[fecha_col], errors="coerce")
            if not valid_dates.isna().all():
                date_min = valid_dates.min()
                date_max = valid_dates.max()
        return ReportData(df=df, date_min=date_min, date_max=date_max, filename=filename)

    @staticmethod
    def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
        keys = [k for k in DEDUPE_KEYS if k in df.columns]
        if not keys:
            return df
        return df.drop_duplicates(subset=keys, keep="last")

    def add(self, daily_report: ReportData) -> AccumulationResult:
        """Acumula un reporte diario y devuelve el consolidado actualizado."""
        with self._lock:
            current = self._load_df()
            incoming = daily_report.df.copy()
            before_rows = len(current)

            if current.empty:
                merged = incoming
            else:
                merged = pd.concat([current, incoming], ignore_index=True)

            merged = self._dedupe(merged)
            sort_keys = [c for c in [STD_COLS["fecha"], STD_COLS["op"]] if c in merged.columns]
            if sort_keys:
                merged = merged.sort_values(by=sort_keys)
            merged = merged.reset_index(drop=True)

            self._save_df(merged)

            meta = self._load_meta()
            meta["total_files"] = int(meta.get("total_files", 0)) + 1
            self._save_meta(meta)

            report = self._to_report(merged, filename=f"Acumulado diario ({meta['total_files']} archivos)")
            return AccumulationResult(
                report=report,
                added_rows=max(0, len(merged) - before_rows),
                total_rows=len(merged),
                total_files=int(meta.get("total_files", 0)),
            )

    def current(self) -> ReportData | None:
        with self._lock:
            df = self._load_df()
            if df.empty:
                return None
            meta = self._load_meta()
            total_files = int(meta.get("total_files", 0))
            return self._to_report(df, filename=f"Acumulado diario ({total_files} archivos)")

    def reset(self) -> None:
        with self._lock:
            if self._csv_path.exists():
                self._csv_path.unlink()
            if self._meta_path.exists():
                self._meta_path.unlink()


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
daily_accumulator = DailyAccumulator(DATA_DIR)
