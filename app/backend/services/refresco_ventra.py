"""Traer de Ventra AHORA, sucursal por sucursal y con freno.

# Por qué existe

Ventra se trae solo cada hora y hay además la recarga de las 6. Entre medias, quien acaba
de facturar y quiere ver su número tiene que esperar sin saber cuánto. Este es el botón
para no esperar.

# Las tres cosas que NO puede hacer

1. **Traer lo de otra sucursal.** Se traduce el `sid` a SU base con `base_de()` y se trae
   sólo esa. Si esa sucursal no tiene base, se dice y no se trae nada: enseñarle las
   ventas de otra sería peor que no enseñarle ninguna.
2. **Gastarse los requests.** Ventra no es nuestro y no aguanta que diez personas pulsen
   un botón en bucle. Hay un tope por sucursal y por hora, y una espera mínima entre dos
   refrescos seguidos.
3. **Pisarse consigo mismo.** Dos pulsaciones a la vez sobre la misma sucursal harían el
   mismo trabajo dos veces contra Ventra. La segunda espera a la primera.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, timedelta

from services import ventra, ventra_sync
from services.ventra_sucursales import base_de

log = logging.getLogger(__name__)

# Cuántos días se vuelven a pedir. Los mismos que el bucle automático: lo de hoy y lo de
# ayer, que es donde se mueve todo. Pedir más es pedirle a Ventra un histórico que ya
# tenemos.
DIAS = 2

# El freno. Seis por hora es uno cada diez minutos de media: de sobra para «acabo de
# facturar y quiero verlo», y lejos de poder hacerle daño a Ventra.
TOPE_POR_HORA = 6
ESPERA_MINIMA_S = 60

_candado = threading.Lock()
_por_sucursal: dict[str, threading.Lock] = {}
# sid -> lista de marcas de tiempo de los refrescos hechos
_hechos: dict[str, list[float]] = {}


def _mi_candado(sid: str) -> threading.Lock:
    with _candado:
        return _por_sucursal.setdefault(sid, threading.Lock())


def _limpiar(sid: str, ahora: float) -> list[float]:
    """Las marcas de la última hora. Las viejas se tiran: el tope es por hora, no total."""
    quedan = [t for t in _hechos.get(sid, []) if ahora - t < 3600]
    _hechos[sid] = quedan

    return quedan


def cuanto_queda(sid: str) -> dict:
    """Si se puede refrescar ahora, y si no, cuánto falta. Para pintar el botón."""
    ahora = time.time()

    with _candado:
        hechos = _limpiar(sid, ahora)

    if not base_de(sid):
        return {"puede": False, "motivo": "esta sucursal no tiene base en Ventra", "restantes": 0}

    if len(hechos) >= TOPE_POR_HORA:
        espera = int(3600 - (ahora - min(hechos)))

        return {"puede": False, "motivo": f"ya se refrescó {TOPE_POR_HORA} veces esta hora",
                "restantes": 0, "segundos": max(espera, 1)}

    if hechos and ahora - max(hechos) < ESPERA_MINIMA_S:
        espera = int(ESPERA_MINIMA_S - (ahora - max(hechos)))

        return {"puede": False, "motivo": "hace muy poco del último",
                "restantes": TOPE_POR_HORA - len(hechos), "segundos": max(espera, 1)}

    return {"puede": True, "restantes": TOPE_POR_HORA - len(hechos)}


def refrescar(sid: str) -> dict:
    """Trae de Ventra los últimos días de ESA sucursal. Devuelve qué pasó."""
    base = base_de(sid)

    if not base:
        return {"ok": False, "motivo": "esta sucursal no tiene base en Ventra"}

    estado = cuanto_queda(sid)

    if not estado["puede"]:
        return {"ok": False, **estado}

    # Se apunta ANTES de traer, no después: si se apuntara al terminar, diez pulsaciones
    # en el mismo segundo pasarían todas el freno y saldrían diez veces contra Ventra.
    with _candado:
        _hechos.setdefault(sid, []).append(time.time())

    hasta = date.today()
    desde = hasta - timedelta(days=DIAS)

    with _mi_candado(sid):
        try:
            n, sin_v, imp = ventra_sync._traer(base, desde, hasta)
        except ventra.VentraNoDisponible as e:
            log.warning("[ventra/manual] %s (%s) no disponible: %s", sid, base, e)

            return {"ok": False, "motivo": f"Ventra no responde ahora mismo: {e}"}

    log.info("[ventra/manual] %s (%s): %d lineas %s..%s", sid, base, n, desde, hasta)

    return {
        "ok": True,
        "base": base,
        "lineas": n,
        "desde": str(desde),
        "hasta": str(hasta),
        "sin_vendedor": sin_v,
        "importe_sin_vendedor": round(imp, 2),
        "restantes": cuanto_queda(sid).get("restantes", 0),
    }
