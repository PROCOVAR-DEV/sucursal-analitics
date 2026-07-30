"""Repositorio de reportes subidos, aislado por sucursal, sobre PostgreSQL.

Guarda SOLO los datos (las filas en `analytics_upload_row`), NUNCA el archivo. Las
columnas derivadas del loader (VendorSegNorm, Size, IsMalta, ...) NO se guardan: se
RE-DERIVAN al leer con `_type_df` + `_add_stable_helpers`, así el DataFrame que reciben
los reportes es idéntico al que daba el parquet. Interfaz pública igual a la versión
anterior (find_conflicts, add, list, get, delete, reset, accumulated).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from services.db import session_scope, Upload, UploadRow
from services.loader import ReportData, STD_COLS, _type_df, _add_stable_helpers


DEDUPE_KEYS = [STD_COLS["op"], STD_COLS["fecha"], STD_COLS["socio"],
               STD_COLS["merc"], STD_COLS["cant"], STD_COLS["importe"]]

# Columnas BASE que se persisten (las derivadas se recalculan al leer).
_BASE_COLS = [STD_COLS["op"], STD_COLS["fecha"], STD_COLS["socio"], STD_COLS["merc"],
              STD_COLS["grupo"], STD_COLS["cant"], STD_COLS["importe"], STD_COLS["suma"],
              STD_COLS["nota"]]

# STD col -> atributo de UploadRow.
_COL2ATTR = {
    STD_COLS["op"]: "operacion",
    STD_COLS["fecha"]: "fecha",
    STD_COLS["socio"]: "socio",
    STD_COLS["merc"]: "mercancia",
    STD_COLS["grupo"]: "grupo",
    STD_COLS["cant"]: "cantidad",
    STD_COLS["importe"]: "importe",
    STD_COLS["suma"]: "suma",
    STD_COLS["nota"]: "nota",
}
_TEXT_ATTRS = ("operacion", "socio", "mercancia", "grupo", "nota")
_NUM_ATTRS = ("cantidad", "importe", "suma")


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


def _ranges_overlap(a_min, a_max, b_min, b_max) -> bool:
    if any(v is None for v in (a_min, a_max, b_min, b_max)):
        return False
    return not (a_max < b_min or b_max < a_min)


def _cell(v):
    """Escalar limpio para guardar (None si es NaN/NA)."""
    try:
        if v is None or pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


class UploadRepository:
    def __init__(self, base_dir: Path | str | None = None):
        # base_dir se conserva por compat; ya NO se usa (los datos viven en postgres).
        pass

    # ---------- lectura de filas -> DataFrame (con columnas derivadas) ----------
    def _df_de_filas(self, upload_ids) -> pd.DataFrame:
        if not upload_ids:
            df = pd.DataFrame(columns=_BASE_COLS)
        else:
            with session_scope() as s:
                rows = s.query(UploadRow).filter(UploadRow.upload_id.in_(list(upload_ids))).all()
                data = [
                    {
                        STD_COLS["op"]: r.operacion,
                        STD_COLS["fecha"]: r.fecha,
                        STD_COLS["socio"]: r.socio,
                        STD_COLS["merc"]: r.mercancia,
                        STD_COLS["grupo"]: r.grupo,
                        STD_COLS["cant"]: r.cantidad,
                        STD_COLS["importe"]: r.importe,
                        STD_COLS["suma"]: r.suma,
                        STD_COLS["nota"]: r.nota,
                    }
                    for r in rows
                ]
            df = pd.DataFrame(data, columns=_BASE_COLS)
        # Reproduce EXACTO lo que hacía el loader: tipa las base y re-deriva helpers
        # (vseg/size/malta/...). Así los reportes reciben el mismo DataFrame que antes.
        df = _type_df(df)
        df = _add_stable_helpers(df)
        return df

    def _uploads(self, sid: str) -> list[dict]:
        with session_scope() as s:
            ups = s.query(Upload).filter_by(sid=sid).order_by(Upload.date_min).all()
            return [
                {"id": u.id, "filename": u.filename, "uploaded_at": u.uploaded_at,
                 "rango": u.rango, "filas": u.filas, "date_min": u.date_min, "date_max": u.date_max}
                for u in ups
            ]

    # ---------- conflictos ----------
    def find_conflicts(self, sid: str, filename: str, date_min, date_max) -> list[dict]:
        dmin = pd.Timestamp(date_min) if date_min is not None else None
        dmax = pd.Timestamp(date_max) if date_max is not None else None
        out: list[dict] = []
        for item in self._uploads(sid):
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

        df = report.df
        uid = uuid.uuid4().hex
        uploaded_at = datetime.utcnow().isoformat(timespec="seconds")
        dmin = report.date_min.isoformat() if report.date_min is not None else None
        dmax = report.date_max.isoformat() if report.date_max is not None else None

        with session_scope() as s:
            s.add(Upload(
                id=uid, sid=sid, filename=report.filename, uploaded_at=uploaded_at,
                rango=report.rango_str, filas=int(len(df)), date_min=dmin, date_max=dmax,
                source="upload",
            ))
            for _, r in df.iterrows():
                kw = {}
                for col, attr in _COL2ATTR.items():
                    val = _cell(r.get(col)) if col in df.columns else None
                    kw[attr] = val
                # fecha -> date; textos -> str; números -> float
                f = kw.get("fecha")
                kw["fecha"] = pd.to_datetime(f).date() if f is not None and pd.notna(f) else None
                for a in _TEXT_ATTRS:
                    kw[a] = None if kw.get(a) is None else str(kw[a])
                for a in _NUM_ATTRS:
                    v = kw.get(a)
                    try:
                        kw[a] = None if v is None else float(v)
                    except (TypeError, ValueError):
                        kw[a] = None
                s.add(UploadRow(upload_id=uid, **kw))

        return StoredUpload(id=uid, filename=report.filename, uploaded_at=uploaded_at,
                            rango=report.rango_str, filas=int(len(df)), date_min=dmin, date_max=dmax)

    def list(self, sid: str) -> list[StoredUpload]:
        return [StoredUpload(**x) for x in self._uploads(sid)]

    def get(self, sid: str, uid: str) -> ReportData | None:
        with session_scope() as s:
            up = s.query(Upload).filter_by(sid=sid, id=uid).one_or_none()
            if up is None:
                return None
            fname = up.filename
        df = self._df_de_filas([uid])
        if df.empty:
            return None
        return _df_to_report(df, filename=fname)

    def delete(self, sid: str, uid: str) -> bool:
        with session_scope() as s:
            up = s.query(Upload).filter_by(sid=sid, id=uid).one_or_none()
            if up is None:
                return False
            s.delete(up)  # las filas caen por cascade (relationship + FK ondelete)
            return True

    def reset(self, sid: str) -> None:
        with session_scope() as s:
            for up in s.query(Upload).filter_by(sid=sid).all():
                s.delete(up)

    def accumulated(self, sid: str) -> ReportData | None:
        with session_scope() as s:
            ids = [u.id for u in s.query(Upload).filter_by(sid=sid).all()]
        if not ids:
            return None
        merged = self._df_de_filas(ids)
        if merged.empty:
            return None
        keys = [k for k in DEDUPE_KEYS if k in merged.columns]
        if keys:
            merged = merged.drop_duplicates(subset=keys, keep="last")
        sort_keys = [c for c in [STD_COLS["fecha"], STD_COLS["op"]] if c in merged.columns]
        if sort_keys:
            merged = merged.sort_values(by=sort_keys)
        merged = merged.reset_index(drop=True)
        return _df_to_report(merged, filename=f"Acumulado ({len(ids)} archivos)")


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
repository = UploadRepository(DATA_DIR)
