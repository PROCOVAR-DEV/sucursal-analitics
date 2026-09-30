"""Lo que NO es mercancía: el cobro del reparto facturado como si fuera un producto.

# Qué pasa y por qué

En AxisPOS todo lo que se cobra en una factura tiene que ser una LÍNEA, y toda línea
apunta al catálogo. No hay concepto de cargo ni de servicio aparte. Así que para poder
cobrar el reparto crearon una entrada de catálogo llamada «ENTREGA A DOMICILIO», con
categoría `SERV` y peso cero. Es un cobro disfrazado de producto, y en el reporte de
ventas viene como una mercancía más.

Hasta el 30/09/2026 analitics no lo sabía —ni una mención de domicilio en todo el
código— y sumaba su importe dentro de la Venta Total y dentro del ingreso de cada
vendedor. Medido ese día en Santiago, septiembre de 2026:

    ENTREGA A DOMICILIO    363 líneas    379,26

Sydney lo vio porque su reporte de AXIS y el panel no cuadraban, y dijo lo que importa:
«entonces a los vendedores le salen mal sus ingresos». Un vendedor no vende el reparto:
lo cobra el que conduce. Contárselo como venta le infla la comisión.

# Por qué la regla vive AQUÍ y sólo aquí

Porque se aplica en un único sitio —`only_valid`, el embudo por el que pasan las
veintitrés pantallas— y no repartida por cada servicio que suma dinero. Una regla
escrita en veinte sitios se arregla en diecinueve; PEDIDO tiene la gemela de esto en
`api/src/lib/servicios.ts` y aprendió lo mismo por las malas.

# Lo que NO se hace

No se borra el dato ni se esconde. La línea sigue en la base y se cuenta aparte: el
panel enseña «Entrega a domicilio» al lado de la Venta Total. Restar dinero de un total
sin decir dónde fue es cómo se pierde una tarde buscando por qué no cuadra — que es
exactamente la tarde que costó esto.
"""
from __future__ import annotations

import unicodedata

import pandas as pd

from services.loader import STD_COLS

#: La columna que marca las líneas de servicio. La pone `enrich_for_sucursal`.
COL = "EsServicio"

#: Categorías de Ventra que no son mercancía, por si algún día viene el grupo puesto.
#: Hoy llega vacío en las diez bases (comprobado el 30/09/2026), así que quien decide
#: de verdad es el nombre — pero cuando AXIS empiece a mandarlo, esto ya funciona.
CATEGORIAS = {"serv", "servicio", "servicios"}

#: La frase ENTERA, no una palabra. Un producto que se llamara «CERVEZA ENTREGA» no
#: puede colar por llevar «entrega» dentro.
FRASES = ("entrega a domicilio", "servicio de entrega")


def _limpio(s: object) -> str:
    t = "" if s is None else str(s)
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower().strip()


def es_servicio(mercancia: object, grupo: object = None) -> bool:
    """¿Esta línea es un cobro de servicio y no algo que se vendió?"""
    if _limpio(grupo) in CATEGORIAS:
        return True
    n = _limpio(mercancia)
    return any(f in n for f in FRASES)


def marcar(df: pd.DataFrame) -> pd.DataFrame:
    """Añade la columna `EsServicio`. No quita nada: eso lo hace `only_valid`."""
    merc = STD_COLS["merc"]
    grupo = STD_COLS["grupo"]

    if df.empty or merc not in df.columns:
        df[COL] = pd.Series([False] * len(df), index=df.index, dtype="bool")
        return df

    gvals = df[grupo] if grupo in df.columns else pd.Series([None] * len(df), index=df.index)
    df[COL] = [es_servicio(m, g) for m, g in zip(df[merc], gvals)]
    df[COL] = df[COL].astype("bool")
    return df


def solo_mercancia(df: pd.DataFrame) -> pd.DataFrame:
    """Las filas que son venta de verdad. Si no está marcado, se devuelve tal cual.

    Lo segundo importa: un DataFrame sin la columna viene de un camino que no pasó por
    `enrich`, y ahí es mejor no filtrar que filtrar a ciegas y devolver cero filas.
    """
    if df.empty or COL not in df.columns:
        return df
    return df[~df[COL].astype("bool")]


def importe_de_servicios(df: pd.DataFrame, keys: list[str] | None = None) -> float:
    """Cuánto se cobró de servicio, para poder ENSEÑARLO aparte.

    `keys` son los gestores válidos: se mide lo mismo que el total al que acompaña, o el
    número de al lado no cuadraría con el de arriba por motivos invisibles.
    """
    if df.empty or COL not in df.columns:
        return 0.0
    imp = STD_COLS["importe"]
    if imp not in df.columns:
        return 0.0
    sub = df[df[COL].astype("bool")]
    if keys is not None and "GestorDetectado" in sub.columns:
        sub = sub[sub["GestorDetectado"].isin(keys)]
    return round(float(sub[imp].sum()), 2)
