"""Qué base de Ventra le toca a cada sucursal de analitics.

# Por qué hace falta una tabla y no vale el nombre

Los nombres no cuadran solos: la sucursal `holguin` lee de la base `holguinmoa`,
`sancti-spiritus` de `sspiritus`, `santiago-de-cuba` de `santiago`. Emparejar por
parecido de texto acierta en siete de diez y falla justo en las tres que importan — y
fallar aquí significa enseñar las ventas de una sucursal dentro de otra, que es un error
que nadie detecta mirando el informe.

# Y por qué CADA BASE ES UNA SUCURSAL

Moa, Palma Soriano y Las Tunas tienen base propia en Ventra con ventas propias, y las
tres van **aparte** — decisión de Jose, 05/09/2026. No se suman a Holguín ni a Santiago
aunque caigan en su provincia: son puntos que venden por su cuenta y sus números tienen
que poder mirarse solos.

Las Tunas además **no existía como sucursal** en analitics, aunque llevaba meses
vendiendo (4.023 líneas en treinta días). Se da de alta.
"""
from __future__ import annotations

# sid de analitics -> database de Ventra. Uno a uno: una base no se parte entre dos
# sucursales, y una sucursal no suma dos bases. Si algún día hiciera falta agrupar, que
# se haga al presentar y no aquí, para que el dato crudo siga siendo trazable.
BASE_POR_SUCURSAL: dict[str, str] = {
    "camaguey": "camaguey",
    "granma": "granma",
    "guantanamo": "guantanamo",
    "habana": "habana",
    "holguin": "holguinmoa",
    "las-tunas": "tunas",
    "moa": "moa",
    "palma-soriano": "palmasoriano",
    "sancti-spiritus": "sspiritus",
    "santiago-de-cuba": "santiago",
}

# El nombre con el que se dan de alta las que faltan. Sólo estas tres: las otras siete
# ya existen y no se tocan.
NOMBRE_POR_SUCURSAL: dict[str, str] = {
    "las-tunas": "Las Tunas",
    "moa": "Moa",
    "palma-soriano": "Palma Soriano",
}


def base_de(sid: str) -> str | None:
    """La base de Ventra de esa sucursal, o None si no tiene.

    Devuelve None y no adivina: una sucursal nueva que nadie añadió a la tabla es un
    aviso de que hay que decidir de dónde lee, no una invitación a buscarle la base más
    parecida. Enseñar las ventas de otra sucursal es peor que no enseñar ninguna.
    """
    return BASE_POR_SUCURSAL.get(sid)


def sucursal_de(base: str) -> str | None:
    """Al revés: de qué sucursal es esa base."""
    for sid, b in BASE_POR_SUCURSAL.items():
        if b == base:
            return sid
    return None
