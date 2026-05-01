"""Exportación a Excel (xlsxwriter) con formato idéntico al de los scripts Python."""
from __future__ import annotations

import io
from typing import Any

import pandas as pd

from core.constants import GESTORES_CONFIG, GESTORES_PERMITIDOS
from services.clientes_punto import compute_clientes_punto
from services.loader import STD_COLS, ReportData, only_valid_gestores
from services.productos import compute_productos
from services.ranking import compute_ranking
from services.settings_store import config_for_report
from services.ventas import compute_ventas


def _writer() -> tuple[io.BytesIO, pd.ExcelWriter]:
    buf = io.BytesIO()
    writer = pd.ExcelWriter(buf, engine="xlsxwriter",
                            engine_kwargs={"options": {"nan_inf_to_errors": True}})
    return buf, writer


def _autosize(ws: Any, df: pd.DataFrame, header_fmt: Any) -> None:
    for col_idx, col_name in enumerate(df.columns):
        max_len = max(
            [len(str(col_name))]
            + [len(str(x)) for x in df[col_name].astype(str).values[:500]]
        )
        ws.set_column(col_idx, col_idx, min(max(10, max_len + 2), 60))
    ws.set_row(0, 20, header_fmt)


def _apply_bands(ws: Any, start_row: int, end_row: int, band_fmt: Any) -> None:
    for r in range(start_row, end_row + 1):
        if (r - start_row) % 2 == 1:
            ws.set_row(r, None, band_fmt)


def export_ventas(report: ReportData, config: dict | None = None) -> bytes:
    data = compute_ventas(report, config)
    buf, writer = _writer()
    wb = writer.book

    color_header = "#1F4E79"
    color_band   = "#D9E1F2"
    color_block  = "#FCE4D6"
    color_kpi    = "#E2EFDA"
    color_title  = "#203864"

    fmt_h          = wb.add_format({"bold": True, "bg_color": color_header,
                                    "font_color": "white", "border": 1, "align": "center"})
    fmt_num        = wb.add_format({"num_format": "0.00"})
    fmt_int        = wb.add_format({"num_format": "0"})
    fmt_band       = wb.add_format({"bg_color": color_band})
    fmt_block      = wb.add_format({"bg_color": color_block, "border": 1, "bold": True, "num_format": "0.00"})
    fmt_block_txt  = wb.add_format({"bg_color": color_block, "border": 1, "bold": True})
    fmt_kpi        = wb.add_format({"bg_color": color_kpi,   "border": 1, "bold": True, "num_format": "#,##0.00"})
    fmt_kpi_txt    = wb.add_format({"bg_color": color_kpi,   "border": 1, "bold": True})
    fmt_big_title  = wb.add_format({"bold": True, "font_size": 16, "font_color": "white",
                                    "align": "left", "valign": "vcenter", "bg_color": color_title})
    fmt_subtitle   = wb.add_format({"italic": True, "font_color": "white",
                                    "align": "right", "valign": "vcenter", "bg_color": color_title})
    fmt_pct        = wb.add_format({"num_format": "0%", "align": "center", "valign": "vcenter"})
    fmt_pct_hidden = wb.add_format({"num_format": ";;;"})

    # Datos de transacciones para las hojas de cada gestor
    df_raw = report.df.copy()
    df_raw = df_raw[df_raw["IsMalta"] | df_raw["IsParranda"]].copy()
    export_std = [c for c in [
        STD_COLS["op"], STD_COLS["fecha"], STD_COLS["merc"],
        STD_COLS["cant"], STD_COLS["importe"], STD_COLS["suma"], "Hectolitros",
    ] if c in df_raw.columns]

    supervisor_rows: list[dict] = []

    for g_data in data["gestores"]:
        g = g_data["gestor"]
        sub = df_raw[df_raw["GestorDetectado"] == g].copy()
        if STD_COLS["fecha"] in sub.columns:
            sub = sub.sort_values([STD_COLS["fecha"]])

        to_write = sub[export_std].copy()
        for c in to_write.columns:
            if c != STD_COLS["op"] and pd.api.types.is_numeric_dtype(to_write[c]):
                to_write[c] = to_write[c].round(2)

        sheet = g[:31]
        to_write.to_excel(writer, sheet_name=sheet, index=False)
        wsg = writer.sheets[sheet]
        wsg.freeze_panes(1, 0)
        _autosize(wsg, to_write, fmt_h)

        for idx, col_name in enumerate(to_write.columns):
            if col_name == STD_COLS["op"]:
                wsg.set_column(idx, idx, None, fmt_int)
            elif pd.api.types.is_numeric_dtype(to_write[col_name]):
                wsg.set_column(idx, idx, None, fmt_num)

        if len(to_write) > 0:
            _apply_bands(wsg, 1, len(to_write), fmt_band)
            wsg.add_table(0, 0, len(to_write), len(to_write.columns) - 1, {
                "name": f"Tabla_{g.replace(' ', '')[:20]}",
                "style": "Table Style Medium 2",
                "columns": [{"header": h} for h in to_write.columns],
            })

        # KPIs
        kpi_row = len(to_write) + 2
        wsg.write(kpi_row,     0, "VENTAS",            fmt_block_txt)
        wsg.write_number(kpi_row, 1, g_data["total_importe"], fmt_block)
        wsg.write(kpi_row + 1, 0, "Total Hectolitros", fmt_block_txt)
        wsg.write_number(kpi_row + 1, 1, g_data["total_hectolitros"], fmt_block)
        wsg.write(kpi_row + 1, 3, g_data["cumplimiento_pct"] / 100, fmt_pct)

        # Tabla de conversión
        conv_row = kpi_row + 4
        wsg.merge_range(conv_row, 0, conv_row, 6,
                        "Conversión de Cantidad a Blisters y Pallets por Producto", fmt_kpi_txt)
        conv_df = pd.DataFrame(g_data["conversion"])
        if conv_df.empty:
            conv_df = pd.DataFrame(
                columns=["producto", "tamano", "blisters", "pallets", "hectolitros"]
            )
        start_r = conv_row + 2
        conv_df.to_excel(writer, sheet_name=sheet, index=False, startrow=start_r)
        for j, coln in enumerate(conv_df.columns):
            wsg.write(start_r, j, coln, fmt_h)
        wsg.set_column(0, len(conv_df.columns) - 1, 12)
        if len(conv_df) > 0:
            _apply_bands(wsg, start_r + 1, start_r + len(conv_df), fmt_band)
            wsg.add_table(start_r, 0, start_r + len(conv_df), len(conv_df.columns) - 1, {
                "name": f"TablaConv_{g.replace(' ', '')[:15]}",
                "style": "Table Style Medium 9",
                "columns": [{"header": h} for h in conv_df.columns],
            })

        supervisor_rows.append({
            "Gestor":            g,
            "Total Venta":       g_data["total_importe"],
            "M330":              g_data.get("malta_330",    0.0),
            "P330":              g_data.get("parranda_330", 0.0),
            "P500":              g_data.get("parranda_500", 0.0),
            "P1500":             g_data.get("parranda_1500", 0.0),
            "Total Hectolitros": g_data["total_hectolitros"],
        })

    # --- Hoja Supervisor ---
    sup_df = pd.DataFrame(supervisor_rows)
    sup_df.to_excel(writer, sheet_name="Supervisor", index=False, startrow=5)
    ws = writer.sheets["Supervisor"]
    ws.merge_range(0, 0, 1, 6, "Resumen de Ventas - Supervisor (SOLO PARRANDA/MALTA)", fmt_big_title)
    ws.merge_range(0, 7, 1, 9, f"Semana: {data['rango']}", fmt_subtitle)
    ws.set_row(0, 28)
    ws.set_row(1, 20)
    ws.freeze_panes(6, 0)
    _autosize(ws, sup_df, fmt_h)
    if len(sup_df) > 0:
        _apply_bands(ws, 6, 5 + len(sup_df), fmt_band)
        ws.add_table(5, 0, 5 + len(sup_df), len(sup_df.columns) - 1, {
            "name": "Tabla_Supervisor",
            "style": "Table Style Medium 9",
            "columns": [{"header": h} for h in sup_df.columns],
        })

    # KPI ventas totales (encima de la tabla)
    ws.merge_range(3, 0, 3, 2, "VENTAS TOTALES", fmt_kpi_txt)
    ws.merge_range(4, 0, 4, 2, data["total_importe"], fmt_kpi)

    # Totales por producto (debajo de la tabla)
    prod_row = 8 + len(sup_df) + 2
    for i, (lbl, col) in enumerate([
        ("TOTAL M330", "M330"), ("TOTAL P330", "P330"),
        ("TOTAL P500", "P500"), ("TOTAL P1500", "P1500"),
    ]):
        val = round(float(sup_df[col].sum()), 2) if col in sup_df.columns else 0.0
        ws.merge_range(prod_row + i, 0, prod_row + i, 2, lbl, fmt_block_txt)
        ws.merge_range(prod_row + i, 3, prod_row + i, 5, val, fmt_block)

    ws.merge_range(prod_row + 4, 0, prod_row + 4, 2, "TOTAL HECTOLITROS", fmt_block_txt)
    ws.merge_range(prod_row + 4, 3, prod_row + 4, 5, data["total_hectolitros"], fmt_block)

    meta_row = prod_row + 8
    ws.merge_range(meta_row, 0, meta_row, 2, "META HECTOLITROS", fmt_block_txt)
    ws.merge_range(meta_row, 3, meta_row, 5, data["meta_hectolitros"], fmt_block)
    cumpl_hecto = data["cumplimiento_pct"] / 100
    ws.merge_range(meta_row, 6, meta_row, 7, "% CUMPL. HECTO", fmt_kpi_txt)
    ws.merge_range(meta_row, 8, meta_row, 10, cumpl_hecto, fmt_pct_hidden)
    ws.write(meta_row, 11, cumpl_hecto, fmt_pct)
    ws.conditional_format(meta_row, 8, meta_row, 10, {
        "type": "data_bar", "bar_color": "#70AD47",
        "min_type": "num", "min_value": 0,
        "max_type": "num", "max_value": 1,
        "bar_only": True,
    })
    for c in range(12):
        ws.set_column(c, c, 14)
    ws.set_column(0, 0, 20)

    writer.close()
    return buf.getvalue()


def export_productos(report: ReportData, config: dict | None = None) -> bytes:
    data = compute_productos(report, config)
    buf, writer = _writer()
    wb = writer.book

    fmt_h     = wb.add_format({"bold": True, "bg_color": "#1F4E79",
                                "font_color": "white", "border": 1})
    fmt_num   = wb.add_format({"num_format": "#,##0.00", "border": 1})
    fmt_pct   = wb.add_format({"num_format": "0.00%", "border": 1})
    fmt_red   = wb.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006",
                                "border": 1, "num_format": "#,##0.00"})
    fmt_green = wb.add_format({"bg_color": "#C6EFCE", "font_color": "#006100",
                                "border": 1, "num_format": "#,##0.00"})
    fmt_brd   = wb.add_format({"border": 1})

    # --- Hoja Cumplimiento ---
    ws_c = wb.add_worksheet("Cumplimiento")
    ws_c.write(0, 0,
               f"Días: {data['dias_laborales_transcurridos']} de "
               f"{data['dias_laborales_totales']} "
               f"(Quedan {data['dias_laborales_restantes']})")
    hdrs = ["Producto", "Meta Mes", "Venta Real", "% Cumpl.",
            "Debería ir", "Estado", "Prom. Diario", "Nec. x Día"]
    for i, h in enumerate(hdrs):
        ws_c.write(2, i, h, fmt_h)
    for r, row in enumerate(data["cumplimiento"]):
        ws_c.write(3 + r, 0, row["producto"],   fmt_brd)
        ws_c.write(3 + r, 1, row["meta"],        fmt_num)
        ws_c.write(3 + r, 2, row["real"],        fmt_num)
        ws_c.write(3 + r, 3, row["cumplimiento_pct"] / 100, fmt_pct)
        ws_c.write(3 + r, 4, row["deberia"],     fmt_num)
        ws_c.write(3 + r, 5, row["delta"],
                   fmt_green if row["delta"] >= 0 else fmt_red)
        ws_c.write(3 + r, 6, row["prom_diario"],       fmt_num)
        ws_c.write(3 + r, 7, row["necesario_por_dia"], fmt_num)
    ws_c.set_column(0, 7, 15)

    # --- Hoja Resumen (CES + PROCOVAR juntos, igual que el script) ---
    resumen_ces      = pd.DataFrame(data["resumen_ces"])
    resumen_procovar = pd.DataFrame(data["resumen_procovar"])

    if not resumen_ces.empty:
        resumen_ces.to_excel(writer, sheet_name="Resumen", index=False, startrow=1)
    else:
        pd.DataFrame(columns=["producto", "total", "cantidad"]).to_excel(
            writer, sheet_name="Resumen", index=False, startrow=1
        )
    ws_res = writer.sheets["Resumen"]
    ws_res.write(0, 0, "Resumen Global CES", fmt_h)

    if not resumen_ces.empty:
        chart_ces = wb.add_chart({"type": "pie"})
        chart_ces.add_series({
            "name": "Ventas CES",
            "categories": ["Resumen", 2, 0, 1 + len(resumen_ces), 0],
            "values":      ["Resumen", 2, 1, 1 + len(resumen_ces), 1],
            "data_labels": {"percentage": True, "position": "outside_end"},
        })
        ws_res.insert_chart("J2", chart_ces)

    start_proc = (len(resumen_ces) if not resumen_ces.empty else 0) + 6
    ws_res.write(start_proc - 1, 0, "Resumen Global PROCOVAR", fmt_h)
    if not resumen_procovar.empty:
        resumen_procovar.to_excel(writer, sheet_name="Resumen", index=False, startrow=start_proc)
        chart_proc = wb.add_chart({"type": "pie"})
        chart_proc.add_series({
            "name": "Ventas PROCOVAR",
            "categories": ["Resumen", start_proc + 1, 0,
                           start_proc + len(resumen_procovar), 0],
            "values":      ["Resumen", start_proc + 1, 1,
                           start_proc + len(resumen_procovar), 1],
            "data_labels": {"percentage": True},
        })
        ws_res.insert_chart(f"J{start_proc + 1}", chart_proc)
    ws_res.set_column(0, 3, 15)

    # --- Hojas por gestor ---
    for g in data["por_gestor"]:
        sheet = g["gestor"][:31]
        ces  = (pd.DataFrame(g["ces"])
                if g["ces"] else pd.DataFrame(columns=["producto", "total", "cantidad"]))
        proc = (pd.DataFrame(g["procovar"])
                if g["procovar"] else pd.DataFrame(columns=["producto", "total", "cantidad"]))

        ces.to_excel(writer, sheet_name=sheet, index=False, startrow=1)
        wsg = writer.sheets[sheet]
        wsg.write(0, 0, f"CES — {g['gestor']}", fmt_h)

        if not ces.empty:
            ch = wb.add_chart({"type": "pie"})
            ch.add_series({
                "categories": [sheet, 2, 0, 1 + len(ces), 0],
                "values":     [sheet, 2, 1, 1 + len(ces), 1],
                "data_labels": {"percentage": True},
            })
            wsg.insert_chart("J2", ch)

        start_p = len(ces) + 4
        wsg.write(start_p, 0, f"PROCOVAR — {g['gestor']}", fmt_h)
        proc.to_excel(writer, sheet_name=sheet, index=False, startrow=start_p + 1)

        if not proc.empty:
            chp = wb.add_chart({"type": "pie"})
            chp.add_series({
                "categories": [sheet, start_p + 2, 0, start_p + 1 + len(proc), 0],
                "values":     [sheet, start_p + 2, 1, start_p + 1 + len(proc), 1],
                "data_labels": {"percentage": True},
            })
            wsg.insert_chart(f"J{start_p + 2}", chp)

    writer.close()
    return buf.getvalue()


def export_ranking(report: ReportData) -> bytes:
    data = compute_ranking(report)
    buf, writer = _writer()
    wb = writer.book
    rango = data["rango"]

    color_title  = "#203864"
    color_header = "#1F4E79"
    color_gold   = "#FFD700"
    color_silver = "#C0C0C0"
    color_bronze = "#CD7F32"

    fmt_big_title = wb.add_format({
        "bold": True, "font_size": 18, "font_color": "white",
        "align": "center", "valign": "vcenter",
        "bg_color": color_title, "border": 1,
    })
    fmt_subtitle = wb.add_format({
        "italic": True, "font_size": 11, "font_color": "white",
        "align": "center", "valign": "vcenter", "bg_color": color_title,
    })
    fmt_header = wb.add_format({
        "bold": True, "font_color": "white", "bg_color": color_header,
        "border": 1, "align": "center", "valign": "vcenter", "font_size": 11,
    })
    fmt_num  = wb.add_format({"num_format": "#,##0", "align": "center", "border": 1})
    fmt_pos  = wb.add_format({"bold": True, "align": "center", "border": 1, "font_size": 13})
    fmt_name = wb.add_format({"bold": True, "align": "left", "border": 1, "font_size": 11, "indent": 1})
    fmt_total_lbl = wb.add_format({
        "bold": True, "font_size": 12, "border": 1, "align": "right",
        "bg_color": color_title, "font_color": "white", "indent": 1,
    })
    fmt_total_val = wb.add_format({
        "bold": True, "font_size": 12, "border": 1, "align": "center",
        "bg_color": color_title, "font_color": "white", "num_format": "#,##0",
    })
    fmt_week_title = wb.add_format({
        "bold": True, "font_size": 13, "font_color": "white",
        "bg_color": "#2E75B6", "align": "left", "valign": "vcenter",
        "border": 1, "indent": 1,
    })
    fmt_date = wb.add_format({"num_format": "dd/mm/yyyy", "align": "center", "border": 1})

    medal_fmts: dict[int, tuple] = {
        1: (
            wb.add_format({"bold": True, "bg_color": color_gold, "border": 1, "align": "center", "font_size": 14}),
            wb.add_format({"bold": True, "bg_color": color_gold, "border": 1, "align": "left", "font_size": 12, "indent": 1}),
            wb.add_format({"bold": True, "bg_color": color_gold, "border": 1, "align": "center", "font_size": 12, "num_format": "#,##0"}),
        ),
        2: (
            wb.add_format({"bold": True, "bg_color": color_silver, "border": 1, "align": "center", "font_size": 13}),
            wb.add_format({"bold": True, "bg_color": color_silver, "border": 1, "align": "left", "font_size": 11, "indent": 1}),
            wb.add_format({"bold": True, "bg_color": color_silver, "border": 1, "align": "center", "font_size": 11, "num_format": "#,##0"}),
        ),
        3: (
            wb.add_format({"bold": True, "bg_color": color_bronze, "font_color": "white", "border": 1, "align": "center", "font_size": 13}),
            wb.add_format({"bold": True, "bg_color": color_bronze, "font_color": "white", "border": 1, "align": "left", "font_size": 11, "indent": 1}),
            wb.add_format({"bold": True, "bg_color": color_bronze, "font_color": "white", "border": 1, "align": "center", "font_size": 11, "num_format": "#,##0"}),
        ),
    }
    MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}

    def write_block(ws: Any, start: int, rows: list[dict],
                    pos_k: str, name_k: str, val_k: str) -> int:
        for i, row in enumerate(rows):
            r   = start + i
            pos = int(row[pos_k])
            medal = MEDAL.get(pos, "")
            label = f"{medal} {pos}" if medal else str(pos)
            val   = float(row[val_k])
            if pos in medal_fmts:
                fp, fn, fv = medal_fmts[pos]
                ws.write(r, 0, label,       fp)
                ws.write(r, 1, row[name_k], fn)
                ws.write_number(r, 2, val,  fv)
            else:
                ws.write(r, 0, label,        fmt_pos)
                ws.write(r, 1, row[name_k],  fmt_name)
                ws.write_number(r, 2, val,   fmt_num)
        return start + len(rows)

    # --- Hoja 1: Ranking General ---
    ws_gen = wb.add_worksheet("Ranking General")
    ws_gen.merge_range(0, 0, 1, 2, "RANKING DE VENTAS", fmt_big_title)
    ws_gen.merge_range(2, 0, 2, 2, f"Periodo: {rango}", fmt_subtitle)
    ws_gen.set_row(0, 30); ws_gen.set_row(1, 22); ws_gen.set_row(2, 20)
    r_hdr = 4
    ws_gen.write(r_hdr, 0, "Posición",     fmt_header)
    ws_gen.write(r_hdr, 1, "Vendedor",     fmt_header)
    ws_gen.write(r_hdr, 2, "Ventas (USD)", fmt_header)
    general = data["general"]
    end_gen = write_block(ws_gen, r_hdr + 1, general, "posicion", "vendedor", "ventas")
    total_row = end_gen + 1
    ws_gen.merge_range(total_row, 0, total_row, 1, "TOTAL VENTAS", fmt_total_lbl)
    ws_gen.write_number(total_row, 2, sum(float(x["ventas"]) for x in general), fmt_total_val)
    if general:
        ws_gen.conditional_format(r_hdr + 1, 2, r_hdr + len(general), 2, {
            "type": "data_bar", "bar_color": "#4472C4", "bar_only": False,
            "min_type": "num", "min_value": 0,
        })
    ws_gen.set_column(0, 0, 12)
    ws_gen.set_column(1, 1, 22)
    ws_gen.set_column(2, 2, 20)
    ws_gen.freeze_panes(5, 0)

    # --- Hoja 2: Ranking Semanal ---
    ws_sem = wb.add_worksheet("Ranking Semanal")
    ws_sem.merge_range(0, 0, 1, 2, "RANKING SEMANAL", fmt_big_title)
    ws_sem.merge_range(2, 0, 2, 2, f"Periodo: {rango}", fmt_subtitle)
    ws_sem.set_row(0, 30); ws_sem.set_row(1, 22); ws_sem.set_row(2, 20)
    semanal_list = data["semanal"]
    semanas_seen: list[str] = []
    for row in semanal_list:
        if row["semana"] not in semanas_seen:
            semanas_seen.append(row["semana"])
    cur = 4
    for semana in semanas_seen:
        bloque = sorted([r for r in semanal_list if r["semana"] == semana],
                        key=lambda x: x["posicion"])
        ws_sem.merge_range(cur, 0, cur, 2, f"Semana: {semana}", fmt_week_title)
        cur += 1
        ws_sem.write(cur, 0, "Posición",     fmt_header)
        ws_sem.write(cur, 1, "Vendedor",     fmt_header)
        ws_sem.write(cur, 2, "Ventas (USD)", fmt_header)
        cur += 1
        end = write_block(ws_sem, cur, bloque, "posicion", "vendedor", "ventas")
        if bloque:
            ws_sem.conditional_format(cur, 2, end - 1, 2, {
                "type": "data_bar", "bar_color": "#4472C4", "bar_only": False,
                "min_type": "num", "min_value": 0,
            })
        cur = end + 1
    ws_sem.set_column(0, 0, 12)
    ws_sem.set_column(1, 1, 22)
    ws_sem.set_column(2, 2, 20)
    ws_sem.freeze_panes(4, 0)

    # --- Hoja 3: Progreso Diario (acumulado) ---
    ws_dia = wb.add_worksheet("Progreso Diario")
    ws_dia.merge_range(0, 0, 1, 3, "PROGRESO DIARIO ACUMULADO", fmt_big_title)
    ws_dia.merge_range(2, 0, 2, 3, f"Periodo: {rango}", fmt_subtitle)
    ws_dia.set_row(0, 30); ws_dia.set_row(1, 22); ws_dia.set_row(2, 20)
    r_hdr = 4
    ws_dia.write(r_hdr, 0, "Fecha",          fmt_header)
    ws_dia.write(r_hdr, 1, "Posición",        fmt_header)
    ws_dia.write(r_hdr, 2, "Vendedor",        fmt_header)
    ws_dia.write(r_hdr, 3, "Acumulado (USD)", fmt_header)
    diario_list = data["diario"]
    fechas_seen: list[str] = []
    for row in diario_list:
        if row["fecha"] not in fechas_seen:
            fechas_seen.append(row["fecha"])
    cur = r_hdr + 1
    for fecha_str in fechas_seen:
        bloque = sorted([r for r in diario_list if r["fecha"] == fecha_str],
                        key=lambda x: x["posicion"])
        try:
            dt = pd.Timestamp(fecha_str).to_pydatetime()
        except Exception:
            dt = None
        for i, row in enumerate(bloque):
            pos   = int(row["posicion"])
            medal = MEDAL.get(pos, "")
            label = f"{medal} {pos}" if medal else str(pos)
            val   = float(row["acumulado"])
            if i == 0 and dt is not None:
                ws_dia.write_datetime(cur, 0, dt, fmt_date)
            else:
                ws_dia.write(cur, 0, "", fmt_date)
            if pos in medal_fmts:
                fp, fn, fv = medal_fmts[pos]
                ws_dia.write(cur, 1, label,          fp)
                ws_dia.write(cur, 2, row["vendedor"], fn)
                ws_dia.write_number(cur, 3, val,      fv)
            else:
                ws_dia.write(cur, 1, label,           fmt_pos)
                ws_dia.write(cur, 2, row["vendedor"],  fmt_name)
                ws_dia.write_number(cur, 3, val,       fmt_num)
            cur += 1
        cur += 1
    ws_dia.set_column(0, 0, 14)
    ws_dia.set_column(1, 1, 12)
    ws_dia.set_column(2, 2, 22)
    ws_dia.set_column(3, 3, 20)
    ws_dia.freeze_panes(5, 0)

    # --- Hoja 4: Evolución (gráfico de líneas) ---
    if diario_list:
        try:
            diario_df = pd.DataFrame(diario_list)
            diario_df["fecha"] = pd.to_datetime(diario_df["fecha"])
            pivot = diario_df.pivot_table(
                index="fecha", columns="vendedor",
                values="acumulado", fill_value=0,
            ).reset_index()
            pivot.columns.name = None
            ws_dt = wb.add_worksheet("_datos_grafico")
            ws_dt.hide()
            ws_dt.write(0, 0, "Fecha")
            gestores_piv = [c for c in pivot.columns if c != "fecha"]
            for j, g in enumerate(gestores_piv):
                ws_dt.write(0, j + 1, g)
            fmt_dh = wb.add_format({"num_format": "dd/mm/yyyy"})
            for i, (_, row) in enumerate(pivot.iterrows()):
                ws_dt.write_datetime(i + 1, 0, row["fecha"].to_pydatetime(), fmt_dh)
                for j, g in enumerate(gestores_piv):
                    ws_dt.write_number(i + 1, j + 1, float(row[g]))
            n_rows = len(pivot)
            chart = wb.add_chart({"type": "line"})
            chart.set_title({"name": "Evolución de Ventas Acumuladas por Vendedor"})
            chart.set_x_axis({"name": "Fecha", "num_format": "dd/mm", "date_axis": True})
            chart.set_y_axis({"name": "Ventas Acumuladas (USD)", "num_format": "#,##0"})
            chart.set_size({"width": 900, "height": 500})
            chart.set_style(10)
            colors = ["#4472C4", "#ED7D31", "#70AD47", "#FFC000", "#5B9BD5", "#FF6384"]
            for j, g in enumerate(gestores_piv):
                chart.add_series({
                    "name":       g,
                    "categories": ["_datos_grafico", 1, 0, n_rows, 0],
                    "values":     ["_datos_grafico", 1, j + 1, n_rows, j + 1],
                    "line":   {"color": colors[j % len(colors)], "width": 2.5},
                    "marker": {"type": "circle", "size": 5},
                })
            chart.set_legend({"position": "bottom"})
            ws_ev = wb.add_worksheet("Evolución")
            ws_ev.merge_range(0, 0, 1, 8, "EVOLUCIÓN DE VENTAS ACUMULADAS", fmt_big_title)
            ws_ev.set_row(0, 30); ws_ev.set_row(1, 22)
            ws_ev.insert_chart("A4", chart)
        except Exception:
            pass

    writer.close()
    return buf.getvalue()


def export_clientes_punto(report: ReportData) -> bytes:
    data = compute_clientes_punto(report)
    buf, writer = _writer()
    wb = writer.book

    color_header = "#1F4E79"
    color_band   = "#D9E1F2"
    color_kpi    = "#E2EFDA"
    color_blk    = "#FCE4D6"
    color_title  = "#203864"

    fmt_h       = wb.add_format({"bold": True, "font_color": "white",
                                  "bg_color": color_header, "border": 1, "align": "center"})
    fmt_num     = wb.add_format({"num_format": "#,##0.00"})
    fmt_int     = wb.add_format({"num_format": "0"})
    fmt_band    = wb.add_format({"bg_color": color_band})
    fmt_kpi     = wb.add_format({"bg_color": color_kpi, "border": 1, "bold": True, "num_format": "#,##0.00"})
    fmt_kpi_txt = wb.add_format({"bg_color": color_kpi, "border": 1, "bold": True})
    fmt_blk     = wb.add_format({"bg_color": color_blk, "border": 1, "bold": True, "num_format": "#,##0.00"})
    fmt_blk_txt = wb.add_format({"bg_color": color_blk, "border": 1, "bold": True})
    fmt_title   = wb.add_format({"bold": True, "font_size": 14, "font_color": "white",
                                  "bg_color": color_title, "align": "left", "valign": "vcenter"})
    fmt_sub     = wb.add_format({"italic": True, "font_color": "white",
                                  "bg_color": color_title, "align": "right", "valign": "vcenter"})

    df = pd.DataFrame(data["filas"])
    if df.empty:
        df = pd.DataFrame([{"info": "sin clientes punto"}])

    df.to_excel(writer, sheet_name="Clientes Punto", index=False, startrow=2)
    ws = writer.sheets["Clientes Punto"]
    ncols = len(df.columns)

    ws.merge_range(0, 0, 0, max(ncols - 2, 0),
                   "Clientes que vinieron por su cuenta (punto)", fmt_title)
    ws.merge_range(0, max(ncols - 1, 1), 0, ncols - 1,
                   f"Periodo: {data['rango']}", fmt_sub)
    ws.set_row(0, 26)
    ws.set_row(1, 4)
    ws.set_row(2, 20, fmt_h)
    ws.freeze_panes(3, 0)

    for idx, col_name in enumerate(df.columns):
        ws.write(2, idx, col_name, fmt_h)
        max_len = max(
            [len(str(col_name))]
            + [len(str(x)) for x in df[col_name].astype(str).values[:500]]
        )
        ws.set_column(idx, idx, min(max(12, max_len + 2), 55))

    for idx, col_name in enumerate(df.columns):
        if col_name == STD_COLS["op"]:
            ws.set_column(idx, idx, None, fmt_int)
        elif col_name in (STD_COLS["importe"], STD_COLS["suma"]):
            ws.set_column(idx, idx, None, fmt_num)

    for r in range(1, len(df) + 1):
        if r % 2 == 0:
            ws.set_row(r + 2, None, fmt_band)

    if len(df) >= 1 and "info" not in df.columns:
        ws.add_table(2, 0, 2 + len(df), ncols - 1, {
            "name": "Tabla_ClientesPunto",
            "style": "Table Style Medium 6",
            "columns": [{"header": h} for h in df.columns],
        })

    # Resumen por gestor inline
    res_row = len(df) + 5
    ws.merge_range(res_row, 0, res_row, 3, "Resumen por Gestor", fmt_kpi_txt)
    res_row += 1
    for j, h in enumerate(["Gestor", "Nro. Operaciones", "Clientes Únicos", "Total Importe"]):
        ws.write(res_row, j, h, fmt_h)
    res_row += 1
    grand = 0.0
    for g_res in data["por_gestor"]:
        ws.write(res_row, 0, g_res["gestor"],           fmt_blk_txt)
        ws.write_number(res_row, 1, g_res["operaciones"],     fmt_int)
        ws.write_number(res_row, 2, g_res["clientes_unicos"],  fmt_int)
        ws.write_number(res_row, 3, g_res["total_importe"],    fmt_blk)
        grand += g_res["total_importe"]
        res_row += 1
    ws.write(res_row, 0, "TOTAL OFICINA",   fmt_kpi_txt)
    ws.write_number(res_row, 1, data["total_operaciones"],    fmt_kpi)
    ws.write_number(res_row, 2, data["total_clientes_unicos"], fmt_kpi)
    ws.write_number(res_row, 3, round(grand, 2),               fmt_kpi)

    writer.close()
    return buf.getvalue()


_MARKET_CURVA: dict[str, float] = {"S1": 4.0, "S2": 5.0, "S3": 6.5, "S4": 6.5}
_MARKET_CURVA_SUM: float = sum(_MARKET_CURVA.values())  # 22.0


def _week_of_month(dt: Any) -> str | None:
    """S1..S5 from day-of-month, same logic as automatizar_market."""
    try:
        if pd.isna(dt):
            return None
        return f"S{min(((int(dt.day) - 1) // 7) + 1, 5)}"
    except Exception:
        return None


def export_ventas_general(report: ReportData, config: dict | None = None) -> bytes:
    """Ventas general: todas las transacciones de todos los productos por gestor."""
    eff = config_for_report(config or {}, report)
    gestores_cfg = eff["gestores"]

    buf, writer = _writer()
    wb = writer.book

    color_header = "#1F4E79"
    color_band   = "#D9E1F2"
    color_block  = "#FCE4D6"
    color_title  = "#203864"

    fmt_h         = wb.add_format({"bold": True, "bg_color": color_header,
                                   "font_color": "white", "border": 1, "align": "center"})
    fmt_num       = wb.add_format({"num_format": "#,##0.00"})
    fmt_int       = wb.add_format({"num_format": "0"})
    fmt_band      = wb.add_format({"bg_color": color_band})
    fmt_block_txt = wb.add_format({"bg_color": color_block, "border": 1, "bold": True})
    fmt_block_num = wb.add_format({"bg_color": color_block, "border": 1, "bold": True,
                                   "num_format": "#,##0.00"})
    fmt_big_title = wb.add_format({"bold": True, "font_size": 16, "font_color": "white",
                                   "align": "left", "valign": "vcenter", "bg_color": color_title})
    fmt_subtitle  = wb.add_format({"italic": True, "font_color": "white",
                                   "align": "right", "valign": "vcenter", "bg_color": color_title})

    df_raw = only_valid_gestores(report.df).copy()
    export_cols = [c for c in [
        STD_COLS["op"], STD_COLS["fecha"], STD_COLS["socio"],
        STD_COLS["merc"], STD_COLS["cant"], STD_COLS["importe"], STD_COLS["suma"],
    ] if c in df_raw.columns]

    supervisor_rows: list[dict] = []

    for g in GESTORES_PERMITIDOS:
        g_cfg = {**GESTORES_CONFIG[g], **(gestores_cfg.get(g) or {})}
        sub = df_raw[df_raw["GestorDetectado"] == g].copy()
        if STD_COLS["fecha"] in sub.columns:
            sub = sub.sort_values([STD_COLS["fecha"]])

        to_write = sub[export_cols].copy()
        for col_name in to_write.columns:
            if col_name != STD_COLS["op"] and pd.api.types.is_numeric_dtype(to_write[col_name]):
                to_write[col_name] = to_write[col_name].round(2)

        sheet = g[:31]
        to_write.to_excel(writer, sheet_name=sheet, index=False)
        wsg = writer.sheets[sheet]
        wsg.freeze_panes(1, 0)
        _autosize(wsg, to_write, fmt_h)

        for idx, col_name in enumerate(to_write.columns):
            if col_name == STD_COLS["op"]:
                wsg.set_column(idx, idx, None, fmt_int)
            elif pd.api.types.is_numeric_dtype(to_write[col_name]):
                wsg.set_column(idx, idx, None, fmt_num)

        if len(to_write) > 0:
            _apply_bands(wsg, 1, len(to_write), fmt_band)
            wsg.add_table(0, 0, len(to_write), len(to_write.columns) - 1, {
                "name": f"TablaG_{g.replace(' ', '')[:18]}",
                "style": "Table Style Medium 2",
                "columns": [{"header": h} for h in to_write.columns],
            })

        total_importe = round(
            float(sub[STD_COLS["importe"]].sum()) if STD_COLS["importe"] in sub.columns else 0.0, 2
        )
        kpi_row = len(to_write) + 2
        wsg.write(kpi_row,     0, "VENTAS TOTALES", fmt_block_txt)
        wsg.write_number(kpi_row, 1, total_importe, fmt_block_num)
        wsg.write(kpi_row + 1, 0, "TRANSACCIONES", fmt_block_txt)
        wsg.write_number(kpi_row + 1, 1, len(sub), fmt_block_num)

        supervisor_rows.append({
            "Gestor": g,
            "Nombre": g_cfg["nombre"],
            "Sector": g_cfg["sector"],
            "Total Venta": total_importe,
            "Transacciones": len(sub),
        })

    # --- Hoja Supervisor ---
    sup_df = pd.DataFrame(supervisor_rows)
    sup_df.to_excel(writer, sheet_name="Supervisor", index=False, startrow=5)
    ws = writer.sheets["Supervisor"]
    ws.merge_range(0, 0, 1, 4, "Resumen General de Ventas — Todos los Productos", fmt_big_title)
    ws.merge_range(0, 5, 1, 7, f"Periodo: {report.date_min} → {report.date_max}", fmt_subtitle)
    ws.set_row(0, 28)
    ws.set_row(1, 20)
    ws.freeze_panes(6, 0)
    _autosize(ws, sup_df, fmt_h)
    if len(sup_df) > 0:
        _apply_bands(ws, 6, 5 + len(sup_df), fmt_band)
        ws.add_table(5, 0, 5 + len(sup_df), len(sup_df.columns) - 1, {
            "name": "Tabla_Supervisor_General",
            "style": "Table Style Medium 9",
            "columns": [{"header": h} for h in sup_df.columns],
        })
    total_row = 7 + len(sup_df) + 2
    ws.write(total_row, 0, "VENTAS TOTALES", fmt_block_txt)
    ws.write_number(total_row, 1, float(sup_df["Total Venta"].sum()), fmt_block_num)
    for c in range(6):
        ws.set_column(c, c, 18)
    ws.set_column(0, 0, 20)

    writer.close()
    return buf.getvalue()


def export_market(report: ReportData, config: dict | None = None) -> bytes:
    """Reporte Market: HL y CCC semanales por gestor vs cuota (estilo automatizar_market)."""
    eff = config_for_report(config or {}, report)
    gestores_cfg = eff["gestores"]
    agencia = "Camaguey"

    df = only_valid_gestores(report.df).copy()
    date_col  = STD_COLS["fecha"]
    socio_col = STD_COLS["socio"] if STD_COLS["socio"] in df.columns else None
    weeks = [f"S{i}" for i in range(1, 6)]

    hl_data:  dict[str, dict[str, float]] = {g: {w: 0.0 for w in weeks} for g in GESTORES_PERMITIDOS}
    ccc_data: dict[str, dict[str, int]]   = {g: {w: 0   for w in weeks} for g in GESTORES_PERMITIDOS}

    if date_col in df.columns:
        df_tmp = df[df["IsMalta"] | df["IsParranda"]].copy()
        df_tmp["_wk"] = df_tmp[date_col].apply(_week_of_month)
        hl_grp = (
            df_tmp.dropna(subset=["_wk"])
            .groupby(["GestorDetectado", "_wk"])["Hectolitros"]
            .sum()
        )
        for g in GESTORES_PERMITIDOS:
            for w in weeks:
                try:
                    hl_data[g][w] = round(float(hl_grp.loc[g, w]), 2)
                except KeyError:
                    pass

        if socio_col:
            df_tmp2 = df.copy()
            df_tmp2["_wk"] = df_tmp2[date_col].apply(_week_of_month)
            ccc_grp = (
                df_tmp2.dropna(subset=[socio_col, "_wk"])
                .groupby(["GestorDetectado", "_wk"])[socio_col]
                .nunique()
            )
            for g in GESTORES_PERMITIDOS:
                for w in weeks:
                    try:
                        ccc_data[g][w] = int(ccc_grp.loc[g, w])
                    except KeyError:
                        pass

    buf, writer = _writer()
    wb = writer.book
    ws = wb.add_worksheet("Reporte de Ventas")

    fmt_title  = wb.add_format({"bold": True, "font_size": 14, "font_color": "#0891B2"})
    fmt_cyan   = wb.add_format({"bold": True, "font_size": 9,  "font_color": "#0891B2"})
    fmt_head   = wb.add_format({
        "bold": True, "bg_color": "#1F2937", "font_color": "white",
        "border": 1, "align": "center", "valign": "vcenter", "font_size": 8, "text_wrap": True,
    })
    fmt_total  = wb.add_format({
        "bold": True, "bg_color": "#374151", "font_color": "white",
        "border": 1, "align": "center", "font_size": 8,
    })
    fmt_yellow = wb.add_format({
        "bold": True, "bg_color": "#FBBF24", "font_color": "#000000",
        "border": 1, "align": "center", "font_size": 8, "num_format": "0",
    })
    fmt_cell = [
        wb.add_format({"bg_color": "#E5E7EB", "border": 1, "align": "center", "font_size": 8}),
        wb.add_format({"bg_color": "#F9FAFB", "border": 1, "align": "center", "font_size": 8}),
    ]
    fmt_lbl = [
        wb.add_format({"bg_color": "#E5E7EB", "border": 1, "align": "left", "font_size": 8}),
        wb.add_format({"bg_color": "#F9FAFB", "border": 1, "align": "left", "font_size": 8}),
    ]
    fmt_red   = wb.add_format({"font_color": "#DC2626", "bold": True, "font_size": 10,
                                "align": "center", "border": 1})
    fmt_amber = wb.add_format({"font_color": "#D97706", "bold": True, "font_size": 10,
                                "align": "center", "border": 1})
    fmt_green = wb.add_format({"font_color": "#16A34A", "bold": True, "font_size": 10,
                                "align": "center", "border": 1})

    def _ind_fmt(pct: float) -> Any:
        if pct >= 100: return fmt_green
        if pct >= 80:  return fmt_amber
        return fmt_red

    headers = [
        "Indicador", "Agencia", "Vendedor", "Sector", "Cuota\nMes",
        "Cuota\nS1", "Real\nS1", "Cuota\nS2", "Real\nS2",
        "Cuota\nS3", "Real\nS3", "Cuota\nS4", "Real\nS4",
        "Cuota\nS5", "Real\nS5", "Cuota\nal día", "Real\nMes",
        "% S3", "●", "% Mes", "●",
    ]

    def write_section(start: int, indicador: str, data: Any, cuota_key: str) -> int:
        total_cuota = sum(
            float((gestores_cfg.get(g) or GESTORES_CONFIG[g]).get(cuota_key, 0))
            for g in GESTORES_PERMITIDOS
        )
        ws.write(start, 0, f"Target {indicador}: {total_cuota:.0f}", fmt_cyan)
        start += 2
        for c, h in enumerate(headers):
            ws.write(start, c, h, fmt_head)
        ws.set_row(start, 30)
        start += 1

        tot_cuota = 0.0
        tot_real  = 0.0
        tot_sem: dict[str, dict[str, float]] = {w: {"c": 0.0, "r": 0.0} for w in weeks}

        for idx, g in enumerate(GESTORES_PERMITIDOS):
            g_cfg = {**GESTORES_CONFIG[g], **(gestores_cfg.get(g) or {})}
            cuota = float(g_cfg.get(cuota_key, 0))
            w_cuotas = {w: round(cuota * _MARKET_CURVA.get(w, 0) / _MARKET_CURVA_SUM, 0) for w in weeks[:4]}
            w_cuotas["S5"] = 0.0
            real_mes = sum(float(v) for v in data[g].values())
            fc = fmt_cell[idx % 2]
            fl = fmt_lbl[idx % 2]
            row = start + idx
            ws.write(row, 0, indicador,       fc)
            ws.write(row, 1, agencia,         fl)
            ws.write(row, 2, g_cfg["nombre"], fl)
            ws.write(row, 3, g_cfg["sector"], fl)
            ws.write(row, 4, int(cuota),      fc)
            col = 5
            for w in weeks:
                ws.write(row, col,     int(w_cuotas[w]),     fc); col += 1
                ws.write(row, col,     int(data[g][w]),       fc); col += 1
                tot_sem[w]["c"] += w_cuotas[w]
                tot_sem[w]["r"] += data[g][w]
            ws.write(row, col, int(cuota),    fmt_yellow); col += 1
            ws.write(row, col, int(real_mes), fmt_yellow); col += 1
            pct_s3 = (data[g]["S3"] / w_cuotas["S3"] * 100) if w_cuotas.get("S3", 0) > 0 else 0.0
            ws.write(row, col, f"{pct_s3:.0f}%", fc); col += 1
            ws.write(row, col, "●", _ind_fmt(pct_s3)); col += 1
            pct_mes = (real_mes / cuota * 100) if cuota > 0 else 0.0
            ws.write(row, col, f"{pct_mes:.0f}%", fc); col += 1
            ws.write(row, col, "●", _ind_fmt(pct_mes))
            tot_cuota += cuota
            tot_real  += real_mes

        end = start + len(GESTORES_PERMITIDOS)
        ws.write(end, 0, "Total", fmt_total)
        for c in range(1, 4):
            ws.write(end, c, "", fmt_total)
        ws.write(end, 4, int(tot_cuota), fmt_total)
        col = 5
        for w in weeks:
            ws.write(end, col, int(tot_sem[w]["c"]), fmt_total); col += 1
            ws.write(end, col, int(tot_sem[w]["r"]), fmt_total); col += 1
        ws.write(end, col, int(tot_cuota), fmt_total); col += 1
        ws.write(end, col, int(tot_real),  fmt_total)
        return end + 3

    ws.write(0, 0, "Reporte de Ventas", fmt_title)
    ws.write(1, 0, "Supervisor:", fmt_cyan)
    ws.write(1, 1, agencia)
    ws.write(1, 2, f"Periodo: {report.date_min} → {report.date_max}")

    row = 3
    row = write_section(row, "HL",  hl_data,  "cuota_hl")
    row = write_section(row, "CCC", ccc_data, "cuota_ccc")

    ws.set_column(0, 0, 10)
    ws.set_column(1, 1, 12)
    ws.set_column(2, 2, 20)
    ws.set_column(3, 3, 10)
    for c in range(4, 21):
        ws.set_column(c, c, 8)
    ws.freeze_panes(1, 0)

    writer.close()
    return buf.getvalue()


def export_all(report: ReportData, config: dict | None = None) -> bytes:
    """Un único libro con todas las hojas principales."""
    buf, writer = _writer()
    wb = writer.book

    ventas    = compute_ventas(report, config)
    productos = compute_productos(report, config)
    ranking   = compute_ranking(report)
    punto     = compute_clientes_punto(report)

    fmt_h = wb.add_format({"bold": True, "bg_color": "#1F4E79",
                            "font_color": "white", "border": 1})

    def _dump(df: pd.DataFrame, sheet: str) -> None:
        df.to_excel(writer, sheet_name=sheet, index=False)
        ws = writer.sheets[sheet]
        for idx, col in enumerate(df.columns):
            ws.write(0, idx, col, fmt_h)
            ws.set_column(idx, idx, max(14, len(str(col)) + 2))

    _dump(pd.DataFrame(ventas["supervisor"]),          "Supervisor")
    _dump(pd.DataFrame(productos["cumplimiento"]),     "Cumplimiento")
    _dump(pd.DataFrame(productos["resumen_ces"]),      "CES")
    _dump(pd.DataFrame(productos["resumen_procovar"]), "PROCOVAR")
    _dump(pd.DataFrame(ranking["general"]),            "Ranking General")
    _dump(pd.DataFrame(ranking["semanal"]),            "Ranking Semanal")
    _dump(pd.DataFrame(ranking["diario"]),             "Ranking Diario")
    _dump(pd.DataFrame(punto["filas"]),                "Clientes Punto")
    _dump(pd.DataFrame(punto["por_gestor"]),           "Punto Resumen")

    writer.close()
    return buf.getvalue()

