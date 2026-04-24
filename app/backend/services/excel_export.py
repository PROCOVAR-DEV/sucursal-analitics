"""Exportación a Excel (xlsxwriter) con formato para cada módulo."""
from __future__ import annotations

import io

import pandas as pd

from core.constants import GESTORES_CONFIG, GESTORES_PERMITIDOS, META_HECTOLITROS_TOTAL
from services.clientes_punto import compute_clientes_punto
from services.loader import ReportData
from services.productos import compute_productos
from services.ranking import compute_ranking
from services.ventas import compute_ventas


def _writer() -> tuple[io.BytesIO, pd.ExcelWriter]:
    buf = io.BytesIO()
    writer = pd.ExcelWriter(buf, engine="xlsxwriter")
    return buf, writer


def export_ventas(report: ReportData, config: dict | None = None) -> bytes:
    data = compute_ventas(report, config)
    buf, writer = _writer()
    wb = writer.book

    fmt_h = wb.add_format({"bold": True, "bg_color": "#1F4E79", "font_color": "white",
                            "border": 1, "align": "center"})
    fmt_kpi = wb.add_format({"bg_color": "#E2EFDA", "border": 1, "bold": True, "num_format": "#,##0.00"})
    fmt_title = wb.add_format({"bold": True, "font_size": 14, "font_color": "white",
                                "bg_color": "#203864", "align": "left"})
    fmt_num = wb.add_format({"num_format": "#,##0.00"})
    fmt_pct = wb.add_format({"num_format": "0.00%", "align": "center"})

    # Hoja Supervisor
    sup = pd.DataFrame(data["supervisor"])
    sup.to_excel(writer, sheet_name="Supervisor", index=False, startrow=3)
    ws = writer.sheets["Supervisor"]
    ws.merge_range(0, 0, 0, 6, f"Resumen de Ventas — Periodo {data['rango']}", fmt_title)
    for idx, col in enumerate(sup.columns):
        ws.write(3, idx, col, fmt_h)
        ws.set_column(idx, idx, 16, fmt_num if idx > 0 else None)
    # KPIs
    kpi_row = 5 + len(sup)
    ws.write(kpi_row, 0, "Total Hectolitros", fmt_h)
    ws.write(kpi_row, 1, data["total_hectolitros"], fmt_kpi)
    ws.write(kpi_row + 1, 0, "Meta", fmt_h)
    ws.write(kpi_row + 1, 1, data["meta_hectolitros"], fmt_kpi)
    ws.write(kpi_row + 2, 0, "% Cumplimiento", fmt_h)
    ws.write(kpi_row + 2, 1, data["cumplimiento_pct"] / 100, fmt_pct)

    # Hojas por gestor
    for g in data["gestores"]:
        df_conv = pd.DataFrame(g["conversion"])
        sheet = g["gestor"][:31]
        if df_conv.empty:
            df_conv = pd.DataFrame([{"producto": "-", "tamano": "-", "blisters": 0, "pallets": 0, "hectolitros": 0}])
        df_conv.to_excel(writer, sheet_name=sheet, index=False, startrow=4)
        wsg = writer.sheets[sheet]
        wsg.merge_range(0, 0, 0, 4, f"{g['nombre']} — {g['sector']}", fmt_title)
        wsg.write(2, 0, "Total Hectolitros"); wsg.write(2, 1, g["total_hectolitros"], fmt_kpi)
        wsg.write(2, 2, "Cuota"); wsg.write(2, 3, g["cuota_hl"], fmt_kpi)
        wsg.write(2, 4, "% Cumpl."); wsg.write(2, 5, g["cumplimiento_pct"] / 100, fmt_pct)
        for idx, col in enumerate(df_conv.columns):
            wsg.write(4, idx, col, fmt_h)
        wsg.set_column(0, 10, 15)

    writer.close()
    return buf.getvalue()


def export_productos(report: ReportData, config: dict | None = None) -> bytes:
    data = compute_productos(report, config)
    buf, writer = _writer()
    wb = writer.book

    fmt_h = wb.add_format({"bold": True, "bg_color": "#1F4E79", "font_color": "white", "border": 1})
    fmt_num = wb.add_format({"num_format": "#,##0.00", "border": 1})
    fmt_pct = wb.add_format({"num_format": "0.00%", "border": 1})
    fmt_red = wb.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006", "border": 1, "num_format": "#,##0.00"})
    fmt_green = wb.add_format({"bg_color": "#C6EFCE", "font_color": "#006100", "border": 1, "num_format": "#,##0.00"})

    # Cumplimiento
    ws = wb.add_worksheet("Cumplimiento")
    ws.write(0, 0, f"Días: {data['dias_laborales_transcurridos']}/{data['dias_laborales_totales']} "
                    f"(restan {data['dias_laborales_restantes']})")
    headers = ["Producto", "Meta", "Real", "% Cumpl.", "Debería", "Delta", "Prom. Diario", "Nec./día"]
    for i, h in enumerate(headers):
        ws.write(2, i, h, fmt_h)
    for r, row in enumerate(data["cumplimiento"]):
        ws.write(3 + r, 0, row["producto"])
        ws.write(3 + r, 1, row["meta"], fmt_num)
        ws.write(3 + r, 2, row["real"], fmt_num)
        ws.write(3 + r, 3, row["cumplimiento_pct"] / 100, fmt_pct)
        ws.write(3 + r, 4, row["deberia"], fmt_num)
        ws.write(3 + r, 5, row["delta"], fmt_green if row["delta"] >= 0 else fmt_red)
        ws.write(3 + r, 6, row["prom_diario"], fmt_num)
        ws.write(3 + r, 7, row["necesario_por_dia"], fmt_num)
    ws.set_column(0, 7, 16)

    # Resumen CES
    pd.DataFrame(data["resumen_ces"]).to_excel(writer, sheet_name="CES", index=False)
    pd.DataFrame(data["resumen_procovar"]).to_excel(writer, sheet_name="PROCOVAR", index=False)

    # Por gestor
    for g in data["por_gestor"]:
        sheet = g["gestor"][:31]
        ces = pd.DataFrame(g["ces"]) if g["ces"] else pd.DataFrame(columns=["producto", "total", "cantidad"])
        proc = pd.DataFrame(g["procovar"]) if g["procovar"] else pd.DataFrame(columns=["producto", "total", "cantidad"])
        ces.to_excel(writer, sheet_name=sheet, index=False, startrow=1)
        wsg = writer.sheets[sheet]
        wsg.write(0, 0, f"CES — {g['gestor']}", fmt_h)
        start_p = 4 + len(ces)
        wsg.write(start_p, 0, f"PROCOVAR — {g['gestor']}", fmt_h)
        proc.to_excel(writer, sheet_name=sheet, index=False, startrow=start_p + 1)

    writer.close()
    return buf.getvalue()


def export_ranking(report: ReportData) -> bytes:
    data = compute_ranking(report)
    buf, writer = _writer()

    for key, name in (("general", "Ranking General"),
                      ("semanal", "Ranking Semanal"),
                      ("diario", "Ranking Diario")):
        df = pd.DataFrame(data[key])
        if df.empty:
            df = pd.DataFrame([{"info": "sin datos"}])
        df.to_excel(writer, sheet_name=name, index=False)

    writer.close()
    return buf.getvalue()


def export_clientes_punto(report: ReportData) -> bytes:
    data = compute_clientes_punto(report)
    buf, writer = _writer()
    wb = writer.book
    fmt_h = wb.add_format({"bold": True, "bg_color": "#1F4E79", "font_color": "white", "border": 1})
    fmt_num = wb.add_format({"num_format": "#,##0.00", "border": 1})

    df = pd.DataFrame(data["filas"])
    if df.empty:
        df = pd.DataFrame([{"info": "sin clientes punto"}])
    df.to_excel(writer, sheet_name="Clientes Punto", index=False, startrow=2)
    ws = writer.sheets["Clientes Punto"]
    ws.write(0, 0, f"Clientes Punto — Periodo {data['rango']}")
    for idx, col in enumerate(df.columns):
        ws.write(2, idx, col, fmt_h)
        ws.set_column(idx, idx, 16)

    pd.DataFrame(data["por_gestor"]).to_excel(writer, sheet_name="Resumen", index=False)

    writer.close()
    return buf.getvalue()


def export_all(report: ReportData, config: dict | None = None) -> bytes:
    """Un único libro con todas las hojas (resumen completo)."""
    buf, writer = _writer()
    ventas = compute_ventas(report, config)
    productos = compute_productos(report, config)
    ranking = compute_ranking(report)
    punto = compute_clientes_punto(report)

    pd.DataFrame(ventas["supervisor"]).to_excel(writer, sheet_name="Supervisor", index=False)
    pd.DataFrame(productos["cumplimiento"]).to_excel(writer, sheet_name="Cumplimiento", index=False)
    pd.DataFrame(productos["resumen_ces"]).to_excel(writer, sheet_name="CES", index=False)
    pd.DataFrame(productos["resumen_procovar"]).to_excel(writer, sheet_name="PROCOVAR", index=False)
    pd.DataFrame(ranking["general"]).to_excel(writer, sheet_name="Ranking General", index=False)
    pd.DataFrame(ranking["semanal"]).to_excel(writer, sheet_name="Ranking Semanal", index=False)
    pd.DataFrame(ranking["diario"]).to_excel(writer, sheet_name="Ranking Diario", index=False)
    pd.DataFrame(punto["filas"]).to_excel(writer, sheet_name="Clientes Punto", index=False)
    pd.DataFrame(punto["por_gestor"]).to_excel(writer, sheet_name="Punto Resumen", index=False)

    writer.close()
    return buf.getvalue()
