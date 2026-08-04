"""Ajustes GLOBALES: los que no son de una sucursal concreta.

Hoy solo guarda las reglas de comisión de ámbito global — las que valen para
todas las sucursales a la vez — pero está pensado para cualquier ajuste que no
tenga dueño. Es clave/valor porque lo global es poco y muy variado; una tabla
por ajuste sería una migración cada vez que aparezca uno nuevo.
"""
from __future__ import annotations

from services.db import Ajuste, session_scope

CLAVE_REGLAS_COMISION = "reglas_comision"


def leer(clave: str, por_defecto=None):
    with session_scope() as s:
        row = s.query(Ajuste).filter_by(clave=clave).one_or_none()
        return (row.valor or {}).get("v", por_defecto) if row else por_defecto


def guardar(clave: str, valor) -> None:
    # El valor se envuelve en {"v": ...} para poder guardar también listas: una
    # columna JSONB acepta cualquier JSON, pero el modelo la declara como dict y
    # así no hay que pelearse con el tipo según lo que toque guardar.
    with session_scope() as s:
        row = s.query(Ajuste).filter_by(clave=clave).one_or_none()
        if row is None:
            s.add(Ajuste(clave=clave, valor={"v": valor}))
        else:
            row.valor = {"v": valor}


def marca_de_tiempo() -> str:
    """Última modificación de CUALQUIER ajuste global.

    La usa la caché: si cambia una regla global, los resultados guardados de
    TODAS las sucursales dejan de valer. Sin esto habría que acordarse de purgar
    a mano y, el día que se olvidara, unas sucursales cobrarían con la regla
    nueva y otras con la vieja.
    """
    try:
        with session_scope() as s:
            filas = s.query(Ajuste.updated_at).all()
            return max((str(f[0]) for f in filas), default="sin-ajustes")
    except Exception:
        return "sin-ajustes"


def reglas_comision_globales() -> list[dict]:
    return list(leer(CLAVE_REGLAS_COMISION, []) or [])


def guardar_reglas_comision_globales(reglas: list[dict]) -> None:
    guardar(CLAVE_REGLAS_COMISION, list(reglas))
