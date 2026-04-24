"""FastAPI app: expone la API REST para el dashboard web."""
from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from core.sessions import sessions
from services.clientes_punto import compute_clientes_punto
from services.excel_export import (
    export_all,
    export_clientes_punto,
    export_productos,
    export_ranking,
    export_ventas,
)
from services.loader import load_report
from services.productos import compute_productos
from services.ranking import compute_ranking
from services.ventas import compute_ventas

app = FastAPI(
    title="Sucursal Analytics API",
    description="API para análisis del Reporte de Venta diario (estilo Power BI).",
    version="1.0.0",
)

# CORS abierto para desarrollo (restringir en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _get_report(session_id: str):
    report = sessions.get(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada. Sube el archivo nuevamente.")
    return report


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    """Carga un archivo Reporte de Venta (.xls/.xlsx) y crea la sesión."""
    if not file.filename or not file.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .xls o .xlsx")
    content = await file.read()
    try:
        report = load_report(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"No se pudo procesar el archivo: {e}") from e

    sid = sessions.put(report)
    return {
        "session_id": sid,
        "filename": file.filename,
        "rango": report.rango_str,
        "filas": int(len(report.df)),
    }


@app.get("/api/session/{sid}/ventas")
def api_ventas(sid: str) -> dict:
    return compute_ventas(_get_report(sid))


@app.get("/api/session/{sid}/productos")
def api_productos(sid: str) -> dict:
    return compute_productos(_get_report(sid))


@app.get("/api/session/{sid}/ranking")
def api_ranking(sid: str) -> dict:
    return compute_ranking(_get_report(sid))


@app.get("/api/session/{sid}/clientes-punto")
def api_clientes_punto(sid: str) -> dict:
    return compute_clientes_punto(_get_report(sid))


@app.get("/api/session/{sid}/dashboard")
def api_dashboard(sid: str) -> dict:
    """Agregado usado por la pantalla inicial del dashboard."""
    report = _get_report(sid)
    ventas = compute_ventas(report)
    productos = compute_productos(report)
    ranking = compute_ranking(report)
    punto = compute_clientes_punto(report)
    return {
        "rango": report.rango_str,
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
        "cumplimiento_productos": productos["cumplimiento"],
    }


def _xlsx_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/session/{sid}/export/ventas.xlsx")
def export_ventas_xlsx(sid: str) -> Response:
    return _xlsx_response(export_ventas(_get_report(sid)), "ventas.xlsx")


@app.get("/api/session/{sid}/export/productos.xlsx")
def export_productos_xlsx(sid: str) -> Response:
    return _xlsx_response(export_productos(_get_report(sid)), "productos.xlsx")


@app.get("/api/session/{sid}/export/ranking.xlsx")
def export_ranking_xlsx(sid: str) -> Response:
    return _xlsx_response(export_ranking(_get_report(sid)), "ranking.xlsx")


@app.get("/api/session/{sid}/export/clientes-punto.xlsx")
def export_punto_xlsx(sid: str) -> Response:
    return _xlsx_response(export_clientes_punto(_get_report(sid)), "clientes_punto.xlsx")


@app.get("/api/session/{sid}/export/all.xlsx")
def export_all_xlsx(sid: str) -> Response:
    return _xlsx_response(export_all(_get_report(sid)), "reporte_completo.xlsx")
