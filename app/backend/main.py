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

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from services.auth_store import auth_store
from services.clientes_analisis import compute_clientes_analisis
from services.diario import compute_diario
from services.metas_gestor import compute_metas_gestor
from services.excel_export import (
    export_all, export_clientes_analisis, export_market, export_parranda_facturas,
    export_productos, export_ranking, export_ventas,
)
from services.loader import ReportData, STD_COLS, available_periods, filter_by_period, load_report
from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.market import compute_market
from services.productos import compute_productos
from services.ranking import compute_ranking
from services.repository import OverlapError, repository
from services.sucursal_store import config_for_period, config_for_report, sucursal_store
from services.vendedores import compute_vendedores
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
    """Configurar metas o subir reportes: admin (todas) o supervisor (su sucursal)."""
    _get_sucursal_or_404(sid)
    if not auth_store.can_write_metas(user, sid):
        raise HTTPException(status_code=403, detail="Sin permiso para configurar esta sucursal")
    return user


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
@app.get("/api/users")
def list_users(_: dict = Depends(require_admin)) -> dict:
    return {"items": auth_store.list()}


@app.post("/api/users")
def create_user(payload: dict, _: dict = Depends(require_admin)) -> dict:
    try:
        return auth_store.create(
            payload["username"], payload.get("password", ""), payload.get("role", "user"),
            payload.get("sucursales", []), payload.get("nombre", ""), payload.get("gestor"))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/users/{username}")
def update_user(username: str, payload: dict, _: dict = Depends(require_admin)) -> dict:
    u = auth_store.update(username, payload)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return u


@app.delete("/api/users/{username}")
def delete_user(username: str, _: dict = Depends(require_admin)) -> dict:
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
def add_gestor(sid: str, payload: dict, suc: dict = Depends(require_access), _m: dict = Depends(require_manage)) -> dict:
    clave = (payload.get("clave") or payload.get("nombre") or "").strip()
    if not clave:
        raise HTTPException(status_code=400, detail="Clave o nombre requerido")
    return sucursal_store.upsert_gestor(sid, clave, payload)


@app.put("/api/sucursales/{sid}/gestores/{clave}")
def edit_gestor(sid: str, clave: str, payload: dict, suc: dict = Depends(require_access), _m: dict = Depends(require_manage)) -> dict:
    if payload.get("nueva_clave") and payload["nueva_clave"].strip().upper() != clave.upper():
        sucursal_store.rename_gestor(sid, clave, payload["nueva_clave"])
        clave = payload["nueva_clave"]
    return sucursal_store.upsert_gestor(sid, clave, payload)


@app.delete("/api/sucursales/{sid}/gestores/{clave}")
def remove_gestor(sid: str, clave: str, suc: dict = Depends(require_access), _m: dict = Depends(require_manage)) -> dict:
    sucursal_store.delete_gestor(sid, clave)
    return {"ok": True}


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
    return JSONResponse(content={"id": stored.id, "filename": stored.filename,
                                 "uploaded_at": stored.uploaded_at, "rango": stored.rango, "filas": stored.filas})


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
    return compute_ranking(report, _eff_scoped(suc, report, mes, user))


@app.get("/api/sucursales/{sid}/sources/{source_id}/clientes-analisis")
def src_clientes_analisis(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    report = filter_by_period(_get_source(sid, source_id), mes)
    return compute_clientes_analisis(report, _eff_scoped(suc, report, mes, user))


@app.get("/api/sucursales/{sid}/sources/{source_id}/vendedores")
def src_vendedores(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    report = filter_by_period(_get_source(sid, source_id), mes)
    return compute_vendedores(report, _eff_scoped(suc, report, mes, user))


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


@app.get("/api/sucursales/{sid}/sources/{source_id}/dashboard")
def src_dashboard(sid: str, source_id: str, mes: str | None = Query(default=None), suc: dict = Depends(require_access), user: dict = Depends(current_user)) -> dict:
    report = repository.accumulated(sid) if source_id == "accumulated" else repository.get(sid, source_id)
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


# --------------------------------------------------------------- exports
_EXPORTERS = {
    "ventas": export_ventas, "productos": export_productos, "market": export_market,
    "ranking": export_ranking, "clientes-analisis": export_clientes_analisis, "all": export_all,
    # Parranda/Malta por FACTURA (reproduce el script automatizar_parranda.py).
    "parranda-facturas": export_parranda_facturas,
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
