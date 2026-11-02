"""Cuántos CLIENTES compraron, contados por el código del cliente EN VENTRA.

POR QUÉ NO POR EL NOMBRE NI POR EL `C-` DE LA NOTA. El nombre del socio cambia de grafía
(«Geovany» / «Jeovani») y a veces se repite entre personas; el `C-` de la nota lo pega una
operadora desde PEDIDO a mano, y cuando el cliente aún no tiene código lleva su nombre, o la
referencia de una transferencia pegada detrás. Las ventas de mostrador llevan `V-` y ni siquiera
llevan `C-`. En cambio `customerCode` es la identidad que Ventra le da a quien recibe la factura:
está en TODAS las líneas, venga pedido o no, y no depende de lo que alguien copie.

No es el código de Parranda (CM01TCP0629): son dos sistemas, y mezclarlos contaría dos veces al
mismo cliente. Esto cuenta clientes; el cruce con el código de Parranda es otro asunto.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

from services.loader import STD_COLS
from services.ventra import COL_CLIENTE_CODIGO


def _norm(s) -> str:
    t = unicodedata.normalize("NFKD", str(s or "").upper()).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", t)


def contar_clientes(df: pd.DataFrame) -> dict | None:
    """{por_nombre, por_codigo, sin_codigo} o None si todavía no hay códigos de Ventra guardados.

    `por_codigo`: códigos de Ventra distintos, más los clientes de líneas SIN código contados por
    nombre (una línea vieja, sin rellenar, no debe desaparecer del total).
    """
    if df is None or df.empty or COL_CLIENTE_CODIGO not in df.columns:
        return None
    socio = STD_COLS["socio"]
    cod = df[COL_CLIENTE_CODIGO].where(df[COL_CLIENTE_CODIGO].notna(), None)
    cod = cod.map(lambda v: None if v is None or str(v).strip() == "" else str(v).strip())
    if cod.notna().sum() == 0:
        return None  # aún no se han rellenado: mejor no enseñar nada que enseñar un número a medias

    nombres = df[socio].map(_norm)
    con = cod.notna()
    codigos = set(cod[con])
    # Clientes de líneas sin código: por nombre, y solo los que no aparecen ya con código
    nombres_con_codigo = set(nombres[con])
    sin_codigo = {n for n in nombres[~con] if n and n not in nombres_con_codigo}
    return {
        "por_nombre": int(nombres[nombres != ""].nunique()),
        "por_codigo": len(codigos) + len(sin_codigo),
        "sin_codigo": len(sin_codigo),
    }
