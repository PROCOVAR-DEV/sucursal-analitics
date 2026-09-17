"""
Quién puede llegar a qué: las reglas puras, sin base de datos.

Aparte de `auth_store` porque ahí dentro todo toca Postgres y esto no toca nada — son
comprobaciones de permisos, que es justo lo que más falta hace poder probar.
"""
from __future__ import annotations

ALL_SUCURSALES = "*"
_ALL_ROLES = ("admin", "analitico")            # los únicos que llevan el comodín


def sucursales_para(role: str, sucursales) -> list[str]:
    """Las sucursales que le tocan a un rol, con el COMODÍN quitado si no le corresponde.

    `"*"` significa «todas» y sólo tiene sentido para `admin` y `analitico`. A un
    supervisor no le da sólo vista: `can_write_metas` llama a `can_access`, así que un
    supervisor con comodín **puede escribirle las metas a las diez sucursales**.

    Pasó de verdad: el usuario `pedro`, supervisor de Santiago, tenía
    `["*", "santiago-de-cuba"]`. No fue ningún ataque —no es una inyección, el comodín
    es una constante del propio programa— sino que el campo se teclea a mano en la
    pantalla de usuarios y nada lo comprobaba. Se limpió el 17/09/2026.

    Se filtra en el almacén y no en el endpoint porque por aquí pasan el alta y la
    edición: uno de los dos se habría quedado sin la comprobación, y sería justo el que
    alguien use.
    """
    if role in _ALL_ROLES:
        return [ALL_SUCURSALES]
    return [s for s in (sucursales or []) if str(s).strip() != ALL_SUCURSALES]
