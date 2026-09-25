"""
La llave con la que se firman las sesiones tiene que sobrevivir a un despliegue.

El 25/09/2026, cada despliegue de analitics echaba a todo el mundo: había que volver a
entrar. La variable `AUTH_SECRET` estaba puesta en Dokploy justo para evitarlo, pero el
código miraba primero el disco — y el contenedor no tiene volumen, así que
`/app/data/secret.key` nace nuevo con cada imagen. El fichero del contenedor estaba
fechado a la hora exacta en que arrancó.

Lo que se prueba es el orden: la variable manda, y el disco es el respaldo.
"""
import os

from services.auth_store import AuthStore


def llave(base, entorno=None):
    """Arranca el almacén como lo hace el servicio, sin tocar la base de datos."""
    if entorno is None:
        os.environ.pop("AUTH_SECRET", None)
    else:
        os.environ["AUTH_SECRET"] = entorno

    a = AuthStore.__new__(AuthStore)
    a._base = base

    return a._load_secret()


def test_la_variable_manda_aunque_haya_fichero(tmp_path):
    (tmp_path / "secret.key").write_bytes(b"la-del-disco")

    assert llave(tmp_path, "la-de-dokploy") == b"la-de-dokploy"


def test_con_la_variable_dos_arranques_firman_igual(tmp_path):
    """Es la propiedad que importa: si no cambia, la sesión sigue valiendo."""
    assert llave(tmp_path, "la-de-dokploy") == llave(tmp_path, "la-de-dokploy")


def test_sin_variable_se_usa_el_disco_y_se_conserva(tmp_path):
    primera = llave(tmp_path, None)

    assert (tmp_path / "secret.key").exists()
    assert llave(tmp_path, None) == primera


def test_sin_variable_y_sin_disco_cada_arranque_es_una_llave_nueva():
    """Sin dónde guardarla no se puede prometer que la sesión dure: y así se ve."""
    assert llave(None, None) != llave(None, None)


def test_una_variable_vacia_no_cuenta(tmp_path):
    """`AUTH_SECRET=` en el panel es no haberla puesto, no una llave vacía."""
    primera = llave(tmp_path, "")

    assert primera == (tmp_path / "secret.key").read_bytes()
