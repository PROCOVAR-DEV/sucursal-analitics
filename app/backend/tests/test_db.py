from services.db import init_db, session_scope, Sucursal

# sid con prefijo __test_ para NO tocar datos reales (los tests corren contra la misma
# DB analitics; nunca deben borrar sucursales de producción).
_SID = "__test_db_cam__"


def test_init_db_crea_tablas_y_roundtrip():
    init_db()  # idempotente
    with session_scope() as s:
        s.query(Sucursal).filter_by(sid=_SID).delete()
        s.add(Sucursal(sid=_SID, nombre="Camaguey", config={"gestores": {}}))
    with session_scope() as s:
        row = s.query(Sucursal).filter_by(sid=_SID).one()
        assert row.nombre == "Camaguey"
        assert row.config == {"gestores": {}}
    # limpieza
    with session_scope() as s:
        s.query(Sucursal).filter_by(sid=_SID).delete()
