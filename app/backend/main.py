"""API REST: multi-sucursal, con login por roles y configuración dinámica.

Estructura de rutas:
  POST   /api/auth/login                          -> {token, user}
  GET    /api/auth/me
  GET/POST/PUT/DELETE /api/users                  -> gestión de usuarios (admin)
  GET/POST /api/sucursales                        -> lista / crear (admin)
  GET/PUT/DELETE /api/sucursales/{sid}            -> config completa / editar / borrar
  POST   /api/sucursales/{sid}/reset
  POST/PUT/DELETE /api/sucursales/{sid}/gestores  -> CRUD de gestores
  POST/GET/DELETE /api/sucursales/{sid}/uploads   -> reportes crudos (aislados)
  GET    /api/sucursales/{sid}/sources/{src}/...  -> dashboard/ventas/productos/...
  GET    /api/sucursales/{sid}/sources/{src}/export/{m}.xlsx

`{src}` = UUID de un archivo subido o "accumulated" (histórico de la sucursal).
"""
from __future__ import annotations

import logging
import threading

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from services.auth_store import auth_store, ALL_SUCURSALES
from services import cache
from services import ajustes
from services import comisiones
from services.clientes_analisis import compute_clientes_analisis
from services.diario import compute_diario
from services.metas_gestor import compute_metas_gestor
from services.excel_export import (
    export_all, export_clientes_analisis, export_gestor_sku, export_market,
    export_parranda_facturas, export_productos, export_ranking, export_ventas,
)
from services.loader import ReportData, STD_COLS, available_periods, filter_by_period, load_report
from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.market import compute_market
from services.productos import compute_productos
from services.ranking import compute_ranking
from services.repository import OverlapError, repository
from services.sucursal_store import config_for_period, config_for_report, sucursal_store
from services.vendedores import compute_vendedores
from services.gestor_sku import compute_gestor_sku
from services.ventas import compute_ventas

logger = logging.getLogger(__name__)

app = FastAPI(title="Sucursal Analytics API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --------------------------------------------------------------- auth deps
def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="No autenticado")
    user = auth_store.verify_token(authorization.split(" ", 1)[1].strip())
    if user is None:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol de administrador")
    return user


def _get_sucursal_or_404(sid: str) -> dict:
    suc = sucursal_store.get(sid)
    if suc is None:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    return suc


def require_access(sid: str, user: dict = Depends(current_user)) -> dict:
    suc = _get_sucursal_or_404(sid)
    if not auth_store.can_access(user, sid):
        raise HTTPException(status_code=403, detail="Sin acceso a esta sucursal")
    return suc


def _xlsx(data: bytes, filename: str) -> Response:
    return Response(content=data, media_type=XLSX_MIME,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _get_source(sid: str, source_id: str) -> ReportData:
    report = repository.accumulated(sid) if source_id == "accumulated" else repository.get(sid, source_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Fuente no encontrada. Sube un archivo.")
    return report


def _eff(suc: dict, report: ReportData | None, mes: str | None) -> dict:
    if mes:
        try:
            return config_for_period(suc, int(mes[:4]), int(mes[5:7]))
        except (ValueError, IndexError):
            pass
    return config_for_report(suc, report)


# --------------------------------------------------------------- permisos por rol
def require_manage(user: dict = Depends(current_user)) -> dict:
    """Config estructural / usuarios / sucursales: solo admin."""
    if not auth_store.can_manage(user):
        raise HTTPException(status_code=403, detail="Solo el administrador puede hacer esto")
    return user


def require_metas_write(sid: str, user: dict = Depends(current_user)) -> dict:
    """Configurar metas / gestores / subir reportes: admin (todas) o supervisor (su sucursal)."""
    _get_sucursal_or_404(sid)
    if not auth_store.can_write_metas(user, sid):
        raise HTTPException(status_code=403, detail="Sin permiso para configurar esta sucursal")
    return user


# Roles que un supervisor puede asignar/gestionar (nunca admin/analitico).
_SUPERVISOR_ROLES = ("supervisor", "gestor")


def _supervisor_sucs(user: dict) -> set:
    """Sucursales concretas del supervisor (sin el comodín '*')."""
    return {s for s in (user.get("sucursales") or []) if s != ALL_SUCURSALES}


def require_manage_users(user: dict = Depends(current_user)) -> dict:
    """Gestión de usuarios: admin (todos) o supervisor. El supervisor solo puede tocar
    usuarios de SU sucursal y con rol supervisor/gestor (se aplica en cada endpoint)."""
    if user.get("role") in ("admin", "supervisor"):
        return user
    raise HTTPException(status_code=403, detail="Sin permiso para gestionar usuarios")


def _scope_for_user(eff: dict, user: dict) -> dict:
    """El rol 'gestor' solo ve SUS datos: restringe los gestores efectivos al suyo."""
    if user.get("role") == "gestor" and user.get("gestor"):
        g = str(user["gestor"]).upper()
        eff = dict(eff)
        eff["gestores"] = {k: v for k, v in (eff.get("gestores") or {}).items() if str(k).upper() == g}
    return eff


def _eff_scoped(suc: dict, report, mes: str | None, user: dict) -> dict:
    return _scope_for_user(_eff(suc, report, mes), user)


# --------------------------------------------------------------- health
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------- auth
@app.post("/api/auth/login")
def login(payload: dict) -> dict:
    u = auth_store.authenticate(payload.get("username", ""), payload.get("password", ""))
    if u is None:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {"token": auth_store.make_token(u["username"]), "user": auth_store._public(u)}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return auth_store._public(user)


# --------------------------------------------------------------- usuarios (admin)
def _puede_tocar(actor: dict, target: dict | None) -> bool:
    """Un supervisor solo puede tocar usuarios supervisor/gestor de SU(s) sucursal(es)."""
    if not target:
        return False
    allowed = _supervisor_sucs(actor)
    return target.get("role") in _SUPERVISOR_ROLES and bool(set(target.get("sucursales") or []) & allowed)


@app.get("/api/users")
def list_users(user: dict = Depends(require_manage_users)) -> dict:
    items = auth_store.list()
    if user.get("role") == "supervisor":
        allowed = _supervisor_sucs(user)
        items = [u for u in items
                 if u.get("role") in _SUPERVISOR_ROLES and (set(u.get("sucursales") or []) & allowed)]
    return {"items": items}


@app.post("/api/users")
def create_user(payload: dict, user: dict = Depends(require_manage_users)) -> dict:
    sucursales = payload.get("sucursales", [])
    if user.get("role") == "supervisor":
        if payload.get("role") not in _SUPERVISOR_ROLES:
            raise HTTPException(status_code=403, detail="Un supervisor solo puede crear supervisores o gestores")
        allowed = _supervisor_sucs(user)
        sucursales = [s for s in (sucursales or list(allowed)) if s in allowed]
        if not sucursales:
            raise HTTPException(status_code=403, detail="Asigná al menos una de tus sucursales")
    try:
        return auth_store.create(
            payload["username"], payload.get("password", ""), payload.get("role", "usuario"),
            sucursales, payload.get("nombre", ""), payload.get("gestor"))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/users/{username}")
def update_user(username: str, payload: dict, user: dict = Depends(require_manage_users)) -> dict:
    if user.get("role") == "supervisor":
        if not _puede_tocar(user, auth_store.get_raw(username)):
            raise HTTPException(status_code=403, detail="No podés editar este usuario")
        if "role" in payload and payload["role"] not in _SUPERVISOR_ROLES:
            raise HTTPException(status_code=403, detail="Rol no permitido para un supervisor")
        if "sucursales" in payload:
            allowed = _supervisor_sucs(user)
            payload["sucursales"] = [s for s in (payload["sucursales"] or []) if s in allowed]
    u = auth_store.update(username, payload)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return u


@app.delete("/api/users/{username}")
def delete_user(username: str, user: dict = Depends(require_manage_users)) -> dict:
    if user.get("role") == "supervisor" and not _puede_tocar(user, auth_store.get_raw(username)):
        raise HTTPException(status_code=403, detail="No podés eliminar este usuario")
    if not auth_store.delete(username):
        raise HTTPException(status_code=400, detail="No se puede eliminar (no existe o es el último admin)")
    return {"ok": True}


# --------------------------------------------------------------- sucursales
@app.get("/api/sucursales")
def list_sucursales(user: dict = Depends(current_user)) -> dict:
    allowed = auth_store.allowed_sucursales(user, [s["id"] for s in sucursal_store.list_summary()])
    return {"items": [s for s in sucursal_store.list_summary() if s["id"] in allowed]}


@app.post("/api/sucursales")
def create_sucursal(payload: dict, _: dict = Depends(require_admin)) -> dict:
    nombre = (payload.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre requerido")
    return sucursal_store.create(nombre, seed_gestores=bool(payload.get("seed_gestores", False)))


@app.get("/api/sucursales/{sid}")
def get_sucursal(suc: dict = Depends(require_access)) -> dict:
    return suc


@app.put("/api/sucursales/{sid}")
def update_sucursal(sid: str, payload: dict, suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    metas_only = set(payload.keys()) <= {"metas", "metas_mensuales"}
    if auth_store.can_manage(user):
        pass  # admin: cualquier cambio
    elif user.get("role") == "supervisor" and metas_only and auth_store.can_access(user, sid):
        pass  # supervisor: solo metas de su sucursal
    else:
        raise HTTPException(status_code=403, detail="Sin permiso para editar esta sucursal")
    return sucursal_store.update(sid, payload)


@app.delete("/api/sucursales/{sid}")
def delete_sucursal(sid: str, _: dict = Depends(require_admin)) -> dict:
    if not sucursal_store.delete(sid):
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    repository.reset(sid)
    return {"ok": True}


@app.post("/api/sucursales/{sid}/reset")
def reset_sucursal(sid: str, suc: dict = Depends(require_access), _m: dict = Depends(require_manage)) -> dict:
    return sucursal_store.reset(sid)


# --------------------------------------------------------------- gestores (CRUD)
@app.post("/api/sucursales/{sid}/gestores")
def add_gestor(sid: str, payload: dict, suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> dict:
    clave = (payload.get("clave") or payload.get("nombre") or "").strip()
    if not clave:
        raise HTTPException(status_code=400, detail="Clave o nombre requerido")
    return sucursal_store.upsert_gestor(sid, clave, payload)


@app.put("/api/sucursales/{sid}/gestores/{clave}")
def edit_gestor(sid: str, clave: str, payload: dict, suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> dict:
    if payload.get("nueva_clave") and payload["nueva_clave"].strip().upper() != clave.upper():
        sucursal_store.rename_gestor(sid, clave, payload["nueva_clave"])
        clave = payload["nueva_clave"]
    return sucursal_store.upsert_gestor(sid, clave, payload)


@app.delete("/api/sucursales/{sid}/gestores/{clave}")
def remove_gestor(sid: str, clave: str, suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> dict:
    sucursal_store.delete_gestor(sid, clave)
    return {"ok": True}


# ----------------------------------------------------- reglas de comisión (CRUD)
#
# La validación de verdad está en services/comisiones.py y estas rutas solo la
# traducen a HTTP. Se hace así a propósito: son reglas que deciden lo que cobra
# gente, y tienen que poder probarse sin levantar el servidor.

def _ordenar(reglas: list) -> list:
    return sorted(reglas, key=lambda r: (str(r.get("desde") or ""), str(r.get("creada") or "")), reverse=True)


def _respuesta_comisiones(sid: str, extra: dict | None = None) -> dict:
    propias = [{**r, "ambito": comisiones.AMBITO_SUCURSAL} for r in sucursal_store.reglas_comision(sid)]
    globales = [{**r, "ambito": comisiones.AMBITO_GLOBAL} for r in ajustes.reglas_comision_globales()]
    # Las globales viajan aparte y en solo lectura: aquí se ven para saber con
    # qué se está compitiendo, pero se editan en su propia pantalla. Mezclarlas
    # en la misma lista llevaría a borrar desde una sucursal algo que afecta a
    # las siete.
    reglas = globales + propias
    suc = sucursal_store.get(sid) or {}
    params = (suc.get("parametros") or {})
    return {
        "items": _ordenar(propias),
        "globales": _ordenar(globales),
        "ambito": comisiones.AMBITO_SUCURSAL,
        # Los avisos van SIEMPRE, no solo al crear: si dos reglas se pisan, hay
        # que verlo cada vez que se abre la pantalla y no solo el día que se creó
        # la segunda.
        "avisos": comisiones.solapes(reglas),
        "comision_general_pct": float(params.get("comision_gestor_pct", 0.01) or 0.0),
        "mes_actual": comisiones.mes_actual(),
        **(extra or {}),
    }


@app.get("/api/sucursales/{sid}/comisiones")
def list_comisiones(sid: str, suc: dict = Depends(require_access)) -> dict:
    return _respuesta_comisiones(sid)


@app.post("/api/sucursales/{sid}/comisiones")
def add_comision(sid: str, payload: dict, suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> dict:
    try:
        regla = comisiones.normalizar_regla(payload, ambito=comisiones.AMBITO_SUCURSAL)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sucursal_store.guardar_reglas_comision(sid, sucursal_store.reglas_comision(sid) + [regla])
    return _respuesta_comisiones(sid, {"item": regla})


@app.put("/api/sucursales/{sid}/comisiones/{rid}")
def edit_comision(sid: str, rid: str, payload: dict, suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> dict:
    reglas = sucursal_store.reglas_comision(sid)
    actual = next((r for r in reglas if str(r.get("id")) == rid), None)
    if actual is None:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    try:
        nueva = comisiones.normalizar_regla(payload, existente=actual, ambito=comisiones.AMBITO_SUCURSAL)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sucursal_store.guardar_reglas_comision(sid, [nueva if str(r.get("id")) == rid else r for r in reglas])
    return _respuesta_comisiones(sid, {"item": nueva})


@app.delete("/api/sucursales/{sid}/comisiones/{rid}")
def remove_comision(sid: str, rid: str, suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> dict:
    reglas = sucursal_store.reglas_comision(sid)
    quedan = [r for r in reglas if str(r.get("id")) != rid]
    if len(quedan) == len(reglas):
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    # Se BORRA de verdad, no se marca de baja. Para "dejó de usarse en tal mes"
    # está `hasta`, que conserva el histórico y no toca lo ya calculado. Borrar
    # es para la regla que se creó por error y nunca debió existir.
    sucursal_store.guardar_reglas_comision(sid, quedan)
    return _respuesta_comisiones(sid, {"ok": True})


# ------------------------------------------------ reglas de comisión GLOBALES
#
# Valen para TODAS las sucursales. Solo las toca un admin: una regla de aquí
# cambia lo que cobra todo el mundo, y un supervisor solo manda en lo suyo.

def _respuesta_globales(extra: dict | None = None) -> dict:
    reglas = [{**r, "ambito": comisiones.AMBITO_GLOBAL} for r in ajustes.reglas_comision_globales()]
    return {
        "items": _ordenar(reglas),
        "ambito": comisiones.AMBITO_GLOBAL,
        "avisos": comisiones.solapes(reglas),
        "mes_actual": comisiones.mes_actual(),
        **(extra or {}),
    }


@app.get("/api/comisiones")
def list_comisiones_globales(_: dict = Depends(current_user)) -> dict:
    return _respuesta_globales()


@app.post("/api/comisiones")
def add_comision_global(payload: dict, _: dict = Depends(require_admin)) -> dict:
    try:
        regla = comisiones.normalizar_regla(payload, ambito=comisiones.AMBITO_GLOBAL)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ajustes.guardar_reglas_comision_globales(ajustes.reglas_comision_globales() + [regla])
    return _respuesta_globales({"item": regla})


@app.put("/api/comisiones/{rid}")
def edit_comision_global(rid: str, payload: dict, _: dict = Depends(require_admin)) -> dict:
    reglas = ajustes.reglas_comision_globales()
    actual = next((r for r in reglas if str(r.get("id")) == rid), None)
    if actual is None:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    try:
        nueva = comisiones.normalizar_regla(payload, existente=actual, ambito=comisiones.AMBITO_GLOBAL)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ajustes.guardar_reglas_comision_globales([nueva if str(r.get("id")) == rid else r for r in reglas])
    return _respuesta_globales({"item": nueva})


@app.delete("/api/comisiones/{rid}")
def remove_comision_global(rid: str, _: dict = Depends(require_admin)) -> dict:
    reglas = ajustes.reglas_comision_globales()
    quedan = [r for r in reglas if str(r.get("id")) != rid]
    if len(quedan) == len(reglas):
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    ajustes.guardar_reglas_comision_globales(quedan)
    return _respuesta_globales({"ok": True})


# --------------------------------------------------------------- uploads
@app.post("/api/sucursales/{sid}/uploads")
async def upload_file(sid: str, file: UploadFile = File(...), force: bool = Form(False),
                      suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> JSONResponse:
    if not file.filename or not file.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .xls o .xlsx")
    content = await file.read()
    try:
        report = load_report(content, file.filename)
    except Exception as e:
        logger.exception("Error leyendo archivo")
        raise HTTPException(status_code=422, detail=f"No se pudo procesar el archivo: {e}") from e
    if report.df.empty:
        raise HTTPException(status_code=422, detail="El archivo no contiene filas válidas.")
    try:
        stored = repository.add(sid, report, force=bool(force))
    except OverlapError as e:
        return JSONResponse(status_code=409, content={
            "detail": str(e), "conflicts": e.conflicts,
            "preview": {"filename": report.filename, "rango": report.rango_str, "filas": int(len(report.df))}})
    except Exception as e:
        logger.exception("Error guardando upload")
        raise HTTPException(status_code=500, detail=f"Error guardando el archivo: {e}") from e

    # Subir un archivo deja obsoletos todos los resultados de esa sucursal, y
    # el siguiente que abra el Resumen pagaría los segundos del recálculo. Se
    # hace aquí, en segundo plano: quien sube ya está esperando, y quien mire
    # después lo encuentra listo. De paso se limpia lo que ya no sirve.
    threading.Thread(target=_tras_subida, args=(suc,), daemon=True).start()

    return JSONResponse(content={"id": stored.id, "filename": stored.filename,
                                 "uploaded_at": stored.uploaded_at, "rango": stored.rango, "filas": stored.filas})


def _tras_subida(suc: dict) -> None:
    """Recalcula el Resumen de la sucursal y purga lo viejo. En segundo plano:
    si algo falla aquí NO debe romper la subida, que ya se guardó bien."""
    sid = suc["id"]
    try:
        version = cache.sucursal_version(sid)
        if version:
            n = cache.purgar_obsoletos_de(sid, version)
            if n:
                logger.info("cache: %s resultados obsoletos de %s borrados", n, sid)

        # Se precalcula con el alcance de admin ("todos"), que es el que ven
        # los roles admin, supervisor y analitico. El del rol gestor se calcula
        # solo cuando ese gestor entre: son pocos y no compensa adelantarlos.
        admin = {"role": "admin", "username": "(precalculo)", "sucursales": [], "gestores": []}
        _compute_dashboard(suc, "accumulated", None, admin)
        logger.info("cache: Resumen de %s precalculado tras la subida", sid)

        borrados = cache.purgar()
        if any(borrados.values()):
            logger.info("cache: purga -> %s", borrados)
    except Exception:
        logger.exception("cache: fallo el precalculo tras subir a %s", sid)


@app.get("/api/cache")
def cache_stats(_: dict = Depends(require_admin)) -> dict:
    """Cuántos resultados hay guardados, cuánto ocupan y desde cuándo."""
    return cache.stats()


@app.post("/api/cache/purgar")
def cache_purgar(dias: int | None = Query(default=None),
                 _: dict = Depends(require_admin)) -> dict:
    """Purga manual. Sin parámetro usa la retención configurada.
    Lo purgado se vuelve a calcular solo si alguien lo pide."""
    antes = cache.stats()
    borrados = cache.purgar(dias if dias is not None else cache.DIAS_RETENCION)
    return {"borrados": borrados, "antes": antes, "despues": cache.stats()}


@app.get("/api/sucursales/{sid}/uploads")
def list_uploads(sid: str, suc: dict = Depends(require_access)) -> dict:
    return {"items": [u.__dict__ for u in repository.list(sid)]}


@app.delete("/api/sucursales/{sid}/uploads/{upload_id}")
def delete_upload(sid: str, upload_id: str, suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> dict:
    if not repository.delete(sid, upload_id):
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return {"ok": True}


@app.delete("/api/sucursales/{sid}/uploads")
def delete_all_uploads(sid: str, suc: dict = Depends(require_access), _w: dict = Depends(require_metas_write)) -> dict:
    repository.reset(sid)
    return {"ok": True}


# --------------------------------------------------------------- consultas
@app.get("/api/sucursales/{sid}/sources/{source_id}/periods")
def src_periods(sid: str, source_id: str, suc: dict = Depends(require_access)) -> dict:
    return {"periods": available_periods(_get_source(sid, source_id))}


@app.get("/api/sucursales/{sid}/sources/{source_id}/ventas")
def src_ventas(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    report = filter_by_period(_get_source(sid, source_id), mes)
    return compute_ventas(report, _eff_scoped(suc, report, mes, user))


@app.get("/api/sucursales/{sid}/sources/{source_id}/productos")
def src_productos(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    report = filter_by_period(_get_source(sid, source_id), mes)
    return compute_productos(report, _eff_scoped(suc, report, mes, user))


@app.get("/api/sucursales/{sid}/sources/{source_id}/market")
def src_market(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    report = filter_by_period(_get_source(sid, source_id), mes)
    return compute_market(report, _eff_scoped(suc, report, mes, user))


@app.get("/api/sucursales/{sid}/sources/{source_id}/ranking")
def src_ranking(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    report = filter_by_period(_get_source(sid, source_id), mes)
    # OJO: aquí NO se aplica _scope_for_user a propósito. El ranking es COMPARATIVO:
    # un usuario 'gestor' debe ver a TODOS sus compañeros para saber en qué puesto va
    # (si se recorta a lo suyo, siempre sale 1º y el ranking no le dice nada).
    # El resto de vistas sí siguen recortadas para el rol 'gestor'.
    return compute_ranking(report, _eff(suc, report, mes))


@app.get("/api/sucursales/{sid}/sources/{source_id}/clientes-analisis")
def src_clientes_analisis(
    sid: str,
    source_id: str,
    mes: str | None = Query(default=None),
    # Grupos comerciales a incluir. Repetible: ?grupo=PARRANDA&grupo=IMPORTACIONES.
    # Sin ninguno = todos, que es como estaba.
    grupo: list[str] = Query(default=[]),
    # "importe" (dolares) o "cantidad" (por empaque, como viene del origen).
    metrica: str = Query(default="importe"),
    suc: dict = Depends(require_access),
    user: dict = Depends(current_user),
) -> dict:
    report = filter_by_period(_get_source(sid, source_id), mes)
    return compute_clientes_analisis(
        report, _eff_scoped(suc, report, mes, user), grupos=grupo, metrica=metrica
    )


@app.get("/api/sucursales/{sid}/sources/{source_id}/vendedores")
def src_vendedores(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    report = filter_by_period(_get_source(sid, source_id), mes)
    return compute_vendedores(report, _eff_scoped(suc, report, mes, user))


@app.get("/api/sucursales/{sid}/sources/{source_id}/gestor-sku")
def src_gestor_sku(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    """Informe cruzado gestor x producto por importe, con totales en ambas direcciones."""
    report = filter_by_period(_get_source(sid, source_id), mes)
    return compute_gestor_sku(report, _eff_scoped(suc, report, mes, user))


@app.get("/api/sucursales/{sid}/sources/{source_id}/diario")
def src_diario(sid: str, source_id: str, mes: str | None = Query(default=None), gestor: str | None = Query(default=None),
               suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    # Reporte COMPLETO (sin filtrar por periodo) para poder comparar el día 1 con el
    # último día del mes anterior. El mes objetivo se pasa aparte.
    report = _get_source(sid, source_id)
    target = mes
    if not target and report is not None and getattr(report, "date_max", None) is not None:
        d = report.date_max
        target = f"{d.year}-{d.month:02d}"
    if target:
        y, m = int(target[:4]), int(target[5:7])
        eff = _scope_for_user(config_for_period(suc, y, m), user)
    else:
        eff = _eff_scoped(suc, report, mes, user)
    return compute_diario(report, eff, mes=target, gestor=gestor)


@app.get("/api/sucursales/{sid}/sources/{source_id}/metas-gestor")
def src_metas_gestor(sid: str, source_id: str, mes: str | None = Query(default=None), dia: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    # `dia` = día de corte elegido (para mirar atrás). Sin él, el último con datos.
    report = filter_by_period(_get_source(sid, source_id), mes)
    # El estudio es del último día subido: se usa la meta de SU mes (no la suma multi-mes).
    if report is not None and getattr(report, "date_max", None) is not None:
        d = report.date_max
        eff = _scope_for_user(config_for_period(suc, d.year, d.month), user)
    else:
        eff = _eff_scoped(suc, report, mes, user)
    return compute_metas_gestor(report, eff, dia)


# Desglose GENERAL (todos los vendedores) por formato de cerveza Parranda y Malta Guajira.
# HL total de cada SKU/tamaño, no por vendedor. Para el Resumen del dashboard.
_FORMATOS_DESGLOSE = [
    ("Parranda", "IsParranda", "1500", "1.5 L"),
    ("Parranda", "IsParranda", "500", "500 ml"),
    ("Parranda", "IsParranda", "330", "330 ml"),
    ("Malta", "IsMalta", "1500", "1.5 L"),
    ("Malta", "IsMalta", "500", "500 ml"),
    ("Malta", "IsMalta", "330", "330 ml"),
]


def _desglose_formato_general(report, eff) -> list[dict]:
    dfx = only_valid(enrich_for_sucursal(report, eff), gestor_keys(eff))
    size_col = STD_COLS["size"]
    out: list[dict] = []
    for prod, flag, size, label in _FORMATOS_DESGLOSE:
        hl = 0.0
        if not dfx.empty and "Hectolitros" in dfx.columns and flag in dfx.columns and size_col in dfx.columns:
            mask = dfx[flag].fillna(False) & (dfx[size_col] == size)
            hl = round(float(dfx.loc[mask, "Hectolitros"].sum()), 2)
        out.append({"producto": prod, "tamano": label, "formato": f"{prod} {label}", "hectolitros": hl})
    return out


def _scope_key(user: dict) -> str:
    """Identifica QUÉ ve este usuario, para no compartir caché entre alcances.
    Solo el rol 'gestor' recorta los datos (ver _scope_for_user); el resto ve lo
    mismo, así que comparten entrada."""
    if user.get("role") == "gestor" and user.get("gestor"):
        return f"gestor:{str(user['gestor']).upper()}"
    return "todos"


def _compute_dashboard(suc: dict, source_id: str, mes: str | None, user: dict) -> dict:
    """Payload del Resumen para UNA sucursal, cacheado.

    Se invalida solo cuando cambia la sucursal (archivo nuevo/borrado o config
    editada). Sin esto, cada carga del Resumen recalculaba todo desde cero."""
    key = ("dashboard", suc["id"], source_id, mes or "", _scope_key(user))
    return cache.get_or_compute(key, suc["id"], lambda: _compute_dashboard_uncached(suc, source_id, mes, user))


def _compute_dashboard_uncached(suc: dict, source_id: str, mes: str | None, user: dict) -> dict:
    """Payload del Resumen para UNA sucursal (fuente = upload uuid o 'accumulated')."""
    report = repository.accumulated(suc["id"]) if source_id == "accumulated" else repository.get(suc["id"], source_id)
    if report is None:
        eff = _scope_for_user(config_for_period(suc, None, None), user)
        return {
            "id": source_id, "filename": "Sin archivos", "rango": "—", "filas": 0, "empty": True,
            "kpis": {"total_hectolitros": 0.0, "meta_hectolitros": eff["meta_hectolitros_total"],
                     "cumplimiento_pct": 0.0, "total_importe": 0.0, "total_clientes": 0,
                     "total_skus": 0, "dias_laborales_transcurridos": 0, "dias_laborales_totales": 0},
            "gestores_ventas": [], "ranking_general": [], "ranking_semanal": [],
            "cumplimiento_productos": [
                {"producto": k, "meta": v, "real": 0.0, "cumplimiento_pct": 0.0, "deberia": 0.0,
                 "delta": -v, "necesario_por_dia": 0.0, "estado": "critico"}
                for k, v in eff["metas_productos_ces"].items()],
            "desglose_formato": [
                {"producto": p, "tamano": lbl, "formato": f"{p} {lbl}", "hectolitros": 0.0}
                for p, _f, _s, lbl in _FORMATOS_DESGLOSE],
        }
    report = filter_by_period(report, mes)
    eff = _eff_scoped(suc, report, mes, user)
    ventas = compute_ventas(report, eff)
    productos = compute_productos(report, eff)
    ranking = compute_ranking(report, eff)
    clientes = compute_clientes_analisis(report, eff)
    return {
        "id": source_id, "filename": report.filename, "rango": report.rango_str, "filas": int(len(report.df)),
        "kpis": {
            "total_hectolitros": ventas["total_hectolitros"], "meta_hectolitros": ventas["meta_hectolitros"],
            "cumplimiento_pct": ventas["cumplimiento_pct"], "total_importe": ventas["total_importe"],
            "total_clientes": clientes["oficina"]["num_clientes"], "total_skus": clientes["oficina"]["num_skus"],
            "dias_laborales_transcurridos": productos["dias_laborales_transcurridos"],
            "dias_laborales_totales": productos["dias_laborales_totales"]},
        "gestores_ventas": ventas["gestores"], "ranking_general": ranking["general"],
        "ranking_semanal": ranking["semanal"], "cumplimiento_productos": productos["cumplimiento"],
        # Desglose GENERAL por formato (HL, no dinero): cada SKU de Parranda y Malta.
        "desglose_formato": _desglose_formato_general(report, eff),
    }


@app.get("/api/sucursales/{sid}/sources/{source_id}/dashboard")
def src_dashboard(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    return _compute_dashboard(suc, source_id, mes, user)


def _aggregate_dashboards(items: list[dict]) -> dict:
    """Combina los payloads de Resumen de varias sucursales en UNO solo.
    - KPIs se SUMAN; % cumplimiento se recalcula = suma(HL) / suma(meta).
    - Gestores y vendedores se fusionan por NOMBRE (sumando).
    - Desglose por formato y cumplimiento por producto se suman por clave.
    Cada item ya viene calculado con la config propia de su sucursal, así que
    no hay cruce de gestores entre sucursales.
    """
    k = {"total_hectolitros": 0.0, "meta_hectolitros": 0.0, "total_importe": 0.0,
         "total_clientes": 0, "total_skus": 0,
         "dias_laborales_transcurridos": 0, "dias_laborales_totales": 0}
    for it in items:
        kp = it.get("kpis") or {}
        k["total_hectolitros"] += kp.get("total_hectolitros") or 0
        k["meta_hectolitros"] += kp.get("meta_hectolitros") or 0
        k["total_importe"] += kp.get("total_importe") or 0
        k["total_clientes"] += kp.get("total_clientes") or 0
        k["total_skus"] += kp.get("total_skus") or 0
        k["dias_laborales_transcurridos"] = max(k["dias_laborales_transcurridos"], kp.get("dias_laborales_transcurridos") or 0)
        k["dias_laborales_totales"] = max(k["dias_laborales_totales"], kp.get("dias_laborales_totales") or 0)
    k["total_hectolitros"] = round(k["total_hectolitros"], 2)
    k["meta_hectolitros"] = round(k["meta_hectolitros"], 2)
    k["total_importe"] = round(k["total_importe"], 2)
    k["cumplimiento_pct"] = round(k["total_hectolitros"] / k["meta_hectolitros"] * 100, 1) if k["meta_hectolitros"] else 0.0

    gest: dict[str, dict] = {}
    for it in items:
        for g in it.get("gestores_ventas") or []:
            e = gest.setdefault(str(g.get("gestor", "")).upper(), {"gestor": g.get("gestor", ""), "total_hectolitros": 0.0})
            e["total_hectolitros"] += g.get("total_hectolitros") or 0
    gestores = sorted(({"gestor": e["gestor"], "total_hectolitros": round(e["total_hectolitros"], 2)} for e in gest.values()),
                      key=lambda x: -x["total_hectolitros"])

    rk: dict[str, dict] = {}
    for it in items:
        for r in it.get("ranking_general") or []:
            e = rk.setdefault(str(r.get("vendedor", "")).upper(), {"vendedor": r.get("vendedor", ""), "ventas": 0.0})
            e["ventas"] += r.get("ventas") or 0
    ranking = sorted(({"vendedor": e["vendedor"], "ventas": round(e["ventas"], 2)} for e in rk.values()),
                     key=lambda x: -x["ventas"])
    tot_v = sum(r["ventas"] for r in ranking)
    for i, r in enumerate(ranking, 1):
        r["posicion"] = i
        r["participacion_pct"] = round(r["ventas"] / tot_v * 100, 1) if tot_v else 0.0

    dg: dict[tuple, dict] = {}
    dg_order: list[tuple] = []
    for it in items:
        for d in it.get("desglose_formato") or []:
            key = (d.get("producto"), d.get("formato"))
            if key not in dg:
                dg[key] = {"producto": d.get("producto"), "tamano": d.get("tamano"), "formato": d.get("formato"), "hectolitros": 0.0}
                dg_order.append(key)
            dg[key]["hectolitros"] += d.get("hectolitros") or 0
    desglose = [{**dg[key], "hectolitros": round(dg[key]["hectolitros"], 2)} for key in dg_order]

    cp: dict[str, dict] = {}
    cp_order: list[str] = []
    for it in items:
        for p in it.get("cumplimiento_productos") or []:
            key = p.get("producto")
            if key not in cp:
                cp[key] = {"producto": key, "grupo": p.get("grupo"), "meta": 0.0, "real": 0.0, "deberia": 0.0, "necesario_por_dia": 0.0}
                cp_order.append(key)
            e = cp[key]
            if not e.get("grupo"):
                e["grupo"] = p.get("grupo")
            e["meta"] += p.get("meta") or 0
            e["real"] += p.get("real") or 0
            e["deberia"] += p.get("deberia") or 0
            e["necesario_por_dia"] += p.get("necesario_por_dia") or 0
    cumplimiento = []
    for key in cp_order:
        e = cp[key]
        meta, real, deb = round(e["meta"], 2), round(e["real"], 2), round(e["deberia"], 2)
        pct = round(real / meta * 100, 1) if meta else 0.0
        cumplimiento.append({"producto": key, "grupo": e["grupo"], "meta": meta, "real": real,
                             "cumplimiento_pct": pct, "deberia": deb, "delta": round(real - deb, 2),
                             "necesario_por_dia": round(e["necesario_por_dia"], 2),
                             "estado": "ok" if pct >= 100 else ("alerta" if pct >= 80 else "critico")})

    return {
        "id": "all", "filename": "Todas las sucursales", "rango": "—",
        "filas": sum(int(it.get("filas") or 0) for it in items),
        "sucursales": len(items), "kpis": k,
        "gestores_ventas": gestores, "ranking_general": ranking, "ranking_semanal": [],
        "cumplimiento_productos": cumplimiento, "desglose_formato": desglose,
    }


def _allowed_sucursales_full(user: dict) -> list[dict]:
    ids = auth_store.allowed_sucursales(user, [s["id"] for s in sucursal_store.list_summary()])
    return [s for s in (sucursal_store.get(i) for i in ids) if s is not None]


# Vista COMBINADA de todas las sucursales permitidas (admin/analitico ven todas).
@app.get("/api/all/sources/{source_id}/dashboard")
def all_dashboard(source_id: str, mes: str | None = Query(default=None), user: dict = Depends(current_user)) -> dict:
    sucs = _allowed_sucursales_full(user)
    agg = _aggregate_dashboards([_compute_dashboard(suc, source_id, mes, user) for suc in sucs])
    agg["rango"] = mes or "Todo (acumulado)"
    return agg


@app.get("/api/all/sources/{source_id}/periods")
def all_periods(source_id: str, user: dict = Depends(current_user)) -> dict:
    ps: set[str] = set()
    for suc in _allowed_sucursales_full(user):
        rep = repository.accumulated(suc["id"]) if source_id == "accumulated" else repository.get(suc["id"], source_id)
        if rep is not None:
            ps.update(available_periods(rep))
    return {"periods": sorted(ps)}


# --------------------------------------------------------------- exports
_EXPORTERS = {
    "ventas": export_ventas, "productos": export_productos, "market": export_market,
    "ranking": export_ranking, "clientes-analisis": export_clientes_analisis, "all": export_all,
    # Parranda/Malta por FACTURA (reproduce el script automatizar_parranda.py).
    "parranda-facturas": export_parranda_facturas,
    "gestor-sku": export_gestor_sku,
}


@app.get("/api/sucursales/{sid}/sources/{source_id}/export/{modulo}.xlsx")
def export_module(sid: str, source_id: str, modulo: str, mes: str | None = Query(default=None),
                  suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> Response:
    exporter = _EXPORTERS.get(modulo)
    if exporter is None:
        raise HTTPException(status_code=404, detail="Módulo de exportación desconocido")
    report = filter_by_period(_get_source(sid, source_id), mes)
    suffix = f"_{mes}" if mes else ""
    data = exporter(report, _eff_scoped(suc, report, mes, user))
    return _xlsx(data, f"{modulo}{suffix}.xlsx")
