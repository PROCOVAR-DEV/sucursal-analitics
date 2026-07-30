from services.sucursal_store import SucursalStore, slugify


def test_crud_y_gestores():
    st = SucursalStore(base_dir=None)
    sid = slugify("QA Sucursal Temp")
    st.delete(sid)  # limpieza previa
    cfg = st.create("QA Sucursal Temp", seed_gestores=False)
    assert st.exists(sid)
    assert cfg["nombre"] == "QA Sucursal Temp"

    st.update(sid, {"metas": {"meta_dinero_total": 5000.0}})
    assert st.get(sid)["metas"]["meta_dinero_total"] == 5000.0

    # las claves de gestor se guardan en MAYÚSCULAS (str(clave).upper())
    st.upsert_gestor(sid, "juan", {"nombre": "Juan"})
    assert "JUAN" in st.get(sid)["gestores"]
    st.rename_gestor(sid, "JUAN", "juanp")
    g = st.get(sid)["gestores"]
    assert "JUANP" in g and "JUAN" not in g
    st.delete_gestor(sid, "JUANP")
    assert "JUANP" not in st.get(sid)["gestores"]

    assert st.delete(sid) is True
    assert st.get(sid) is None
