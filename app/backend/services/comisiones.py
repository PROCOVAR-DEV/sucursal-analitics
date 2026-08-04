"""Reglas de comisión por producto, con vigencia por periodo.

Hasta ahora la comisión del gestor era UN porcentaje plano sobre todo lo vendido
(`comision_gestor_pct`). Eso sigue siendo el suelo: lo que no tenga regla propia
cobra ese porcentaje y los números no cambian. Encima se pueden poner reglas por
producto — arroz al 2%, Parranda al 0,8% — y varias a la vez.

Tres decisiones que gobiernan todo este módulo:

1. **La vigencia se mide en MESES, no en días.** Todo el sistema calcula por
   periodo (año, mes) y los informes se sacan por mes cerrado. Si la vigencia
   fuera por día habría meses partidos, con dos porcentajes dentro del mismo
   informe y un total que no cuadra con ninguno de los dos.

2. **Hacia adelante y nunca hacia atrás.** Una regla creada hoy no puede tocar
   un mes ya pasado: lo pagado está pagado y recalcularlo cambiaría cifras que
   alguien ya cobró y firmó. Por eso `desde` nunca puede ser anterior al mes en
   curso, y esto se comprueba al guardar, no al calcular.

3. **Gana la más ESPECÍFICA; entre iguales, la más nueva.** «ARROZ» cubre todos
   los arroces y «ARROZ PATEKO» solo ese, y la de ese manda para ese. Cuando dos
   reglas apuntan a lo MISMO no se prohíbe el solape: se avisa y se aplica la
   última creada, que es lo que pidió Jose. Prohibirlo obligaría a editar la
   vieja antes de poder crear la nueva, y lo normal es justamente "desde ahora,
   esto pasa a ser 2%".

Este módulo es puro: entra config y sale número. No toca base de datos ni
peticiones, para poder probarlo entero sin levantar nada.
"""
from __future__ import annotations

import pandas as pd

from services.loader import STD_COLS


# Tipos de objetivo que puede tener una regla. Se corresponden con las dos formas
# en que ya se clasifica una línea en el resto del sistema: por su grupo comercial
# (PARRANDA, IMPORTACIONES...) o por lo que diga el nombre del producto (ARROZ).
# No se inventa un tercer criterio a propósito: si aquí se clasificara distinto,
# una regla podría cuadrar con lo que el usuario ve en "Grupos y productos" y no
# con lo que cobra.
TIPO_GRUPO = "grupo"
TIPO_PRODUCTO = "producto"

# Ámbito: una regla puede valer para TODAS las sucursales o solo para una. Lo de
# la sucursal manda sobre lo global cuando apuntan a lo mismo — que es lo que
# significa poner algo en una sucursal concreta: una excepción a lo general.
AMBITO_GLOBAL = "global"
AMBITO_SUCURSAL = "sucursal"


def clave_precedencia(r: dict) -> tuple:
    """Cuánto manda una regla. Mayor = gana.

    Es UNA sola función para que el cálculo y el aviso de solape no puedan
    discrepar: si el aviso dijera que gana una y luego se aplicara otra, el aviso
    sería peor que no tenerlo.
    """
    return (
        1 if r.get("tipo") != TIPO_GRUPO else 0,          # producto concreto > grupo entero
        len(str(r.get("objetivo") or "").strip()),        # objetivo más largo = más específico
        1 if r.get("ambito") == AMBITO_SUCURSAL else 0,   # la sucursal manda sobre lo global
        str(r.get("creada") or ""),                       # y entre iguales, la más nueva
        str(r.get("id") or ""),                           # desempate estable
    )


def _mes(valor) -> str:
    """Normaliza a 'YYYY-MM'. Devuelve '' si no se puede."""
    t = str(valor or "").strip()
    if len(t) >= 7 and t[4] == "-":
        return t[:7]
    return ""


def _vigente(regla: dict, periodo: str) -> bool:
    """¿Esta regla está en vigor en este mes?

    `hasta` vacío significa "sigue vigente": es el caso normal mientras nadie
    diga lo contrario. Cerrarla es poner el último mes en que se aplicó.
    """
    desde = _mes(regla.get("desde"))
    hasta = _mes(regla.get("hasta"))
    if not desde or not periodo:
        return False
    if periodo < desde:
        return False
    return not hasta or periodo <= hasta


def reglas_vigentes(reglas: list[dict], periodo: str) -> list[dict]:
    """Reglas en vigor en `periodo`, ordenadas por PRECEDENCIA.

    El orden ES la precedencia: para una línea que encaje con varias, se coge la
    primera. Manda la MÁS ESPECÍFICA, no la más nueva:

      «ARROZ» al 2%  +  «ARROZ PATEKO» al 3%
        -> el Pateko cobra 3%, el resto de arroces 2%.

    Que es como lo diría cualquiera: pongo una regla para los arroces y luego
    afino una para uno concreto. Si mandara la más nueva, crear la genérica
    después se llevaría por delante la del producto concreto sin avisar, y el
    Pateko volvería al 2% sin que nadie hubiera tocado su regla.

    El criterio, en orden:

    1. Producto concreto antes que grupo entero. Nombrar un producto es más
       intencionado que caer dentro de un grupo.
    2. Objetivo más largo antes que más corto. «ARROZ PATEKO» describe menos
       cosas que «ARROZ», así que es la que se quería para esa línea.
    3. Entre reglas igual de específicas, la de la SUCURSAL antes que la global.
       Poner una regla en una sucursal concreta es justamente decir "aquí no,
       aquí es otra cosa".
    4. Y solo entre reglas del mismo ámbito, la más nueva. Ese es el caso del
       solape de verdad: dos reglas para lo mismo, y gana la última.
    5. Por `id` al final, para que dos creadas en el mismo segundo se resuelvan
       siempre igual y no según el orden en que salieron del JSON.
    """
    activas = [r for r in (reglas or []) if r.get("activa", True) and _vigente(r, periodo)]
    return sorted(activas, key=clave_precedencia, reverse=True)


def _encaja(regla: dict, grupo: str, producto: str) -> bool:
    objetivo = str(regla.get("objetivo") or "").strip().upper()
    if not objetivo:
        return False
    if regla.get("tipo") == TIPO_GRUPO:
        return grupo.strip().upper() == objetivo
    return objetivo in producto.upper()


def pct_de_linea(regla_por_defecto: float, vigentes: list[dict], grupo: str, producto: str) -> tuple[float, str | None]:
    """Porcentaje que le toca a una línea, y el id de la regla que lo decidió.

    Devuelve `(pct, None)` cuando no encaja ninguna regla: ese es el caso de la
    comisión general de siempre.
    """
    for r in vigentes:
        if _encaja(r, grupo, producto):
            return float(r.get("pct") or 0.0), str(r.get("id") or "")
    return float(regla_por_defecto), None


def comision_de(df: pd.DataFrame, pct_general: float, reglas: list[dict], periodo: str) -> dict:
    """Comisión de un conjunto de líneas, desglosada por regla.

    Devuelve el total y el detalle de qué aportó cada regla, porque un gestor que
    ve solo el total no puede comprobar si le pagaron bien. El desglose es lo que
    convierte esto en algo discutible con un papel delante.

    Con `reglas` vacío el resultado es exactamente `importe_total * pct_general`,
    que es lo que se venía calculando. Esa igualdad es la que garantiza que
    activar esta función no mueva ni un número mientras nadie cree una regla.
    """
    imp = STD_COLS["importe"]
    vacio = {"comision": 0.0, "base": 0.0, "detalle": []}
    if df is None or df.empty or imp not in df.columns:
        return vacio

    vigentes = reglas_vigentes(reglas, periodo)
    merc = STD_COLS["merc"]

    # Camino rápido: sin reglas vigentes no hay nada que mirar línea a línea.
    if not vigentes:
        base = round(float(df[imp].sum()), 2)
        return {"comision": round(base * float(pct_general), 2), "base": base, "detalle": []}

    grupos = df["GrupoComercial"] if "GrupoComercial" in df.columns else pd.Series([""] * len(df), index=df.index)
    prods = df[merc] if merc in df.columns else pd.Series([""] * len(df), index=df.index)
    importes = pd.to_numeric(df[imp], errors="coerce").fillna(0.0)

    # Se acumula por regla en vez de fila a fila para que el desglose salga solo.
    acum: dict[str | None, dict] = {}
    for g, p, v in zip(grupos.fillna(""), prods.fillna(""), importes):
        pct, rid = pct_de_linea(pct_general, vigentes, str(g), str(p))
        a = acum.setdefault(rid, {"pct": pct, "base": 0.0})
        a["base"] += float(v)

    por_id = {str(r.get("id")): r for r in vigentes}
    detalle = []
    total = 0.0
    for rid, a in acum.items():
        com = a["base"] * a["pct"]
        total += com
        r = por_id.get(rid or "")
        detalle.append({
            "regla_id": rid,
            "nombre": (r.get("nombre") if r else None) or "Comisión general",
            "pct": round(a["pct"], 6),
            "base": round(a["base"], 2),
            "comision": round(com, 2),
        })

    # Lo general primero y luego por peso: el desglose se lee de arriba abajo.
    detalle.sort(key=lambda d: (d["regla_id"] is not None, -d["comision"]))
    return {
        "comision": round(total, 2),
        "base": round(float(importes.sum()), 2),
        "detalle": detalle,
    }


def solapes(reglas: list[dict]) -> list[dict]:
    """Pares de reglas que pisan el mismo objetivo en meses que se cruzan.

    No es un error: es un aviso. Se dice cuál manda (la más nueva) para que quien
    la creó vea el efecto de lo que acaba de hacer, en vez de descubrirlo cuando
    no cuadre una nómina.
    """
    activas = [r for r in (reglas or []) if r.get("activa", True)]
    avisos = []
    for i, a in enumerate(activas):
        for b in activas[i + 1:]:
            if str(a.get("tipo")) != str(b.get("tipo")):
                continue
            if str(a.get("objetivo") or "").strip().upper() != str(b.get("objetivo") or "").strip().upper():
                continue

            a_ini, a_fin = _mes(a.get("desde")), _mes(a.get("hasta")) or "9999-12"
            b_ini, b_fin = _mes(b.get("desde")), _mes(b.get("hasta")) or "9999-12"
            if not a_ini or not b_ini or a_ini > b_fin or b_ini > a_fin:
                continue

            gana, pierde = (a, b) if clave_precedencia(a) > clave_precedencia(b) else (b, a)
            avisos.append({
                "objetivo": a.get("objetivo"),
                "tipo": a.get("tipo"),
                "ambitos": sorted({str(a.get("ambito") or AMBITO_SUCURSAL), str(b.get("ambito") or AMBITO_SUCURSAL)}),
                "desde": max(a_ini, b_ini),
                "hasta": None if min(a_fin, b_fin) == "9999-12" else min(a_fin, b_fin),
                "gana": {"id": gana.get("id"), "nombre": gana.get("nombre"), "pct": gana.get("pct"), "ambito": gana.get("ambito")},
                "pierde": {"id": pierde.get("id"), "nombre": pierde.get("nombre"), "pct": pierde.get("pct"), "ambito": pierde.get("ambito")},
                "mensaje": (
                    f"«{gana.get('nombre')}» ({float(gana.get('pct') or 0) * 100:g}%) se solapa con "
                    f"«{pierde.get('nombre')}» ({float(pierde.get('pct') or 0) * 100:g}%) sobre "
                    f"{a.get('objetivo')}. Se aplicará «{gana.get('nombre')}»"
                    + (" (regla de la sucursal, que manda sobre la global)."
                       if gana.get("ambito") != pierde.get("ambito") and gana.get("ambito") == AMBITO_SUCURSAL
                       else " por ser la más nueva.")
                ),
            })
    return avisos


# --------------------------------------------------------------- alta y edición
#
# La validación vive aquí, junto al cálculo, y no en la capa de la API. Es la
# misma razón por la que el motor es puro: estas reglas deciden lo que cobra
# gente, así que tienen que poder probarse sin levantar un servidor.

def mes_actual() -> str:
    from datetime import date

    hoy = date.today()
    return f"{hoy.year:04d}-{hoy.month:02d}"


def _pct_valido(valor) -> float:
    try:
        pct = float(valor)
    except (TypeError, ValueError):
        raise ValueError("El porcentaje no es un número.")
    if pct < 0:
        raise ValueError("El porcentaje no puede ser negativo.")
    if pct > 1:
        raise ValueError(
            "El porcentaje se guarda como fracción: 2% es 0.02, no 2. "
            f"Recibido {pct}, que sería un {pct * 100:g}%."
        )
    return pct


def normalizar_regla(payload: dict, existente: dict | None = None, ahora: str | None = None,
                     ambito: str = AMBITO_SUCURSAL) -> dict:
    """Valida y completa una regla. Lanza `ValueError` con el motivo si no vale.

    El punto importante es que NADA puede empezar ni terminar en un mes ya
    pasado. Una comisión de un mes cerrado ya se calculó, se revisó y se pagó;
    si una regla nueva pudiera alcanzarlo, el mismo informe daría dos cifras
    distintas según cuándo se pidiera, y la de ayer ya está en la nómina de
    alguien. Por eso se corta aquí y no en la pantalla: la pantalla se puede
    saltar, esto no.
    """
    ahora = ahora or mes_actual()
    base = dict(existente or {})

    tipo = str(payload.get("tipo", base.get("tipo") or TIPO_PRODUCTO)).strip().lower()
    if tipo not in (TIPO_GRUPO, TIPO_PRODUCTO):
        raise ValueError(f"Tipo desconocido: «{tipo}». Debe ser «{TIPO_GRUPO}» o «{TIPO_PRODUCTO}».")

    objetivo = str(payload.get("objetivo", base.get("objetivo") or "")).strip()
    if not objetivo:
        raise ValueError(
            "Falta a qué se aplica la regla: un grupo comercial (ej. PARRANDA) "
            "o un texto del nombre del producto (ej. ARROZ)."
        )

    pct = _pct_valido(payload.get("pct", base.get("pct", 0.0)))

    desde = _mes(payload.get("desde", base.get("desde")))
    if not desde:
        raise ValueError("Falta el mes desde el que se aplica (formato AAAA-MM).")
    # Solo se comprueba si CAMBIA: una regla vieja que ya venía de atrás se puede
    # seguir editando (subirle el %, cerrarla) sin que su propio `desde` la bloquee.
    if desde != _mes(base.get("desde")) and desde < ahora:
        raise ValueError(
            f"No se puede aplicar una comisión a un mes ya pasado ({desde}). "
            f"Lo más atrás posible es el mes en curso ({ahora}): lo de meses "
            "cerrados ya se calculó y se pagó."
        )

    hasta = _mes(payload.get("hasta", base.get("hasta"))) or None
    if hasta:
        if hasta < desde:
            raise ValueError(f"El mes final ({hasta}) es anterior al inicial ({desde}).")
        if hasta != _mes(base.get("hasta")) and hasta < ahora:
            raise ValueError(
                f"No se puede cerrar la regla en un mes ya pasado ({hasta}): eso "
                f"cambiaría comisiones ya calculadas. Lo más atrás es {ahora}."
            )

    from datetime import datetime
    from uuid import uuid4

    return {
        "id": base.get("id") or uuid4().hex[:12],
        "nombre": str(payload.get("nombre", base.get("nombre") or "")).strip() or f"{objetivo} {pct * 100:g}%",
        "tipo": tipo,
        "objetivo": objetivo,
        "pct": pct,
        "desde": desde,
        "hasta": hasta,
        "activa": bool(payload.get("activa", base.get("activa", True))),
        # El ámbito lo pone la ruta por la que entró (global o de una sucursal),
        # no el cliente: si viniera en el cuerpo, una petición a la sucursal
        # podría crear una regla que afectara a todas las demás.
        "ambito": base.get("ambito") or ambito,
        # `creada` decide quién gana un solape, así que se pone en el servidor y
        # no se acepta del cliente: si viniera de fuera, cualquiera podría colar
        # una regla "más nueva" con una fecha inventada.
        "creada": base.get("creada") or datetime.now().isoformat(timespec="seconds"),
    }
