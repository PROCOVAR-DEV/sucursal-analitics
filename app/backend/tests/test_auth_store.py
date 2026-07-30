import uuid

from services.auth_store import AuthStore


def _store():
    return AuthStore(base_dir=None)


def test_create_authenticate_update_delete():
    st = _store()
    u = "t_" + uuid.uuid4().hex[:8]
    creado = st.create(u, "clave123", "supervisor", ["cam"], nombre="Tester")
    assert creado["username"] == u and creado["role"] == "supervisor"
    assert "password" not in creado and "password_hash" not in creado
    assert st.authenticate(u, "clave123")["username"] == u
    assert st.authenticate(u, "malo") is None
    st.update(u, {"role": "usuario", "sucursales": ["cam", "hab"]})
    assert st.get_raw(u)["role"] == "usuario"
    tok = st.make_token(u)
    assert st.verify_token(tok)["username"] == u
    assert st.delete(u) is True
    assert st.get_raw(u) is None
