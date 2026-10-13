"""Las metas en la base del CRM (services/metas_crm.py y copiar_metas_al_crm.py).

Las de base de datos necesitan un CRM migrado (026 o posterior) y un usuario miembro de
`analytics_metas`, el mismo permiso que tendrá Analytics en el servidor:

    CRM_METAS_DATABASE_URL_PRUEBA=postgresql://usuario:clave@host:5432/crm pytest

Sin ella se saltan, y lo dicen. Sólo escriben sucursales `__test_…`.
"""
import copy
import os

import pytest
from sqlalchemy import text

from services import metas_crm
from services.sucursal_store import SucursalStore, config_for_period, config_accumulated

URL_PRUEBA = os.environ.get("CRM_METAS_DATABASE_URL_PRUEBA", "").strip()
con_crm = pytest.mark.skipif(not URL_PRUEBA, reason="sin CRM_METAS_DATABASE_URL_PRUEBA (CRM migrado)")

SID = "__test_metas_crm__"


def _config() -> dict:
    """Una config como las de producción, con todos los casos que el modelo tiene que guardar."""
    return {
        "nombre": "Prueba", "supervisor_nombre": "Sup",
        "gestores": {
            "GARI": {"nombre": "Gari", "agencia": "A", "sector": "1", "cuota_hl": 500.0, "cuota_ccc": 30.0,
                     "aliases": ["GARI R"], "activo": True, "es_supervisor": False, "baja_desde": "",
                     "sin_meta": False, "metas_formato": {"PARRANDA-1500": 300.0}},
            "SIDNEY": {"nombre": "Sidney", "agencia": "A", "sector": "", "cuota_hl": 0.0, "cuota_ccc": 0.0,
                       "aliases": [], "activo": True, "es_supervisor": True, "sin_meta": True, "metas_formato": {}},
            "NUEVO": {"nombre": "Nuevo", "aliases": [], "activo": True},
        },
        "metas": {"meta_hectolitros_total": 4156.5, "meta_dinero_total": 1e6, "meta_ccc_total": 120.0,
                  "metas_productos_ces": {"ARROZ": 2700.0, "PAPEL": 0.0}, "formatos": ["P1500", "M330"]},
        "parametros": {"trabaja_sabado": True},
        "metas_mensuales": {
            "2026-09": {"meta_hectolitros_total": 4000.0, "meta_ccc_total": 100.0,
                        "metas_productos_ces": {"ARROZ": 2500.0},
                        "gestores": {
                            "GARI": {"cuota_hl": 545.63, "cuota_ccc": 31.0,
                                     "metas_formato": {"PARRANDA-1500": 401.6, "MALTA-1500": 117.39},
                                     "metas_cantidad": {"ARROZ": 245.0}},
                            # sólo cantidades: el desglose por formato se hereda de la base
                            "SIDNEY": {"metas_cantidad": {"ARROZ": 504.0}},
                            # en el roster del mes, sin nada
                            "NUEVO": {},
                        }},
            # mes «configurado» pero vacío: la pantalla lo distingue de no tenerlo
            "2026-10": {},
            # sólo dinero
            "2026-11": {"meta_dinero_total": 2e6, "gestores": {"GARI": {"cuota_hl": 600.0, "metas_formato": {}}}},
        },
    }


def _efectivas(suc: dict) -> list:
    return [config_for_period(suc, y, m) for y, m in ((None, None), (2026, 9), (2026, 10), (2026, 11), (2026, 12))] + [
        config_accumulated(suc, [(2026, 9), (2026, 10), (2026, 11)])]


# --------------------------------------------------------------- sin base de datos

def test_separar_y_juntar_no_cambian_lo_que_ve_ninguna_pantalla():
    suc = {**_config(), "id": SID}
    parte, avisos = metas_crm.separar(suc)
    assert avisos == []
    # Se juntan sobre una config a la que se le han CAMBIADO las metas: manda la parte.
    vieja = copy.deepcopy(suc)
    vieja["metas"]["meta_hectolitros_total"] = 1
    vieja["metas_mensuales"] = {"2025-01": {"meta_hectolitros_total": 9}}
    vieja["gestores"]["GARI"]["cuota_hl"] = 1
    junta = metas_crm.juntar(vieja, parte)
    assert _efectivas(junta) == _efectivas(suc)
    assert junta["metas_mensuales"].keys() == suc["metas_mensuales"].keys()
    # La identidad del gestor es de Analytics y no pasa por la parte de metas.
    assert junta["gestores"]["GARI"]["aliases"] == ["GARI R"]
    assert "aliases" not in str(parte)


def test_separar_avisa_de_lo_que_no_cabe():
    suc = _config()
    suc["metas"]["meta_rara"] = 1
    suc["metas_mensuales"]["2026-9"] = {"meta_hectolitros_total": 1}
    suc["metas_mensuales"]["2026-09"]["gestores"]["GARI"]["nota"] = "x"
    _, avisos = metas_crm.separar(suc)
    assert sorted(avisos) == ["metas.meta_rara", "metas_mensuales.2026-09.gestores.GARI.nota", "metas_mensuales.2026-9"]


def test_codigo_de_sucursal():
    assert metas_crm.codigo("camaguey") == "CAM"
    assert metas_crm.codigo("santiago-de-cuba") == "STG"
    assert metas_crm.codigo("moa") == "moa"


# --------------------------------------------------------------- contra el CRM

@pytest.fixture
def crm(monkeypatch):
    monkeypatch.setenv("CRM_METAS_DATABASE_URL", URL_PRUEBA)
    sids = [SID, "__test_metas_crm_b__", "__test_metas_crm_c__"]
    for s in sids:
        metas_crm.borrar(s)
    yield metas_crm._engine()
    for s in sids:
        metas_crm.borrar(s)


def _versiones(engine, sid):
    with engine.connect() as c:
        return sorted(c.execute(text(
            "select 's', row_version from metas_venta_sucursal where sucursal = :s union all "
            "select 'p', row_version from metas_venta_producto where sucursal = :s union all "
            "select 'g', row_version from metas_venta_gestor where sucursal = :s union all "
            "select 'f', row_version from metas_venta_gestor_formato where sucursal = :s union all "
            "select 'c', row_version from metas_venta_gestor_producto where sucursal = :s"), {"s": sid}).all())


@con_crm
def test_guardar_y_leer_ida_y_vuelta(crm):
    parte, _ = metas_crm.separar(_config())
    metas_crm.guardar(SID, parte)
    assert metas_crm.leer(SID) == parte

    # Guardar lo mismo no toca ninguna fila.
    antes = _versiones(crm, SID)
    assert len(antes) == 4 + 3 + 6 + 3 + 2  # sucursal, productos, gestores, formatos, cantidades
    metas_crm.guardar(SID, parte)
    assert _versiones(crm, SID) == antes

    # Quitar un mes se lleva sus filas y las de sus hijos; cambiar una cuota sólo toca esa.
    del parte["metas_mensuales"]["2026-09"]
    parte["gestores"]["GARI"]["cuota_hl"] = 510.0
    metas_crm.guardar(SID, parte)
    assert metas_crm.leer(SID) == parte
    assert len(_versiones(crm, SID)) == 3 + 2 + 3 + 1 + 0


@con_crm
def test_el_store_guarda_y_lee_del_crm(crm):
    st = SucursalStore()
    nombre = "__test metas crm__"
    sid = "test-metas-crm"
    st.delete(sid)
    metas_crm.borrar(sid)
    try:
        st.create(nombre, seed_gestores=False)
        assert st.get(sid)["id"] == sid
        st.upsert_gestor(sid, "gari", {"nombre": "Gari", "cuota_hl": 500})
        st.update(sid, {"metas": {"meta_hectolitros_total": 4000, "formatos": ["p1500"]}})
        # Lo que manda la calculadora al guardar el mes y al guardar las cantidades.
        st.update(sid, {"metas_mensuales": {"2026-10": {"gestores": {"GARI": {
            "cuota_hl": 545.63, "cuota_ccc": 3, "metas_formato": {"PARRANDA-1500": 401.6}, "metas_cantidad": {}}},
            "meta_hectolitros_total": 545.63}}})
        st.update(sid, {"metas_mensuales": {"2026-10": {"gestores": {"GARI": {"metas_cantidad": {"ARROZ": 245}}}}}})

        parte = metas_crm.leer(sid)
        assert parte["metas"]["meta_hectolitros_total"] == 4000.0
        assert parte["metas"]["formatos"] == ["P1500"]
        assert parte["gestores"]["GARI"]["cuota_hl"] == 500.0
        assert parte["metas_mensuales"]["2026-10"]["gestores"]["GARI"] == {
            "cuota_hl": 545.63, "cuota_ccc": 3.0, "metas_formato": {"PARRANDA-1500": 401.6},
            "metas_cantidad": {"ARROZ": 245.0}}

        # Manda el CRM: lo que se cambie allí es lo que ve Analytics.
        with crm.begin() as c:
            c.execute(text("update metas_venta_gestor set cuota_hl = 999 where sucursal = :s and periodo = '2026-10'"), {"s": sid})
        assert config_for_period(st.get(sid), 2026, 10)["gestores"]["GARI"]["cuota_hl"] == 999.0

        # Renombrar un gestor mueve su cuota base; borrar el mes lo quita del CRM.
        st.rename_gestor(sid, "GARI", "GARIR")
        st.update(sid, {"metas_mensuales": {"2026-10": None}})
        parte = metas_crm.leer(sid)
        assert list(parte["gestores"]) == ["GARIR"] and parte["metas_mensuales"] == {}

        st.reset(sid)
        assert metas_crm.leer(sid)["metas"]["formatos"] == []
    finally:
        st.delete(sid)
    # Quitar la sucursal es quitarla entera, también del CRM.
    assert metas_crm.leer(sid) == {"metas_mensuales": {}, "gestores": {}}


@con_crm
def test_copia_dry_run_copia_e_idempotente(crm, capsys):
    import copiar_metas_al_crm
    from services.db import Sucursal, session_scope

    with session_scope() as s:
        s.query(Sucursal).filter_by(sid=SID).delete()
        s.add(Sucursal(sid=SID, nombre="Prueba", config=_config()))
    try:
        assert copiar_metas_al_crm.main(["--dry-run"]) == 0
        assert f"{SID} -> {SID}: base sí, 2 gestores con cuota base, 3 meses, 4 cuotas" in capsys.readouterr().out
        assert metas_crm.leer(SID) == {"metas_mensuales": {}, "gestores": {}}

        assert copiar_metas_al_crm.main([]) == 0
        parte, _ = metas_crm.separar(_config())
        assert metas_crm.leer(SID) == parte

        antes = _versiones(crm, SID)
        assert copiar_metas_al_crm.main([]) == 0
        assert _versiones(crm, SID) == antes

        # Con la variable puesta, lo que ve Analytics es lo copiado.
        suc = SucursalStore().get(SID)
        assert _efectivas(suc) == _efectivas({**_config(), "id": SID})
    finally:
        with session_scope() as s:
            s.query(Sucursal).filter_by(sid=SID).delete()


@con_crm
def test_copia_se_niega_si_dos_sucursales_dan_el_mismo_codigo(crm, monkeypatch, capsys):
    import copiar_metas_al_crm
    from services.db import Sucursal, session_scope

    monkeypatch.setitem(metas_crm.CODIGO_SUCURSAL, "__test_metas_crm_b__", "__test_metas_crm_c__")
    with session_scope() as s:
        for sid in ("__test_metas_crm_b__", "__test_metas_crm_c__"):
            s.query(Sucursal).filter_by(sid=sid).delete()
            s.add(Sucursal(sid=sid, nombre=sid, config=_config()))
    try:
        assert copiar_metas_al_crm.main([]) == 1
        assert "mismo código" in capsys.readouterr().err
        assert metas_crm.leer("__test_metas_crm_c__") == {"metas_mensuales": {}, "gestores": {}}
    finally:
        with session_scope() as s:
            for sid in ("__test_metas_crm_b__", "__test_metas_crm_c__"):
                s.query(Sucursal).filter_by(sid=sid).delete()


@con_crm
def test_sin_permiso_fuera_de_sus_tablas(crm):
    with pytest.raises(Exception, match="permission denied"):
        with crm.connect() as c:
            c.execute(text("select count(*) from cliente_cuotas"))
