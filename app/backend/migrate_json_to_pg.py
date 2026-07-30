"""Migración única JSON/parquet -> PostgreSQL. Idempotente: re-correrla NO duplica.

- users.json      -> analytics_user   (upsert por username)
- sucursales.json -> analytics_sucursal (upsert por sid; nombre en columna, resto en config)
- uploads/<sid>/index.json + <uid>.parquet -> analytics_upload + analytics_upload_row
  (se salta el upload si su id ya existe -> idempotente; solo se leen, no se borran archivos)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from services.db import session_scope, User, Sucursal, Upload, UploadRow
from services.repository import _COL2ATTR, _cell, _TEXT_ATTRS, _NUM_ATTRS


def _migrar_usuarios(data_dir: Path, s) -> int:
    p = data_dir / "users.json"
    if not p.exists():
        return 0
    raw = json.loads(p.read_text(encoding="utf-8"))
    users = raw if isinstance(raw, list) else list(raw.values())
    n = 0
    for u in users:
        username = str(u.get("username", "")).strip().lower()
        if not username:
            continue
        data = {"nombre": u.get("nombre", username),
                "sucursales": u.get("sucursales", []),
                "gestor": u.get("gestor")}
        row = s.query(User).filter_by(username=username).one_or_none()
        if row is None:
            s.add(User(username=username, password_hash=u.get("password_hash", ""),
                       role=u.get("role", "usuario"), data=data))
        else:
            # El JSON es la fuente de verdad: se actualiza el existente.
            row.password_hash = u.get("password_hash", row.password_hash)
            row.role = u.get("role", row.role)
            row.data = data
        n += 1
    return n


def _migrar_sucursales(data_dir: Path, s) -> int:
    p = data_dir / "sucursales.json"
    if not p.exists():
        return 0
    raw = json.loads(p.read_text(encoding="utf-8"))
    sucs = raw if isinstance(raw, list) else list(raw.values())
    n = 0
    for suc in sucs:
        sid = suc.get("id") or suc.get("sid")
        if not sid:
            continue
        nombre = suc.get("nombre", sid)
        body = {k: v for k, v in suc.items() if k not in ("id", "sid", "nombre")}
        row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
        if row is None:
            s.add(Sucursal(sid=sid, nombre=nombre, config=body))
        else:
            row.nombre = nombre
            row.config = body
        n += 1
    return n


def _fila_kwargs(r, columnas) -> dict:
    kw = {}
    for col, attr in _COL2ATTR.items():
        kw[attr] = _cell(r.get(col)) if col in columnas else None
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
    return kw


def _migrar_uploads(data_dir: Path, s) -> tuple[int, int]:
    uploads_dir = data_dir / "uploads"
    if not uploads_dir.exists():
        return 0, 0
    n_up = n_rows = 0
    for suc_dir in sorted(uploads_dir.iterdir()):
        if not suc_dir.is_dir():
            continue
        sid = suc_dir.name
        index_p = suc_dir / "index.json"
        if not index_p.exists():
            continue
        try:
            items = json.loads(index_p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in items:
            uid = it.get("id")
            if not uid:
                continue
            if s.query(Upload).filter_by(id=uid).first():
                continue  # ya migrado -> idempotente
            parquet_p = suc_dir / f"{uid}.parquet"
            if not parquet_p.exists():
                continue
            df = pd.read_parquet(parquet_p)
            cols = set(df.columns)
            s.add(Upload(
                id=uid, sid=sid, filename=it.get("filename", uid),
                uploaded_at=it.get("uploaded_at", ""), rango=it.get("rango", ""),
                filas=int(it.get("filas", len(df))),
                date_min=it.get("date_min"), date_max=it.get("date_max"),
                source="migracion",
            ))
            for _, r in df.iterrows():
                s.add(UploadRow(upload_id=uid, **_fila_kwargs(r, cols)))
                n_rows += 1
            n_up += 1
    return n_up, n_rows


def migrar(data_dir: Path) -> dict:
    data_dir = Path(data_dir)
    with session_scope() as s:
        usuarios = _migrar_usuarios(data_dir, s)
        sucursales = _migrar_sucursales(data_dir, s)
    # Uploads en su propia transacción, DESPUÉS de las sucursales (FK upload.sid).
    with session_scope() as s:
        uploads, filas = _migrar_uploads(data_dir, s)
    return {"usuarios": usuarios, "sucursales": sucursales, "uploads": uploads, "filas": filas}


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "data"
    res = migrar(base)
    print("Migración completada:", res)
