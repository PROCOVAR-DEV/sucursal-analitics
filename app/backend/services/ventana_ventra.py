"""Qué ventana de Ventra se vuelve a leer, y cuándo toca el repaso de cierre. Reglas puras.

Aparte de `ventra_sync` porque ahí dentro todo toca Postgres y esto no toca nada: son dos
cuentas de fechas, que es justo lo que hay que poder probar sin base de datos.

# Por qué el MES y no unos días

Analitics guarda una COPIA de Ventra. Si en Ventra corrigen una nota o anulan una línea, la
copia solo se entera si ese día se vuelve a leer. Con 2-3 días de ventana, lo corregido
pasado ese plazo se quedaba viejo para siempre: el 16/10/2026 tres facturas de Holguín del
01/10 seguían saliendo «sin vendedor» cuando Ventra ya llevaba el vendedor desde hacía días.
Pedidos no lo sufre porque su cotejo repasa el mes entero a las 18:30; aquí se hace igual.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

#: Hasta qué día del mes se sigue repasando también el mes anterior: el cierre de un mes se
#: corrige en los primeros días del siguiente.
DIAS_CIERRE_MES_ANTERIOR = 7

#: La hora de Cuba del repaso de cierre. Las 18:00 es cuando cierran las sucursales; media
#: hora más, como el cotejo de Pedidos, para no pelearse con lo que se factura a última hora.
HORA_CIERRE = (18, 30)


def desde_del_repaso(hoy: date) -> date:
    """El primer día que el repaso vuelve a leer: el 1 del mes, o el del anterior en el cierre."""
    primero = hoy.replace(day=1)

    if hoy.day <= DIAS_CIERRE_MES_ANTERIOR:
        return (primero - timedelta(days=1)).replace(day=1)

    return primero


def dias_del_repaso(hoy: date) -> int:
    """Cuántos días atrás llega el repaso (para `al_dia`, que cuenta en días)."""
    return (hoy - desde_del_repaso(hoy)).days


def toca_cierre(ahora: datetime, ultimo_cierre: date | None) -> bool:
    """¿Ya pasó la hora de cierre (hora de Cuba) y hoy todavía no se hizo el repaso?

    `ahora` tiene que venir ya en hora de Cuba: con el servidor en UTC, «las 18:30» serían las
    14:30, con las sucursales facturando todavía.
    """
    return (ahora.hour, ahora.minute) >= HORA_CIERRE and ultimo_cierre != ahora.date()
