"""Calidad de las FICHAS de cliente de Ventra: cuántas están duplicadas y cuántas compartidas.

El código de cliente de Ventra (`customerCode`) casi identifica a un cliente, pero no del todo, y
ahí está lo útil:

- FICHA DUPLICADA: el mismo cliente con dos o más códigos (los dos «PO-…» de un mismo nombre, un
  apellido mal escrito, o el mismo código de Parranda en dos fichas). Cuenta de más.
- FICHA COMPARTIDA: un código de Ventra usado con personas distintas. Cuenta de menos.

No se usa para dar «el número de clientes» (ése sigue siendo el de nombres): ninguna de las dos
cuentas es exacta, y presentar una como la buena es lo que llevó a dudar de ella. Sirve para saber
qué fichas hay que arreglar en Axis, que es donde se arreglan.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

import pandas as pd

from services.loader import STD_COLS
from services.ventra import COL_CLIENTE_CODIGO

_CODIGO_PARRANDA = re.compile(r"^[A-Za-z]{2}[0-9]{2}[A-Za-z]{3}[0-9]{4}$")


def _norm(s) -> str:
    """Nombre comparable: sin «PO-», sin tildes ni signos. «PO-JUAN PÉREZ» y «Juan Perez» son uno."""
    s = re.sub(r"^\s*PO[-.\s]+", "", str(s or ""), flags=re.IGNORECASE)
    t = unicodedata.normalize("NFKD", s.upper()).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", t)


def _parecidos(a: str, b: str) -> bool:
    return a == b or (bool(a) and bool(b) and (a in b or b in a
            or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85))


def _codigo_de_la_nota(nota) -> str | None:
    """El código de Parranda de la nota, CORTADO en el primer «;» y solo si tiene forma de código."""
    m = re.search(r"C-([^;]*)", str(nota or ""))
    t = m.group(1).strip().upper() if m else ""
    return t if _CODIGO_PARRANDA.match(t) else None


def calidad_de_fichas(df: pd.DataFrame) -> dict | None:
    """{fichas, fichas_compartidas, clientes_con_varias_fichas} o None si aún no hay códigos de Ventra.

    Solo mira lo que hay en `df` (el periodo y los filtros que se estén viendo).
    """
    if df is None or df.empty or COL_CLIENTE_CODIGO not in df.columns:
        return None
    cod = df[COL_CLIENTE_CODIGO].map(lambda v: None if v is None or v != v or str(v).strip() == "" else str(v).strip())
    if cod.notna().sum() == 0:
        return None  # aún no se han rellenado: mejor no enseñar nada que enseñar un número a medias

    nombres_por_ficha: dict[str, set] = {}
    parranda_por_ficha: dict[str, set] = {}
    notas = df[STD_COLS["nota"]] if STD_COLS["nota"] in df.columns else [None] * len(df)
    for c, n, nota in zip(cod, df[STD_COLS["socio"]], notas):
        if c is None:
            continue
        nombres_por_ficha.setdefault(c, set()).add(_norm(n))
        p = _codigo_de_la_nota(nota)
        if p:
            parranda_por_ficha.setdefault(c, set()).add(p)

    # Compartidas: una ficha con nombres que no se parecen entre sí
    compartidas = 0
    for ns in nombres_por_ficha.values():
        ns = sorted(x for x in ns if x)
        if len(ns) > 1 and not all(_parecidos(ns[0], b) for b in ns[1:]):
            compartidas += 1

    # Duplicadas: fichas distintas que son el mismo cliente (mismo nombre, o mismo código de
    # Parranda con nombres parecidos). Se agrupan con «union-find».
    padre = {c: c for c in nombres_por_ficha}

    def raiz(c):
        while padre[c] != c:
            padre[c] = padre[padre[c]]
            c = padre[c]
        return c

    por_nombre: dict[str, list] = {}
    for c, ns in nombres_por_ficha.items():
        for n in ns:
            if n:
                por_nombre.setdefault(n, []).append(c)
    for lst in por_nombre.values():
        for c in lst[1:]:
            padre[raiz(c)] = raiz(lst[0])
    por_parranda: dict[str, list] = {}
    for c, ps in parranda_por_ficha.items():
        for p in ps:
            por_parranda.setdefault(p, []).append(c)
    for fichas in por_parranda.values():
        fichas = sorted(set(fichas))
        for i in range(len(fichas)):
            for j in range(i + 1, len(fichas)):
                if any(_parecidos(a, b) for a in nombres_por_ficha[fichas[i]] for b in nombres_por_ficha[fichas[j]]):
                    padre[raiz(fichas[j])] = raiz(fichas[i])
    tamanos: dict[str, int] = {}
    for c in nombres_por_ficha:
        tamanos[raiz(c)] = tamanos.get(raiz(c), 0) + 1

    return {
        "fichas": len(nombres_por_ficha),
        "fichas_compartidas": compartidas,
        "clientes_con_varias_fichas": sum(1 for t in tamanos.values() if t > 1),
    }
