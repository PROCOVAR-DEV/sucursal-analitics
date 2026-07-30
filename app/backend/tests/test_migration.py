import json

import pandas as pd

from migrate_json_to_pg import migrar
from services.db import session_scope, User, Sucursal, Upload, UploadRow


def test_migracion_idempotente(tmp_path):
    (tmp_path / "users.json").write_text(json.dumps([
        {"username": "__test_admin__", "password_hash": "pbkdf2$sha256$1$x$y",
         "role": "admin", "sucursales": ["*"], "nombre": "T"}
    ]))
    (tmp_path / "sucursales.json").write_text(json.dumps([
        {"id": "__test_cam__", "nombre": "Camaguey", "gestores": {}, "metas": {"meta_dinero_total": 1.0}}
    ]))
    ud = tmp_path / "uploads" / "__test_cam__"
    ud.mkdir(parents=True)
    df = pd.DataFrame([{"Operacion": "1", "Fecha": "2026-01-05", "Socio": "JUAN",
                        "Mercancia": "X", "Cantidad": 1, "Importe": 10.0}])
    df.to_parquet(ud / "__test_u1__.parquet")
    (ud / "index.json").write_text(json.dumps([
        {"id": "__test_u1__", "filename": "v.xlsx", "uploaded_at": "2026-01-05",
         "rango": "", "filas": 1, "date_min": "2026-01-05", "date_max": "2026-01-05"}
    ]))

    r1 = migrar(tmp_path)
    migrar(tmp_path)  # segunda corrida: idempotente, no debe duplicar

    assert r1["usuarios"] >= 1 and r1["sucursales"] >= 1 and r1["uploads"] >= 1 and r1["filas"] >= 1
    with session_scope() as s:
        assert s.query(User).filter_by(username="__test_admin__").count() == 1
        assert s.query(Sucursal).filter_by(sid="__test_cam__").count() == 1
        assert s.query(Upload).filter_by(id="__test_u1__").count() == 1  # no duplicó

    # limpieza (no dejar rastro en la DB compartida)
    with session_scope() as s:
        s.query(UploadRow).filter_by(upload_id="__test_u1__").delete()
        s.query(Upload).filter_by(id="__test_u1__").delete()
        s.query(Sucursal).filter_by(sid="__test_cam__").delete()
        s.query(User).filter_by(username="__test_admin__").delete()
