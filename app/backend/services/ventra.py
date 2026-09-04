"""Leer el Reporte de Venta desde VENTRA, en vez de que alguien suba un Excel.

# Por qué

Hasta ahora, para ver los informes de una sucursal había que exportar el Reporte de Venta
del sistema, mandarlo y subirlo a mano. Ventra ya tiene ese mismo dato —de las diez bases,
con más de un año de histórico— y lo sirve por API. El Excel deja de hacer falta.

# Es el MISMO dato

Comprobado contra el Ventra de producción el 04/09/2026, columna por columna:

    No. de Operación   -> operNumber        Cantidad          -> quantity
    Fecha/Hora         -> date              Precio de Venta   -> priceOut
    Mercancía          -> productName       Entidad           -> objectName
    Nombre de socio    -> customerName      Nota              -> note

Y cuadra al céntimo: Camagüey del 1 al 3 de julio da `DEYANIRA 5.069,70`, el mismo número
que la hoja Supervisor del Excel generado por los scripts originales.

# Lo que este módulo NO hace

No calcula nada de negocio. Deja las mismas columnas estables que deja `loader.py` desde el
Excel, y de ahí para abajo —`enrich_for_sucursal`, ventas, productos, market, parranda,
ranking— no cambia nada. Si algún día un informe sale distinto según de dónde vinieran las
filas, es que este módulo está mal.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd
import requests

from services.loader import STD_COLS, ReportData

BASE_URL = os.environ.get("VENTRA_API_URL", "http://10.188.2.2:3001/api/external-api")
TOKEN = os.environ.get("VENTRA_API_TOKEN") or os.environ.get("WAREHOUSE_API_TOKEN") or ""

# Es un ERP al otro lado de una VPN, no una API de al lado. Pero CON tope: sin él, un
# Ventra colgado deja la sincronización esperando para siempre y no vuelve a correr.
TIMEOUT_S = int(os.environ.get("VENTRA_TIMEOUT_S", "60"))

# Ventra no pagina las ventas: sólo acepta `limit`. Un mes de la sucursal más grande son
# ~5.000 líneas, así que se pide de sobra y se trae por meses, nunca el año de una vez.
TOPE_LINEAS = int(os.environ.get("VENTRA_LIMIT", "50000"))

# El único tipo de operación que aparece en las líneas de venta, en las diez bases.
# Se filtra a propósito: el día que Ventra empiece a devolver devoluciones o traslados por
# el mismo endpoint, esto los deja fuera en vez de sumarlos a las ventas en silencio.
OPER_TYPE_VENTA = 2

# Columnas nuevas que el Excel no traía. Van aquí y no en `STD_COLS` porque son de esta
# fuente: un informe que las use tiene que tolerar que no estén.
COL_OBJETO = "Objeto"
COL_TIPO_PUNTO = "TipoPunto"
COL_BASE = "BaseVentra"


class VentraNoDisponible(RuntimeError):
    """Ventra no contestó. No es un fallo de programación: la VPN se cae."""


# --------------------------------------------------------------------------------------
# Tipo de punto
# --------------------------------------------------------------------------------------

# Cada base llama a sus objetos como quiere. Medido en agosto de 2026:
#
#   camaguey      PV CAMAGUEY · ALM CAMAGUEY · FLORIDA
#   guantanamo    PV GTMO · ALM CENTRAL · PTO MONEDERO
#   habana        HABANA HACENDADO · PUNTO J
#   santiago      AURORA · PV-STGO · PTO MONEDERO
#   sspiritus     ALM S-SPIRITUS · TIENDA S-SPIRITUS
#   moa           ALMACEN MOA
#
# Tres familias con diez nombres. Se clasifica por reglas, y lo que no encaja se queda en
# `sin_clasificar` A PROPÓSITO: meter AURORA en "punto de venta" porque suena a tienda es
# inventarse un dato que después alguien suma.
PUNTO_VENTA = "punto_venta"
ALMACEN = "almacen"
MONEDERO = "monedero"
SIN_CLASIFICAR = "sin_clasificar"

# Los que no se pueden deducir del nombre. Hay que preguntar qué son; mientras tanto se
# ven como lo que son —desconocidos— en vez de esconderse en un cajón equivocado.
EXCEPCIONES: dict[str, str] = {
    # "AURORA": ALMACEN,
    # "FLORIDA": PUNTO_VENTA,
    # "HABANA HACENDADO": ALMACEN,
    # "PUNTO J": PUNTO_VENTA,
}


def tipo_de_punto(objeto: str | None) -> str:
    """De qué tipo es un `objectName` de Ventra.

    El nombre crudo se guarda igual, siempre: esto es una etiqueta al lado, no un
    reemplazo. Si mañana se descubre que AURORA es un almacén, se corrige aquí y se
    recalcula, sin haber perdido el nombre original.
    """
    n = (objeto or "").strip().upper()

    if not n:
        return SIN_CLASIFICAR
    if n in EXCEPCIONES:
        return EXCEPCIONES[n]
    if "MONEDERO" in n:
        return MONEDERO
    if n.startswith(("PV ", "PV-", "PV_", "TIENDA")):
        return PUNTO_VENTA
    if n.startswith(("ALM", "ALMACEN", "ALMACÉN")):
        return ALMACEN
    return SIN_CLASIFICAR


# --------------------------------------------------------------------------------------
# Hablar con Ventra
# --------------------------------------------------------------------------------------

def _get(ruta: str) -> Any:
    if not TOKEN:
        raise VentraNoDisponible("falta VENTRA_API_TOKEN")
    try:
        r = requests.get(
            f"{BASE_URL}{ruta}",
            headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
            timeout=TIMEOUT_S,
        )
    except requests.RequestException as e:
        raise VentraNoDisponible(f"no se pudo llegar a Ventra: {e}") from e
    if r.status_code != 200:
        raise VentraNoDisponible(f"Ventra {r.status_code} en {ruta}: {r.text[:200]}")
    return r.json()


def bases() -> list[dict[str, Any]]:
    """Las bases (sucursales) que Ventra tiene configuradas.

    Se PREGUNTAN, no se deducen del nombre de nuestras sucursales: los slugs no se parecen
    a lo que uno supondría —`granma` es BAYAMO, `tunas` es LAS TUNAS, `sspiritus` es Sancti
    Spíritus— y adivinar falla en cuatro de diez. Además son DIEZ bases para ocho
    sucursales: `moa` y `palmasoriano` van por su cuenta, y quien asuma una base por
    sucursal se las deja fuera sin enterarse.
    """
    d = _get("/axis/databases")
    filas = d if isinstance(d, list) else (d.get("items") or d.get("data") or [])
    return [
        {
            "database": f.get("database"),
            "branchName": f.get("branchName"),
            "connected": bool(f.get("connected", True)),
        }
        for f in filas
        if f.get("database")
    ]


def _dia(v: date | datetime | str) -> str:
    if isinstance(v, str):
        return v[:10]
    return v.strftime("%Y-%m-%d")


def ventas_crudas(base: str, desde: date | str, hasta: date | str) -> list[dict[str, Any]]:
    """Las líneas de venta de UNA base entre dos fechas, tal como las da Ventra."""
    d = _get(
        f"/axis/sales?database={base}&from={_dia(desde)}&to={_dia(hasta)}&limit={TOPE_LINEAS}"
    )
    filas = d.get("rows") if isinstance(d, dict) else d
    return list(filas or [])


# --------------------------------------------------------------------------------------
# De Ventra a las columnas estables
# --------------------------------------------------------------------------------------

def _importe(fila: dict[str, Any]) -> float:
    """Lo que el Excel traía ya calculado y Ventra no.

    `quantity × priceOut − discount`. El descuento se resta porque es lo que de verdad se
    cobró; dejarlo fuera infla las ventas de quien más descuenta, que es justo a quien hay
    que poder mirar.
    """
    cant = pd.to_numeric(fila.get("quantity"), errors="coerce")
    precio = pd.to_numeric(fila.get("priceOut"), errors="coerce")
    dto = pd.to_numeric(fila.get("discount"), errors="coerce")
    cant = 0.0 if pd.isna(cant) else float(cant)
    precio = 0.0 if pd.isna(precio) else float(precio)
    dto = 0.0 if pd.isna(dto) else float(dto)
    return cant * precio - dto


def a_dataframe(filas: Iterable[dict[str, Any]], base: str = "") -> pd.DataFrame:
    """Las líneas de Ventra, con los mismos nombres de columna que deja el Excel.

    A partir de aquí el resto de la aplicación no puede notar de dónde vinieron.
    """
    datos = []

    for f in filas:
        # Sólo ventas. Ver OPER_TYPE_VENTA.
        if f.get("operType") is not None and int(f.get("operType")) != OPER_TYPE_VENTA:
            continue
        objeto = (f.get("objectName") or "").strip()
        datos.append(
            {
                STD_COLS["op"]: f.get("operNumber"),
                STD_COLS["fecha"]: f.get("date"),
                STD_COLS["socio"]: (f.get("customerName") or "").strip(),
                STD_COLS["merc"]: (f.get("productName") or "").strip(),
                STD_COLS["grupo"]: (f.get("category") or "").strip(),
                STD_COLS["cant"]: f.get("quantity"),
                STD_COLS["importe"]: _importe(f),
                STD_COLS["nota"]: f.get("note"),
                COL_OBJETO: objeto,
                COL_TIPO_PUNTO: tipo_de_punto(objeto),
                COL_BASE: base,
            }
        )

    df = pd.DataFrame(datos, columns=[
        STD_COLS["op"], STD_COLS["fecha"], STD_COLS["socio"], STD_COLS["merc"],
        STD_COLS["grupo"], STD_COLS["cant"], STD_COLS["importe"], STD_COLS["nota"],
        COL_OBJETO, COL_TIPO_PUNTO, COL_BASE,
    ])

    if df.empty:
        return df

    # `date` llega como medianoche LOCAL de Cuba expresada en UTC ("2026-09-02T04:00:00Z").
    # Se quita la zona antes de nada: comparar por día en UTC mueve las ventas de un día al
    # anterior en los bordes del mes, y entonces los informes de fin de mes no cuadran con
    # los del principio del siguiente.
    fecha = pd.to_datetime(df[STD_COLS["fecha"]], errors="coerce", utc=True)
    df[STD_COLS["fecha"]] = fecha.dt.tz_convert("America/Havana").dt.tz_localize(None)

    df[STD_COLS["op"]] = pd.to_numeric(df[STD_COLS["op"]], errors="coerce").astype("Int64")
    for c in (STD_COLS["cant"], STD_COLS["importe"]):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # El mismo segmento de vendedor que saca el loader del Excel, con la misma función:
    # dos formas de calcular el gestor son dos números que un día no coinciden.
    from core.utils import normalize_text
    df[STD_COLS["vseg"]] = df[STD_COLS["nota"]].apply(
        lambda v: normalize_text(_solo_segmento_v(v))
    )

    return df


_RE_V = re.compile(r"(?:^|;)\s*V[-:]\s*([^;]+)", re.IGNORECASE)


def _solo_segmento_v(nota: str | None) -> str:
    """El vendedor, y SÓLO del segmento `V-`. Sin `V-`, vacío.

    `core.utils.extract_vendor_segment` devuelve la nota ENTERA cuando no encuentra `V-`, y
    eso aquí no vale: la nota lleva también `C-<cliente>`, y hay clientes que se llaman como
    un gestor —«CONSUMO PROPIO (ALEXANDER)»—, así que la venta acaba atribuida a quien no
    la hizo. Con el Excel el daño era pequeño porque casi todas las notas traían `V-`; con
    Ventra no: en Palma Soriano y Moa NINGUNA lo trae, y el 100 % de sus ventas se
    repartiría entre gestores inventados.

    Lo que no trae vendedor se queda sin vendedor, y se cuenta aparte. Ver `sin_vendedor`.
    """
    m = _RE_V.search(str(nota) if nota is not None else "")
    return m.group(1).strip() if m else ""


def sin_vendedor(df: pd.DataFrame) -> tuple[int, float]:
    """Cuántas líneas no traen `V-` y cuánto importe suman.

    Es un número que hay que ENSEÑAR, no esconder. Cada sucursal empezó a escribir la nota
    en una fecha distinta —Santiago en enero de 2026, Camagüey en mayo, Granma en agosto— y
    Moa y Palma Soriano no han empezado. Un informe por gestor de antes de esa fecha no
    está vacío por un fallo: es que el dato no existía.
    """
    if df.empty or STD_COLS["vseg"] not in df.columns:
        return 0, 0.0
    faltan = df[df[STD_COLS["vseg"]].fillna("").str.strip() == ""]
    return len(faltan), float(faltan[STD_COLS["importe"]].sum())


def cargar(base: str, desde: date | str, hasta: date | str) -> ReportData:
    """Un `ReportData` como el que sale del Excel, pero traído de Ventra."""
    df = a_dataframe(ventas_crudas(base, desde, hasta), base=base)
    fechas = df[STD_COLS["fecha"]].dropna() if not df.empty else pd.Series(dtype="datetime64[ns]")

    return ReportData(
        df=df,
        date_min=fechas.min() if not fechas.empty else None,
        date_max=fechas.max() if not fechas.empty else None,
        filename=f"ventra:{base} {_dia(desde)}..{_dia(hasta)}",
    )
