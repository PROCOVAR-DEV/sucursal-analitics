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


def recortar_a_gestor(eff: dict, gestor: str) -> dict:
    """La configuración de la sucursal, vista por UNO de sus vendedores.

    Que un `gestor` sólo vea sus ventas ya se hacía: se quedaba con su ficha dentro de
    `gestores` y el resto de filas desaparecía. Pero las METAS seguían siendo las de la
    sucursal, así que la pantalla comparaba lo que vende UNA persona contra lo que tiene
    que vender el equipo entero.

    Santiago, 25/09/2026: un vendedor con 82 pacas de arroz leía **3 %**, porque el 2.945
    de esa fila es el plan de los diez. El supervisor, que mira los totales contra las
    metas totales, veía el 41 % bueno en la misma fila. Dos pantallas de la misma
    aplicación diciendo cosas distintas del mismo producto, y ninguna avisando de cuál
    estaba midiendo qué.

    Lo suyo es lo que le repartieron a él:

        hectolitros    su `cuota_hl`           (y `cuota_ccc` para los clientes)
        productos      sus `metas_cantidad`    lo que se le puso en la calculadora

    **Un producto sin plan suyo sale de la tabla, no con la meta de la sucursal.** Donde
    no hay meta no hay cumplimiento que enseñar, y poner la del equipo es exactamente el
    número que se vino a quitar. Lo que ha vendido de ese producto no se pierde: sigue en
    el resumen por grupo y en los totales, que no dependen de las metas.

    El dinero se queda como está: no hay cuota de dinero por vendedor que poner en su
    lugar, y no se enseña como meta en ninguna de sus pantallas.
    """
    g = str(gestor).strip().upper()
    mios = {k: v for k, v in (eff.get("gestores") or {}).items() if str(k).strip().upper() == g}

    def _num(v, campo) -> float:
        try:
            return float((v or {}).get(campo) or 0)
        except (TypeError, ValueError):
            return 0.0

    # Las metas por cantidad, sumadas por si su ficha trae el mismo producto dos veces.
    # Un cero no es una meta: es una fila que sólo sirve para enseñar un 0 % que se lee
    # como «va fatal».
    metas: dict[str, float] = {}
    for v in mios.values():
        for producto, cantidad in ((v or {}).get("metas_cantidad") or {}).items():
            try:
                n = float(cantidad or 0)
            except (TypeError, ValueError):
                continue
            if n > 0:
                metas[str(producto)] = round(metas.get(str(producto), 0.0) + n, 2)

    return {
        **eff,
        "gestores": mios,
        "meta_hectolitros_total": round(sum(_num(v, "cuota_hl") for v in mios.values()), 2),
        "meta_ccc_total": round(sum(_num(v, "cuota_ccc") for v in mios.values()), 2),
        "metas_productos_ces": metas,
    }
