"""Cuotas y KPIs: los lleva el CRM, Analytics solo los LEE (Jose, 13/10/2026).

Lo que se lee y por qué está en el CRM: `docs/2026-10-13-analytics-lee-del-crm.md`
(repo PROCOVAR-DEV/procovar-crm). Aquí, tres cosas:

1. `aplicar_cuotas(eff, ...)`: si el CRM tiene cuotas de esa sucursal y mes, las metas
   de cada gestor (`cuota_hl`, `metas_formato`, `metas_cantidad`) y los totales de la
   sucursal salen de ahí, no de `metas_mensuales`. Lo llama `config_for_period`, que es
   por donde pasa TODA la configuración: así ninguna vista se queda con la mitad.
2. `kpis_por_clave(eff, sid)`: los KPI del mes (visitas, pedidos, efectividad...) por
   gestor de Analytics, para enseñarlos al lado de las ventas.
3. Sin configurar, o si el CRM no contesta o no tiene cuotas ese mes, NO cambia nada:
   Analytics sigue con sus metas como siempre. Así se puede desplegar antes que el CRM.

Variables de entorno (sin valores en el repo):
  CRM_API_URL    base de la API, p. ej. https://crm.procovar.cloud/api/v1
  CRM_API_TOKEN  el TOKEN_SERVICIO del CRM

Cómo se casa un gestor del CRM (sub de Accesos) con la CLAVE de Analytics: por su
código de vendedor de Accesos puesto como alias (o como clave), o, si no, por nombre
completo igual al nombre, la clave o un alias. Lo que no casa no se inventa: sale en
`eff["_crm_sin_casar"]`.
"""
from __future__ import annotations

import logging
import os
import time

import httpx

from core.utils import detect_size, normalize_text

log = logging.getLogger(__name__)

# Slug de Analytics -> código de sucursal de Accesos / CRM.
CODIGO_SUCURSAL = {
    "camaguey": "CAM",
    "granma": "GR",
    "guantanamo": "GTO",
    "la-habana": "HAB",
    "holguin": "HOL",
    "sancti-spiritus": "SS",
    "santiago-de-cuba": "STG",
    "las-tunas": "TUN",
}

_TTL = 60.0  # config_for_period se llama muchas veces por petición
_TAMANO = 200  # el máximo que sirve el CRM
_CACHE: dict = {}


def configurado() -> bool:
    return bool(os.getenv("CRM_API_URL") and os.getenv("CRM_API_TOKEN"))


def _leer(ruta: str, params: dict) -> list | None:
    """Todas las páginas de una lectura; None si el CRM falla (no rompe nada)."""
    base = os.getenv("CRM_API_URL", "").rstrip("/")
    cabeceras = {"Authorization": f"Bearer {os.getenv('CRM_API_TOKEN', '')}"}
    filas: list = []
    pagina = 1
    try:
        while True:
            resp = httpx.get(f"{base}{ruta}", headers=cabeceras, timeout=5.0,
                             params={**params, "pagina": pagina, "tamano": _TAMANO})
            resp.raise_for_status()
            datos = resp.json().get("datos") or []
            filas.extend(datos)
            if len(datos) < _TAMANO:
                return filas
            pagina += 1
    except Exception as exc:  # CRM caído o mal configurado: Analytics sigue como antes
        log.warning("CRM no disponible en %s: %s", ruta, exc)
        return None


def _cacheado(ruta: str, sid: str, anio: int, mes: int) -> list | None:
    codigo = CODIGO_SUCURSAL.get(sid)
    if not codigo or not configurado():
        return None
    clave = (ruta, codigo, anio, mes)
    hit = _CACHE.get(clave)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    filas = _leer(ruta, {"anio": anio, "mes": mes, "sucursal": codigo})
    _CACHE[clave] = (time.time(), filas)  # también el fallo: no esperar 5 s en cada vista
    return filas


def huella() -> str:
    """Para la clave de la caché del Resumen: las cuotas del CRM cambian sin que cambie
    nada en Analytics. Sin CRM, vacía (la clave de siempre).
    ponytail: tramos de 10 min, no la fecha real de la última cuota; si recalcular el
    Resumen cada 10 min pesa, pedirle al CRM un `actualizado_at` máximo por sucursal."""
    return f"crm:{int(time.time() // 600)}" if configurado() else ""


def casar(gestores: dict, filas: list) -> dict:
    """{sub del CRM: CLAVE de Analytics} para las filas que casan."""
    por_codigo: dict = {}
    por_nombre: dict = {}
    for clave, g in (gestores or {}).items():
        g = g or {}
        for alias in [clave, *(g.get("aliases") or [])]:
            por_codigo[str(alias).strip().upper()] = clave
        for nombre in [clave, g.get("nombre"), *(g.get("aliases") or [])]:
            n = normalize_text(nombre)
            if n:
                por_nombre[n] = clave
    salida: dict = {}
    for f in filas:
        sub = f.get("usuario_id") or f.get("gestor")
        if not sub:
            continue
        codigo = str(f.get("codigo_vendedor") or "").strip().upper()
        clave = (por_codigo.get(codigo) if codigo else None) or por_nombre.get(normalize_text(f.get("nombre")))
        if clave:
            salida[sub] = clave
    return salida


def _formato(producto: str) -> str | None:
    """'PARRANDA 1,5 L' -> 'PARRANDA-1500': la clave con la que se guardan las metas."""
    size = detect_size(producto)
    t = str(producto).upper()
    if not size:
        return None
    if "PARRANDA" in t:
        return f"PARRANDA-{size}"
    if "MALTA" in t or "GUAJIRA" in t:
        return f"MALTA-{size}"
    return None


def aplicar_cuotas(eff: dict, sid: str, anio: int, mes: int) -> dict:
    """Las metas del mes salen de las cuotas del CRM (si las hay)."""
    filas = _cacheado("/integracion/cuotas", sid, anio, mes)
    if not filas:
        return eff

    # Las cuotas no traen el nombre: se casa por el código de vendedor (KPI sí lo trae).
    kpis = _cacheado("/integracion/kpis/gestores", sid, anio, mes) or []
    nombres = {k.get("usuario_id"): k.get("nombre") for k in kpis}
    filas_con_nombre = [{**f, "nombre": nombres.get(f.get("gestor"))} for f in filas]
    sub_a_clave = casar(eff.get("gestores") or {}, filas_con_nombre)

    hl: dict = {}
    formato: dict = {}
    cantidad: dict = {}
    total_hl = 0.0
    productos: dict = {}
    sin_casar: set = set()
    for f in filas:
        cuota_hl = float(f.get("cuota_hectolitros") or 0)
        cuota = float(f.get("cuota") or 0)
        producto = str(f.get("producto") or f.get("sku") or "")
        total_hl += cuota_hl
        if cuota_hl <= 0:
            productos[producto] = productos.get(producto, 0.0) + cuota
        clave = sub_a_clave.get(f.get("gestor"))
        if not clave:
            sin_casar.add(f.get("codigo_vendedor") or f.get("gestor") or "(sin gestor)")
            continue
        if cuota_hl > 0:
            hl[clave] = hl.get(clave, 0.0) + cuota_hl
            fmt = _formato(producto)
            if fmt:
                formato.setdefault(clave, {})
                formato[clave][fmt] = formato[clave].get(fmt, 0.0) + cuota_hl
        else:
            cantidad.setdefault(clave, {})
            cantidad[clave][producto] = cantidad[clave].get(producto, 0.0) + cuota

    eff = dict(eff)
    eff["gestores"] = {
        clave: {
            **(g or {}),
            "cuota_hl": round(hl.get(clave, 0.0), 2),
            "metas_formato": {k: round(v, 2) for k, v in formato.get(clave, {}).items()},
            "metas_cantidad": cantidad.get(clave, {}),
        }
        for clave, g in (eff.get("gestores") or {}).items()
    }
    eff["meta_hectolitros_total"] = round(total_hl, 2)
    eff["metas_productos_ces"] = productos
    eff["_fuente_metas"] = "crm"
    eff["_crm_sin_casar"] = sorted(str(s) for s in sin_casar)
    return eff


def kpis_por_clave(eff: dict, sid: str) -> dict:
    """{CLAVE: kpis del CRM} del mes de `eff`; {} sin CRM o sin mes único."""
    periodo = eff.get("_period")
    if not periodo or not configurado():
        return {}
    filas = _cacheado("/integracion/kpis/gestores", sid, int(periodo[:4]), int(periodo[5:7])) or []
    sub_a_clave = casar(eff.get("gestores") or {}, filas)
    return {sub_a_clave[f["usuario_id"]]: f.get("kpis") or {}
            for f in filas if f.get("usuario_id") in sub_a_clave}
