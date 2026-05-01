"""FastAPI app: API REST para el dashboard web.

Endpoints principales:
  POST   /api/uploads                      -> sube un archivo (.xls/.xlsx)
  GET    /api/uploads                      -> lista los archivos subidos
  DELETE /api/uploads/{id}                 -> elimina un archivo
  DELETE /api/uploads                      -> borra todos
  GET    /api/sources/{id}/...             -> dashboard/ventas/productos/ranking/clientes-punto
  GET    /api/sources/{id}/export/{m}.xlsx -> exportación por módulo
  GET    /api/settings                     -> metas editables
  PUT    /api/settings                     -> guardar metas
  POST   /api/settings/reset               -> restaurar metas por defecto

`{id}` puede ser el UUID de un archivo subido, o la cadena "accumulated"
para consultar el histórico acumulado (todos los archivos juntos).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from services.clientes_punto import compute_clientes_punto
from services.vendedores import compute_vendedores
from services.excel_export import (
    export_all,
    export_clientes_punto,
    export_market,
    export_productos,
    export_ranking,
    export_ventas,
    export_ventas_general,
)
from services.loader import ReportData, available_periods, filter_by_period, load_report
from services.productos import compute_productos
from services.ranking import compute_ranking
from services.repository import OverlapError, repository
from services.settings_store import settings_store
from services.ventas import compute_ventas

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sucursal Analytics API",
    description="API REST para el análisis del Reporte de Venta (por archivo y acumulado).",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _get_source(source_id: str) -> ReportData:
    if source_id == "accumulated":
        report = repository.accumulated()
    else:
        report = repository.get(source_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Fuente no encontrada. Sube un archivo.")
    return report


def _get_source_or_none(source_id: str) -> ReportData | None:
    if source_id == "accumulated":
        return repository.accumulated()
    return repository.get(source_id)


def _xlsx_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------
# Health
# --------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------------
# Uploads CRUD
# --------------------------------------------------------------------
@app.post("/api/uploads")
async def upload_file(
    file: UploadFile = File(...),
    force: bool = Form(False),
) -> JSONResponse:
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
        stored = repository.add(report, force=bool(force))
    except OverlapError as e:
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(e),
                "conflicts": e.conflicts,
                "preview": {
                    "filename": report.filename,
                    "rango": report.rango_str,
                    "filas": int(len(report.df)),
                },
            },
        )
    except Exception as e:
        logger.exception("Error guardando upload")
        raise HTTPException(status_code=500, detail=f"Error guardando el archivo: {e}") from e

    return JSONResponse(content={
        "id": stored.id,
        "filename": stored.filename,
        "uploaded_at": stored.uploaded_at,
        "rango": stored.rango,
        "filas": stored.filas,
    })


@app.get("/api/uploads")
def list_uploads() -> dict:
    return {"items": [u.__dict__ for u in repository.list()]}


@app.delete("/api/uploads/{upload_id}")
def delete_upload(upload_id: str) -> dict:
    ok = repository.delete(upload_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return {"ok": True}


@app.delete("/api/uploads")
def delete_all_uploads() -> dict:
    repository.reset()
    return {"ok": True}


# --------------------------------------------------------------------
# Consultas (por archivo individual o acumulado)
# --------------------------------------------------------------------
@app.get("/api/sources/{source_id}/summary")
def src_summary(source_id: str) -> dict:
    report = _get_source(source_id)
    return {
        "id": source_id,
        "filename": report.filename,
        "rango": report.rango_str,
        "filas": int(len(report.df)),
    }


@app.get("/api/sources/{source_id}/periods")
def src_periods(source_id: str) -> dict:
    report = _get_source(source_id)
    return {"periods": available_periods(report)}


@app.get("/api/sources/{source_id}/ventas")
def src_ventas(source_id: str, mes: str | None = Query(default=None)) -> dict:
    return compute_ventas(filter_by_period(_get_source(source_id), mes), settings_store.load())


@app.get("/api/sources/{source_id}/productos")
def src_productos(source_id: str, mes: str | None = Query(default=None)) -> dict:
    return compute_productos(filter_by_period(_get_source(source_id), mes), settings_store.load())


@app.get("/api/sources/{source_id}/ranking")
def src_ranking(source_id: str, mes: str | None = Query(default=None)) -> dict:
    return compute_ranking(filter_by_period(_get_source(source_id), mes))


@app.get("/api/sources/{source_id}/clientes-punto")
def src_punto(source_id: str, mes: str | None = Query(default=None)) -> dict:
    return compute_clientes_punto(filter_by_period(_get_source(source_id), mes))


@app.get("/api/sources/{source_id}/vendedores")
def src_vendedores(source_id: str, mes: str | None = Query(default=None)) -> dict:
    return compute_vendedores(filter_by_period(_get_source(source_id), mes), settings_store.load())


@app.get("/api/sources/{source_id}/dashboard")
def src_dashboard(source_id: str, mes: str | None = Query(default=None)) -> dict:
    report = _get_source_or_none(source_id)
    cfg = settings_store.load()
    if report is None:
        # Sin archivos aún: devolver shape vacío con metas por defecto
        from services.settings_store import config_for_period
        eff = config_for_period(cfg, None, None)
        return {
            "id": source_id,
            "filename": "Sin archivos",
            "rango": "—",
            "filas": 0,
            "empty": True,
            "kpis": {
                "total_hectolitros": 0.0,
                "meta_hectolitros": eff["meta_hectolitros_total"],
                "cumplimiento_pct": 0.0,
                "total_importe": 0.0,
                "total_clientes_punto": 0,
                "operaciones_punto": 0,
                "dias_laborales_transcurridos": 0,
                "dias_laborales_totales": 0,
            },
            "gestores_ventas": [],
            "ranking_general": [],
            "ranking_semanal": [],
            "cumplimiento_productos": [
                {"producto": k, "meta": v, "real": 0.0, "cumplimiento_pct": 0.0,
                 "deberia": 0.0, "delta": -v, "necesario_por_dia": 0.0, "estado": "critico"}
                for k, v in eff["metas_productos_ces"].items()
            ],
        }
    r = filter_by_period(report, mes)
    ventas = compute_ventas(r, cfg)
    productos = compute_productos(r, cfg)
    ranking = compute_ranking(r)
    punto = compute_clientes_punto(r)
    return {
        "id": source_id,
        "filename": report.filename,
        "rango": report.rango_str,
        "filas": int(len(report.df)),
        "kpis": {
            "total_hectolitros": ventas["total_hectolitros"],
            "meta_hectolitros": ventas["meta_hectolitros"],
            "cumplimiento_pct": ventas["cumplimiento_pct"],
            "total_importe": ventas["total_importe"],
            "total_clientes_punto": punto["total_clientes_unicos"],
            "operaciones_punto": punto["total_operaciones"],
            "dias_laborales_transcurridos": productos["dias_laborales_transcurridos"],
            "dias_laborales_totales": productos["dias_laborales_totales"],
        },
        "gestores_ventas": ventas["gestores"],
        "ranking_general": ranking["general"],
        "ranking_semanal": ranking["semanal"],
        "cumplimiento_productos": productos["cumplimiento"],
    }


# --------------------------------------------------------------------
# Exportaciones Excel
# --------------------------------------------------------------------
@app.get("/api/sources/{source_id}/export/ventas.xlsx")
def export_ventas_xlsx(source_id: str, mes: str | None = Query(default=None)) -> Response:
    report = filter_by_period(_get_source(source_id), mes)
    suffix = f"_{mes}" if mes else ""
    return _xlsx_response(export_ventas(report, settings_store.load()), f"ventas{suffix}.xlsx")


@app.get("/api/sources/{source_id}/export/productos.xlsx")
def export_productos_xlsx(source_id: str, mes: str | None = Query(default=None)) -> Response:
    report = filter_by_period(_get_source(source_id), mes)
    suffix = f"_{mes}" if mes else ""
    return _xlsx_response(export_productos(report, settings_store.load()), f"productos{suffix}.xlsx")


@app.get("/api/sources/{source_id}/export/ranking.xlsx")
def export_ranking_xlsx(source_id: str, mes: str | None = Query(default=None)) -> Response:
    report = filter_by_period(_get_source(source_id), mes)
    suffix = f"_{mes}" if mes else ""
    return _xlsx_response(export_ranking(report), f"ranking{suffix}.xlsx")


@app.get("/api/sources/{source_id}/export/clientes-punto.xlsx")
def export_punto_xlsx(source_id: str, mes: str | None = Query(default=None)) -> Response:
    report = filter_by_period(_get_source(source_id), mes)
    suffix = f"_{mes}" if mes else ""
    return _xlsx_response(export_clientes_punto(report), f"clientes_punto{suffix}.xlsx")


@app.get("/api/sources/{source_id}/export/ventas-general.xlsx")
def export_ventas_general_xlsx(source_id: str, mes: str | None = Query(default=None)) -> Response:
    report = filter_by_period(_get_source(source_id), mes)
    suffix = f"_{mes}" if mes else ""
    return _xlsx_response(export_ventas_general(report, settings_store.load()), f"ventas_general{suffix}.xlsx")


@app.get("/api/sources/{source_id}/export/market.xlsx")
def export_market_xlsx(source_id: str, mes: str | None = Query(default=None)) -> Response:
    report = filter_by_period(_get_source(source_id), mes)
    suffix = f"_{mes}" if mes else ""
    return _xlsx_response(export_market(report, settings_store.load()), f"market{suffix}.xlsx")


@app.get("/api/sources/{source_id}/export/all.xlsx")
def export_all_xlsx(source_id: str, mes: str | None = Query(default=None)) -> Response:
    report = filter_by_period(_get_source(source_id), mes)
    suffix = f"_{mes}" if mes else ""
    return _xlsx_response(export_all(report, settings_store.load()), f"reporte_completo{suffix}.xlsx")


# --------------------------------------------------------------------
# Configuración (metas editables)
# --------------------------------------------------------------------
@app.get("/api/settings")
def get_settings() -> dict:
    return settings_store.load()


@app.put("/api/settings")
def put_settings(payload: dict) -> dict:
    return settings_store.save(payload)


@app.post("/api/settings/reset")
def reset_settings() -> dict:
    return settings_store.reset()
