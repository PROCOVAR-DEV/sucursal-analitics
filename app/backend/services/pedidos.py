"""Conexión con la app PEDIDO para traer la cantidad de pedidos por cliente.

Best-effort: si PEDIDO no está configurado o no responde, devuelve {} y la vista
de clientes simplemente no muestra el conteo (no rompe nada).

Config por variables de entorno:
  PEDIDO_API_URL   ej: http://localhost:8400
  PEDIDO_API_KEY   (o SERVICE_API_KEY)  el x-api-key compartido con PEDIDO
"""
from __future__ import annotations

import os
import time

import httpx

from core.utils import normalize_text

_TTL = 60.0  # segundos de cache para no golpear PEDIDO en cada carga
_CACHE: dict = {"at": 0.0, "data": {}}


def fetch_order_counts() -> dict[str, int]:
    """Mapa {nombre_normalizado: cantidad_pedidos} desde la API de PEDIDO."""
    base = os.getenv("PEDIDO_API_URL")
    key = os.getenv("PEDIDO_API_KEY") or os.getenv("SERVICE_API_KEY")
    if not base or not key:
        return {}

    now = time.time()
    if _CACHE["data"] and (now - _CACHE["at"]) < _TTL:
        return _CACHE["data"]

    try:
        resp = httpx.get(
            f"{base.rstrip('/')}/integration/client-order-counts",
            headers={"x-api-key": key},
            timeout=5.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        out: dict[str, int] = {}
        for row in payload.get("counts", []):
            nombre = normalize_text(row.get("nombre"))
            if nombre:
                out[nombre] = out.get(nombre, 0) + int(row.get("pedidos") or 0)
        _CACHE["at"] = now
        _CACHE["data"] = out
        return out
    except Exception:
        # PEDIDO caído / mal configurado: no rompe la vista de clientes.
        return {}
