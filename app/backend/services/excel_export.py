"""Exportación a Excel con el formato y los colores de los reportes originales.

Cada función recibe (report, eff) y devuelve los bytes de un .xlsx. Todo es
dinámico: gestores, metas, factores y grupos salen de la config de la sucursal.
"""
from __future__ import annotations

import io

import pandas as pd

from core.constants import COLORS, GROUP_BG_COLORS, SIZE_MULT
from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.metas_gestor import metas_formato_de
from services.loader import STD_COLS
from services.market import WEEKS, compute_market
from services.productos import compute_productos
from services.ranking import compute_ranking
from services.ventas import compute_ventas
from services.clientes_analisis import compute_clientes_analisis
from services.gestor_sku import compute_gestor_sku


# ---------------------------------------------------------------- helpers
def _formats(wb):
    C = COLORS
    return {
        "title": wb.add_format({"bold": True, "font_size": 15, "font_color": "white",
                                "bg_color": C["title"], "align": "center", "valign": "vcenter", "border": 1}),
        "subtitle": wb.add_format({"italic": True, "font_color": "white", "bg_color": C["title"],
                                   "align": "center", "valign": "vcenter"}),
        "header": wb.add_format({"bold": True, "font_color": "white", "bg_color": C["header"],
                                 "align": "center", "valign": "vcenter", "border": 1, "text_wrap": True}),
        "label": wb.add_format({"bold": True, "border": 1, "bg_color": C["band"]}),
        "num": wb.add_format({"num_format": "0.00", "border": 1}),
        "int": wb.add_format({"num_format": "0", "border": 1}),
        "money": wb.add_format({"num_format": "$#,##0.00", "border": 1}),
        "money_b": wb.add_format({"bold": True, "num_format": "$#,##0.00", "border": 1, "bg_color": C["kpi"]}),
        # El mismo resalte que `money_b` pero SIN moneda: para los totales cuando
        # lo que se mide son empaques y no dólares.
        "int_b": wb.add_format({"bold": True, "num_format": "#,##0", "border": 1, "bg_color": C["kpi"]}),
        "pct": wb.add_format({"num_format": "0.0%", "border": 1, "align": "center"}),
        "band": wb.add_format({"bg_color": C["band"], "border": 1}),
        "kpi": wb.add_format({"bold": True, "num_format": "#,##0.00", "border": 1, "bg_color": C["kpi"]}),
        "kpi_txt": wb.add_format({"bold": True, "border": 1, "bg_color": C["kpi"], "align": "center"}),
        "block": wb.add_format({"bold": True, "num_format": "0.00", "border": 1, "bg_color": C["block"]}),
        "block_txt": wb.add_format({"bold": True, "border": 1, "bg_color": C["block"]}),
        "green": wb.add_format({"num_format": "0.00", "border": 1, "bg_color": C["green_bg"], "font_color": C["green_fg"]}),
        "red": wb.add_format({"num_format": "0.00", "border": 1, "bg_color": C["red_bg"], "font_color": C["red_fg"]}),
        "green_pct": wb.add_format({"num_format": "0.0%", "border": 1, "align": "center", "bg_color": C["green_bg"], "font_color": C["green_fg"]}),
        "red_pct": wb.add_format({"num_format": "0.0%", "border": 1, "align": "center", "bg_color": C["red_bg"], "font_color": C["red_fg"]}),
        "yellow": wb.add_format({"num_format": "0.0%", "border": 1, "align": "center", "bg_color": C["yellow_bg"], "font_color": C["yellow_fg"]}),
        "gold": wb.add_format({"bold": True, "border": 1, "bg_color": C["gold"], "align": "center"}),
        "silver": wb.add_format({"bold": True, "border": 1, "bg_color": C["silver"], "align": "center"}),
        "bronze": wb.add_format({"bold": True, "font_color": "white", "border": 1, "bg_color": C["bronze"], "align": "center"}),
        "money0": wb.add_format({"num_format": "#,##0", "border": 1, "align": "center"}),
    }


def _pct_fmt(f, ok: bool):
    return f["green_pct"] if ok else f["red_pct"]


def _new_wb():
    bio = io.BytesIO()
    writer = pd.ExcelWriter(bio, engine="xlsxwriter", engine_kwargs={"options": {"nan_inf_to_errors": True}})
    return bio, writer.book


# ---------------------------------------------------------------- VENTAS
def _sheet_supervisor(wb, f, data: dict):
    ws = wb.add_worksheet("Supervisor")
    groups = data["groups_order"]
    headers = ["Gestor", "Total Venta", "Comisión"] + [f"{g} $" for g in groups] + \
              ["M330", "M500", "M1500", "P330", "P500", "P1500", "Total HL"]
    ncol = len(headers)
    ws.merge_range(0, 0, 0, ncol - 1, f"Resumen de Ventas — {data.get('supervisor_nombre') or ''}", f["title"])
    ws.merge_range(1, 0, 1, ncol - 1, f"Periodo: {data['rango']}", f["subtitle"])

    ws.merge_range(3, 0, 3, 1, "VENTAS TOTALES", f["kpi_txt"])
    ws.write_number(3, 2, data["total_importe"], f["kpi"])
    ws.merge_range(3, 3, 3, 4, "COMISIÓN GESTORES", f["kpi_txt"])
    ws.write_number(3, 5, data["total_comision_gestores"], f["kpi"])
    ws.merge_range(3, 6, 3, 7, "COMISIÓN SUPERVISOR", f["kpi_txt"])
    ws.write_number(3, 8, data["comision_supervisor"], f["kpi"])

    hr = 5
    for j, h in enumerate(headers):
        ws.write(hr, j, h, f["header"])
    r = hr + 1
    for row in data["supervisor"]:
        ws.write(r, 0, row["gestor"], f["label"])
        ws.write_number(r, 1, row["total_venta"], f["money"])
        ws.write_number(r, 2, row["comision"], f["money"])
        c = 3
        for g in groups:
            ws.write_number(r, c, row["mix"].get(g, 0.0), f["money"]); c += 1
        for key in ("M330", "M500", "M1500", "P330", "P500", "P1500", "total_hectolitros"):
            ws.write_number(r, c, row[key], f["num"]); c += 1
        r += 1
    ws.write(r, 0, "TOTAL GENERAL", f["block_txt"])
    ws.write_number(r, 1, data["total_importe"], f["money_b"])
    ws.write_number(r, 2, data["total_comision_gestores"], f["money_b"])
    c = 3
    for g in groups:
        ws.write_number(r, c, round(sum(x["mix"].get(g, 0.0) for x in data["supervisor"]), 2), f["money_b"]); c += 1
    for key in ("M330", "M500", "M1500", "P330", "P500", "P1500", "total_hectolitros"):
        ws.write_number(r, c, round(sum(x[key] for x in data["supervisor"]), 2), f["block"]); c += 1

    mr = r + 2
    ws.merge_range(mr, 0, mr, 1, "META HECTOLITROS", f["block_txt"])
    ws.write_number(mr, 2, data["meta_hectolitros"], f["block"])
    ws.merge_range(mr, 3, mr, 4, "% CUMPL. HL", f["kpi_txt"])
    ws.write_number(mr, 5, data["cumplimiento_pct"] / 100.0, _pct_fmt(f, data["cumplimiento_pct"] >= 100))
    ws.merge_range(mr + 1, 0, mr + 1, 1, "META DINERO", f["block_txt"])
    ws.write_number(mr + 1, 2, data["meta_dinero"], f["block"])
    ws.merge_range(mr + 1, 3, mr + 1, 4, "% CUMPL. $", f["kpi_txt"])
    ws.write_number(mr + 1, 5, data["cumplimiento_dinero_pct"] / 100.0, _pct_fmt(f, data["cumplimiento_dinero_pct"] >= 100))

    ws.set_column(0, 0, 18)
    ws.set_column(1, ncol - 1, 13)
    ws.freeze_panes(hr + 1, 1)


def _sheet_gestor_ventas(wb, f, g: dict):
    ws = wb.add_worksheet(g["gestor"][:31])
    ws.merge_range(0, 0, 0, 5, f"{g['nombre']} ({g['gestor']}) — {g['sector']}", f["title"])
    ws.write(1, 0, "VENTAS", f["block_txt"]); ws.write_number(1, 1, g["total_importe"], f["money_b"])
    ws.write(2, 0, "COMISIÓN", f["block_txt"]); ws.write_number(2, 1, g["comision"], f["money_b"])
    ws.write(3, 0, "Total Hectolitros", f["block_txt"]); ws.write_number(3, 1, g["total_hectolitros"], f["block"])
    ws.write(3, 3, "% Cumpl.", f["kpi_txt"])
    ws.write_number(3, 4, g["cumplimiento_pct"] / 100.0, _pct_fmt(f, g["cumplimiento_pct"] >= 100))

    r = 5
    ws.merge_range(r, 0, r, 3, "Mix de Ventas por Grupo Comercial", f["kpi_txt"]); r += 1
    ws.write(r, 0, "Grupo", f["header"]); ws.write(r, 1, "Importe $", f["header"]); ws.write(r, 2, "%", f["header"])
    total_mix = sum(g["mix"].values()) or 1
    r += 1
    for grp, val in g["mix"].items():
        ws.write(r, 0, grp, f["label"]); ws.write_number(r, 1, val, f["money"])
        ws.write_number(r, 2, val / total_mix, f["pct"]); r += 1

    r += 1
    ws.merge_range(r, 0, r, 4, "Conversión Blisters / Pallets por Producto", f["kpi_txt"]); r += 1
    for j, h in enumerate(["Producto", "Tamaño", "Blisters", "Pallets", "Hectolitros"]):
        ws.write(r, j, h, f["header"])
    r += 1
    for row in g["conversion"]:
        ws.write(r, 0, row["producto"], f["label"]); ws.write(r, 1, row["tamano"], f["num"])
        ws.write_number(r, 2, row["blisters"], f["num"]); ws.write_number(r, 3, row["pallets"], f["num"])
        ws.write_number(r, 4, row["hectolitros"], f["num"]); r += 1
    ws.set_column(0, 0, 16); ws.set_column(1, 4, 13)


def export_ventas(report, eff: dict) -> bytes:
    data = compute_ventas(report, eff)
    bio, wb = _new_wb()
    f = _formats(wb)
    _sheet_supervisor(wb, f, data)
    for g in data["gestores"]:
        _sheet_gestor_ventas(wb, f, g)
    wb.close()
    return bio.getvalue()


# ---------------------------------------------------------------- PRODUCTOS
def export_productos(report, eff: dict) -> bytes:
    data = compute_productos(report, eff)
    bio, wb = _new_wb()
    f = _formats(wb)

    ws = wb.add_worksheet("Cumplimiento")
    ws.merge_range(0, 0, 0, 7, "Cumplimiento de Metas — Importaciones (CES)", f["title"])
    ws.write(1, 0, f"Días: {data['dias_laborales_transcurridos']} de {data['dias_laborales_totales']} "
                   f"(quedan {data['dias_laborales_restantes']})", f["subtitle"])
    hdr = ["Producto", "Meta Mes", "Venta Real", "% Cumpl.", "Debería ir", "Delta", "Prom. Diario", "Nec. x Día"]
    for j, h in enumerate(hdr):
        ws.write(3, j, h, f["header"])
    r = 4
    for row in data["cumplimiento"]:
        ok = row["delta"] >= 0
        ws.write(r, 0, row["producto"], f["label"])
        ws.write_number(r, 1, row["meta"], f["num"]); ws.write_number(r, 2, row["real"], f["num"])
        ws.write_number(r, 3, row["cumplimiento_pct"] / 100.0, _pct_fmt(f, row["cumplimiento_pct"] >= 100))
        ws.write_number(r, 4, row["deberia"], f["num"])
        ws.write_number(r, 5, row["delta"], f["green"] if ok else f["red"])
        ws.write_number(r, 6, row["prom_diario"], f["num"]); ws.write_number(r, 7, row["necesario_por_dia"], f["num"])
        r += 1
    ws.set_column(0, 0, 18); ws.set_column(1, 7, 13)

    ws2 = wb.add_worksheet("Resumen")
    r = 0
    for grp in data["groups_order"]:
        rows = data["resumen_por_grupo"].get(grp, [])
        if not rows:
            continue
        gfmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": GROUP_BG_COLORS.get(grp, COLORS["header"]),
                              "border": 1, "align": "center"})
        ws2.merge_range(r, 0, r, 2, f"Resumen Global — {grp}", gfmt); r += 1
        for j, h in enumerate(["Producto", "Total $", "Cantidad"]):
            ws2.write(r, j, h, gfmt)
        r += 1
        for row in rows:
            ws2.write(r, 0, row["producto"], f["label"])
            ws2.write_number(r, 1, float(row["total"]), f["money"])
            ws2.write_number(r, 2, float(row["cantidad"]), f["num"]); r += 1
        r += 2
    ws2.set_column(0, 0, 42); ws2.set_column(1, 2, 16)
    wb.close()
    return bio.getvalue()


# ---------------------------------------------------------------- MARKET
def export_market(report, eff: dict) -> bytes:
    data = compute_market(report, eff)
    bio, wb = _new_wb()
    f = _formats(wb)
    ws = wb.add_worksheet("Reporte de Ventas")
    sem = {"verde": f["green_pct"], "amarillo": f["yellow"], "rojo": f["red_pct"]}

    def block(title, filas, cuota_key, start):
        ncol = 4 + len(WEEKS) * 2 + 3
        ws.merge_range(start, 0, start, ncol - 1, f"{title} — {data.get('supervisor_nombre') or ''}", f["title"])
        r = start + 1
        head = ["Vendedor", "Agencia", "Sector", "Cuota Mes"]
        for w in WEEKS:
            head += [f"Cuota {w}", f"Real {w}"]
        head += ["Real Mes", "% Cumpl.", "●"]
        for j, h in enumerate(head):
            ws.write(r, j, h, f["header"])
        r += 1
        for row in filas:
            ws.write(r, 0, row["nombre"], f["label"]); ws.write(r, 1, row.get("agencia", ""), f["band"])
            ws.write(r, 2, row.get("sector", ""), f["band"])
            ws.write_number(r, 3, row[cuota_key], f["num"])
            c = 4
            for w in WEEKS:
                ws.write_number(r, c, row["cuota_semanal"][w], f["num"]); c += 1
                ws.write_number(r, c, row["real_semanal"][w], f["num"]); c += 1
            ws.write_number(r, c, row["real_mes"], f["num"]); c += 1
            ws.write_number(r, c, row["cumplimiento_pct"] / 100.0, _pct_fmt(f, row["cumplimiento_pct"] >= 100)); c += 1
            ws.write(r, c, "●", sem.get(row["semaforo"], f["num"]))
            r += 1
        return r + 1

    r = block("HECTOLITROS (HL)", data["hl"], "cuota_hl", 0)
    block("CAJAS COMERCIALES (CCC)", data["ccc"], "cuota_ccc", r + 1)
    ws.set_column(0, 0, 18); ws.set_column(1, 3 + len(WEEKS) * 2 + 3, 10)
    wb.close()
    return bio.getvalue()


# ---------------------------------------------------------------- RANKING
def export_ranking(report, eff: dict) -> bytes:
    data = compute_ranking(report, eff)
    bio, wb = _new_wb()
    f = _formats(wb)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    podium = {1: f["gold"], 2: f["silver"], 3: f["bronze"]}

    ws = wb.add_worksheet("Ranking General")
    ws.merge_range(0, 0, 1, 2, "RANKING DE VENTAS", f["title"])
    ws.merge_range(2, 0, 2, 2, f"Periodo: {data['rango']}", f["subtitle"])
    for j, h in enumerate(["Posición", "Vendedor", "Ventas (USD)"]):
        ws.write(4, j, h, f["header"])
    r = 5
    for row in data["general"]:
        pos = row["posicion"]; fmt = podium.get(pos, f["label"])
        ws.write(r, 0, f"{medals.get(pos,'')} {pos}".strip(), fmt)
        ws.write(r, 1, row["vendedor"], fmt)
        ws.write_number(r, 2, row["ventas"], f["money0"]); r += 1
    if data["general"]:
        ws.conditional_format(5, 2, r - 1, 2, {"type": "data_bar", "bar_color": "#4472C4"})
    ws.set_column(0, 0, 12); ws.set_column(1, 1, 22); ws.set_column(2, 2, 18)

    if data["semanal"]:
        ws2 = wb.add_worksheet("Ranking Semanal")
        ws2.merge_range(0, 0, 1, 2, "RANKING SEMANAL", f["title"])
        semdf = pd.DataFrame(data["semanal"])
        r = 3
        for semana in semdf["semana"].drop_duplicates():
            ws2.merge_range(r, 0, r, 2, f"Semana: {semana}", f["subtitle"]); r += 1
            for j, h in enumerate(["Posición", "Vendedor", "Ventas (USD)"]):
                ws2.write(r, j, h, f["header"])
            r += 1
            for _, row in semdf[semdf["semana"] == semana].sort_values("posicion").iterrows():
                pos = int(row["posicion"]); fmt = podium.get(pos, f["label"])
                ws2.write(r, 0, f"{medals.get(pos,'')} {pos}".strip(), fmt)
                ws2.write(r, 1, row["vendedor"], fmt)
                ws2.write_number(r, 2, float(row["ventas"]), f["money0"]); r += 1
            r += 1
        ws2.set_column(0, 0, 12); ws2.set_column(1, 1, 22); ws2.set_column(2, 2, 18)

    if data["diario"]:
        ws3 = wb.add_worksheet("Progreso Diario")
        ws3.merge_range(0, 0, 1, 3, "PROGRESO DIARIO (acumulado)", f["title"])
        for j, h in enumerate(["Fecha", "Posición", "Vendedor", "Acumulado (USD)"]):
            ws3.write(3, j, h, f["header"])
        r = 4
        diadf = pd.DataFrame(data["diario"])
        for fecha in diadf["fecha"].drop_duplicates():
            first = True
            for _, row in diadf[diadf["fecha"] == fecha].sort_values("posicion").iterrows():
                pos = int(row["posicion"]); fmt = podium.get(pos, f["label"])
                ws3.write(r, 0, fecha if first else "", f["band"]); first = False
                ws3.write(r, 1, f"{medals.get(pos,'')} {pos}".strip(), fmt)
                ws3.write(r, 2, row["vendedor"], fmt)
                ws3.write_number(r, 3, float(row["acumulado"]), f["money0"]); r += 1
            r += 1
        ws3.set_column(0, 0, 14); ws3.set_column(1, 1, 12); ws3.set_column(2, 2, 22); ws3.set_column(3, 3, 18)
    wb.close()
    return bio.getvalue()


# ---------------------------------------------------------------- ANÁLISIS DE CLIENTES
def _sheet_clientes(wb, f, sheet_name: str, titulo: str, blk: dict, metrica: str = "importe") -> None:
    """Una hoja: clientes (filas) × producto (columnas), en importe o en cantidad.

    El formato de celda va con la métrica. Escribir empaques con formato de
    dólares no es un detalle estético: el Excel sale con "$1,240.00" donde hay
    1.240 cajas, y quien lo abra —o lo reenvíe— saca la cuenta equivocada sin
    tener forma de notarlo.
    """
    es_cantidad = metrica == "cantidad"
    # "ambas" = las dos, una al lado de la otra. Lo pidió Claudia: con un informe
    # para cada una hay que cruzarlas a ojo, y el Excel tiene que salir con LO
    # MISMO que se está viendo en pantalla.
    es_ambas = metrica == "ambas"
    # En cantidad se usan los formatos enteros, que ya existen para los conteos.
    fmt_tot = f["int_b"] if (es_cantidad and "int_b" in f) else (f["int"] if es_cantidad else f["money_b"])
    fmt_celda = f["int"] if es_cantidad else f["money"]
    ws = wb.add_worksheet(sheet_name[:31])
    skus = blk.get("skus", [])
    clientes = blk.get("clientes", [])
    has_gestor = bool(clientes and "gestor" in clientes[0])

    # columnas fijas + una por SKU
    fixed = ["#", "Cliente"] + (["Gestor"] if has_gestor else []) + (
        ["Total $", "Total cantidad"] if es_ambas else ["Total cantidad" if es_cantidad else "Total $"]
    ) + ["# Productos"]
    # Con las dos métricas, cada SKU ocupa DOS columnas: el importe y, pegada, la
    # cantidad. La hoja sale ancha, pero es justo lo que se pidió — separarlas es
    # volver a tener dos informes que hay que cruzar a mano.
    por_sku = 2 if es_ambas else 1
    ncols = len(fixed) + len(skus) * por_sku
    ws.merge_range(0, 0, 0, max(1, ncols - 1), titulo, f["title"])
    ws.merge_range(1, 0, 1, max(1, ncols - 1),
                   f"{len(clientes)} clientes · {len(skus)} productos · total "
                   + (f"${blk.get('total', 0):,.2f} y {blk.get('total_cantidad', 0):,.0f}" if es_ambas
                      else f"{blk.get('total', 0):,.0f}" if es_cantidad
                      else f"${blk.get('total', 0):,.2f}"),
                   f["subtitle"])

    hdr_row = 3
    for j, h in enumerate(fixed):
        ws.write(hdr_row, j, h, f["header"])
    for k, s in enumerate(skus):
        base = len(fixed) + k * por_sku
        ws.write(hdr_row, base, s["sku"], f["header"])
        if es_ambas:
            ws.write(hdr_row, base + 1, f"{s['sku']} (cant)", f["header"])

    r = hdr_row + 1
    for i, c in enumerate(clientes, start=1):
        col = 0
        ws.write_number(r, col, i, f["int"]); col += 1
        ws.write(r, col, c["cliente"], f["label"]); col += 1
        if has_gestor:
            ws.write(r, col, c.get("gestor", ""), f["band"]); col += 1
        ws.write_number(r, col, c["total"], f["money_b"] if es_ambas else fmt_tot); col += 1
        if es_ambas:
            ws.write_number(r, col, c.get("total_cantidad", 0.0), f["int"]); col += 1
        ws.write_number(r, col, c["num_skus"], f["int"]); col += 1
        montos = c.get("sku_montos", {})
        cantidades = c.get("sku_cantidades", {})
        for k, s in enumerate(skus):
            base = len(fixed) + k * por_sku
            v = montos.get(s["sku"])
            if v:
                ws.write_number(r, base, v, f["money"] if es_ambas else fmt_celda)
            else:
                ws.write(r, base, "", f["num"])
            if es_ambas:
                q = cantidades.get(s["sku"])
                if q:
                    ws.write_number(r, base + 1, q, f["int"])
                else:
                    ws.write(r, base + 1, "", f["num"])
        r += 1

    # fila de totales por SKU
    tcol = 0
    ws.write(r, tcol, "", f["block_txt"]); tcol += 1
    ws.write(r, tcol, "TOTAL POR SKU", f["block_txt"]); tcol += 1
    if has_gestor:
        ws.write(r, tcol, "", f["block_txt"]); tcol += 1
    ws.write_number(r, tcol, blk.get("total", 0.0), f["money_b"]); tcol += 1
    if es_ambas:
        ws.write_number(r, tcol, blk.get("total_cantidad", 0.0), f["block"]); tcol += 1
    ws.write(r, tcol, "", f["block_txt"]); tcol += 1
    for k, s in enumerate(skus):
        base = len(fixed) + k * por_sku
        ws.write_number(r, base, s["total"], f["block"])
        if es_ambas:
            ws.write_number(r, base + 1, s.get("total_cantidad", 0.0), f["block"])

    ws.set_column(0, 0, 5)
    ws.set_column(1, 1, 34)
    ws.set_column(2, len(fixed) - 1, 13)
    ws.set_column(len(fixed), max(len(fixed), ncols - 1), 16)
    ws.freeze_panes(hdr_row + 1, 2)


#: Cómo se llama el MODELO ESTANDARIZADO, para que se llame igual en la pantalla, en
#: las hojas y en el nombre del archivo. No es el `clientes-analisis` de abajo.
NOMBRE_INFORME = "Modelo estandarizado de ventas por cliente"


def export_clientes_analisis(report, eff: dict, grupos: list[str] | None = None,
                             metrica: str = "importe", exclusivo: bool = False) -> bytes:
    """El Excel sale con LO MISMO que se está viendo en pantalla.

    Antes salía siempre el informe completo en importe, sin los filtros. Un
    archivo que no coincide con la pantalla de la que salió es peor que no
    tenerlo: se reenvía por correo, se discute con él delante, y nadie sabe que
    está mirando otra cosa.
    """
    data = compute_clientes_analisis(report, eff, grupos=grupos, metrica=metrica, exclusivo=exclusivo)
    real = data.get("metrica", "importe")
    # Los grupos elegidos van en el título: es lo único que dice, dentro del
    # archivo, que esto no es el total de todo.
    sufijo = f" — {', '.join(grupos)}" if grupos else ""
    # Que el titulo diga que es la cartera EXCLUSIVA: un Excel sin eso se confunde con
    # el normal del mismo grupo, y son dos poblaciones distintas.
    if data.get("exclusivo"):
        sufijo += " (sólo compran esto)"
    bio, wb = _new_wb()
    f = _formats(wb)
    # EL NOMBRE DEL INFORME, uno solo y en todas partes.
    #
    # Se llamaba «Análisis de clientes» en la pantalla, «Clientes de X» en cada hoja y
    # `clientes-analisis` en el fichero descargado: tres nombres para lo mismo, y
    # ninguno el que usa Procovar. Jose, 02/10/2026: «el nombre es modelo estandarizado
    # de ventas por cliente». Un informe que se reenvía por correo tiene que llamarse
    # igual en el correo, en la pestaña y dentro del archivo.
    # Éste NO es el «Modelo estandarizado»: es el detalle por SKU del catálogo, que
    # sirve para trabajar los datos. Tenerlos con el mismo nombre dejó dos descargas
    # casi iguales en Reportes y Jose no sabía cuál bajar. Cada uno con el suyo.
    _sheet_clientes(wb, f, "Oficina", f"Análisis de clientes — Oficina (total){sufijo}",
                    data["oficina"], real)
    for g in data["por_gestor"]:
        titulo = f"Clientes de {g['gestor']}{sufijo}"
        _sheet_clientes(wb, f, g["gestor"], titulo, g, real)
    wb.close()
    return bio.getvalue()


# ------------------------------------------------ PARRANDA/MALTA POR FACTURA
# Reproduce el script `automatizar_parranda.py`: una hoja por vendedor con CADA
# factura (No. Operación, Fecha, Cliente, Mercancía, Cantidad, Importe, Suma Total,
# Hectolitros) SOLO de Parranda/Malta, KPIs y conversión a Blisters/Pallets; más una
# hoja Supervisor con el resumen. Sirve para revisar factura por factura.
_UNITS_PP = {"330": 496, "500": 336, "1500": 110}  # unidades por pallet (fallback del script)


def _codigo_fmt(producto: str, size: str) -> str:
    """`Parranda` + `1500` -> `P1500`, que es la clave con la que se guardan las metas."""
    return f"{'P' if str(producto).upper().startswith('P') else 'M'}{size}"


def _metas_por_cantidad(ws, f, sub, fila: int, *, metas: dict, merc: str, cant: str) -> int:
    """Las metas de lo que se cuenta en unidades. Devuelve la fila libre siguiente.

    Arroz, papel, azúcar, vodka: no tienen hectolitros ni blísters, así que no caben en
    la tabla de conversión. Sus metas se ponen por vendedor en la calculadora
    (`metas_cantidad`) y hasta ahora no salían en el fichero de facturas, que es el que
    se le manda a cada uno.

    Se cruza por NOMBRE con `contains`, exactamente igual que «Sus metas por cantidad»
    de la pantalla de vendedores. Si aquí se cruzara de otra forma, el mismo producto
    daría dos cifras distintas según de dónde se mirara, y no habría manera de saber
    cuál creerse.

    La meta es la del MES ENTERO, sin prorratear por días: es la que se puso en la
    configuración y es la que el vendedor reconoce. El fichero de facturas sale de un
    rango de fechas cualquiera —una semana, un día— y prorratear aquí daría un número
    que no está escrito en ningún sitio.
    """
    limpias = {}
    for producto, v in (metas or {}).items():
        try:
            n = float(v or 0)
        except (TypeError, ValueError):
            continue
        # Un cero no es una meta: es una fila que sólo sirve para enseñar un 0 % que se
        # lee como «va fatal». Misma regla que `recortar_a_gestor`.
        if n > 0:
            limpias[str(producto)] = n
    if not limpias:
        return fila

    ws.merge_range(fila, 0, fila, 4, "Metas por Cantidad (productos sin hectolitros)", f["kpi_txt"])
    for j, h in enumerate(["Producto", "Meta (empaques)", "Vendido", "Falta", "Cumplimiento"]):
        ws.write(fila + 1, j, h, f["header"])

    r = fila + 2
    for producto in sorted(limpias):
        meta = round(limpias[producto], 2)
        real = 0.0
        if not sub.empty and merc in sub.columns and cant in sub.columns:
            casan = sub[merc].astype(str).str.contains(str(producto), case=False, na=False)
            real = round(float(pd.to_numeric(sub.loc[casan, cant], errors="coerce").fillna(0).sum()), 2)
        ws.write(r, 0, producto, f["band"])
        ws.write_number(r, 1, meta, f["int"])
        ws.write_number(r, 2, real, f["int"])
        ws.write_number(r, 3, round(max(0.0, meta - real), 2), f["int"])
        ws.write_number(r, 4, real / meta, f["pct"])
        r += 1
    return r + 1
# (columna en el df normalizado, encabezado, tipo de formato)
_INV_COLS = [
    ("__op__", "No. Operación", "int"),
    ("__fecha__", "Fecha", "date"),
    ("__socio__", "Cliente", "text"),
    ("__merc__", "Mercancía", "text"),
    ("__cant__", "Cantidad (empaques)", "int"),
    ("__importe__", "Importe", "money"),
    ("__suma__", "Suma Total", "money"),
    ("Hectolitros", "Hectolitros", "num"),
]


def _suma_col(d, col: str) -> float:
    """Suma una columna que puede no existir o venir con texto. 0.0 si no hay nada."""
    if col not in d.columns:
        return 0.0
    return float(pd.to_numeric(d[col], errors="coerce").fillna(0).sum())


def _agrupar_por_producto(sub, *, merc: str, cant: str, imp: str, con_grupo: bool) -> list[dict]:
    """Una fila por Mercancía, de mayor a menor importe."""
    if sub is None or sub.empty or merc not in sub.columns:
        return []
    d = sub.copy()
    nombres = d[merc].astype(str).str.strip()
    d["__prod__"] = nombres.mask(nombres.isin(["", "nan", "None", "NaN"]), "(sin nombre)")
    out = []
    for prod, sg in d.groupby("__prod__", dropna=False):
        out.append({
            "producto": str(prod),
            "grupo": (str(sg["GrupoComercial"].iloc[0])
                      if con_grupo and "GrupoComercial" in sg.columns else ""),
            "cantidad": round(_suma_col(sg, cant), 2),
            "importe": round(_suma_col(sg, imp), 2),
            "pallets": round(_suma_col(sg, "Pallets"), 2),
            "hl": round(_suma_col(sg, "Hectolitros"), 2),
        })
    out.sort(key=lambda x: x["importe"], reverse=True)
    return out


def _resumen_por_producto(ws, f, sub, fila: int, *, merc: str, cant: str, imp: str,
                          con_grupo: bool, con_hl: bool, con_pallets: bool = True,
                          titulo: str = "Desglose por Producto") -> int:
    """Tabla de pie con una fila por producto. Devuelve la fila libre siguiente.

    La tabla de arriba —«Conversión Cantidad → Blisters y Pallets»— solo sabe de Malta
    y Parranda en sus tres tamaños: en el fichero general, donde hay arroz, aceite o
    papel, saldría entera en cero. Ésta agrupa por la Mercancía tal como viene en la
    factura, así que vale para cualquier producto y además trae el importe, que la de
    arriba no tiene.

    El nombre del producto ocupa dos celdas unidas: las columnas de la tabla de
    facturas son estrechas y un nombre real no cabe en una sola.
    """
    # Una columna entera de ceros no informa de nada y hace dudar de si el informe
    # está roto: los pallets y los hectolitros solo salen si hay algo que contar.
    hdr = (["Producto"] + (["Grupo"] if con_grupo else [])
           + ["Cantidad (empaques)", "Importe"]
           + (["Pallets"] if con_pallets else []) + (["Hectolitros"] if con_hl else []))
    ancho = len(hdr) + 1  # +1 por la celda unida del nombre
    ws.merge_range(fila, 0, fila, ancho - 1, titulo, f["kpi_txt"])
    ws.merge_range(fila + 1, 0, fila + 1, 1, hdr[0], f["header"])
    for j, h in enumerate(hdr[1:], start=2):
        ws.write(fila + 1, j, h, f["header"])

    filas = _agrupar_por_producto(sub, merc=merc, cant=cant, imp=imp, con_grupo=con_grupo)
    r = fila + 2
    if not filas:
        ws.merge_range(r, 0, r, ancho - 1, "Sin ventas en el rango", f["band"])
        return r + 1

    for it in filas:
        ws.merge_range(r, 0, r, 1, it["producto"], f["band"])
        j = 2
        if con_grupo:
            ws.write(r, j, it["grupo"], f["band"]); j += 1
        ws.write_number(r, j, it["cantidad"], f["int"]); j += 1
        ws.write_number(r, j, it["importe"], f["money"]); j += 1
        if con_pallets:
            ws.write_number(r, j, it["pallets"], f["num"]); j += 1
        if con_hl:
            ws.write_number(r, j, it["hl"], f["num"])
        r += 1

    ws.merge_range(r, 0, r, 1, "TOTAL", f["block_txt"])
    j = 2
    if con_grupo:
        ws.write(r, j, "", f["block_txt"]); j += 1
    ws.write_number(r, j, round(sum(i["cantidad"] for i in filas), 2), f["int_b"]); j += 1
    ws.write_number(r, j, round(sum(i["importe"] for i in filas), 2), f["money_b"]); j += 1
    if con_pallets:
        ws.write_number(r, j, round(sum(i["pallets"] for i in filas), 2), f["block"]); j += 1
    if con_hl:
        ws.write_number(r, j, round(sum(i["hl"] for i in filas), 2), f["block"])
    return r + 1


def export_parranda_facturas(report, eff: dict, grupos: list[str] | None = None,
                             solo_cerveza: bool = True) -> bytes:
    """Una hoja por vendedor con CADA factura.

    `solo_cerveza` era lo único que había: el informe nació copiando
    `automatizar_parranda.py` y filtraba a Malta/Parranda, así que de todo lo demás que
    se vende —arroz, aceite, papel, baterías— no había ningún fichero por factura.

    Con `solo_cerveza=False` salen TODAS las líneas, y `grupos` acota a los grupos
    comerciales que se quieran. Así el mismo informe sirve para las tres preguntas: el
    general (sin grupo), el de un tipo concreto (un grupo), y el de cerveza de siempre.

    El bloque de hectolitros de abajo se queda como está y sigue mirando sólo Malta y
    Parranda: los hectolitros son de la cerveza. Un saco de arroz no tiene HL, y
    sumarlo ahí daría un total que no significa nada.
    """
    bio, wb = _new_wb()
    f = _formats(wb)
    date_fmt = wb.add_format({"num_format": "dd/mm/yyyy", "border": 1})
    pct_ctr = wb.add_format({"num_format": "0%", "border": 1, "align": "center", "bold": True, "bg_color": COLORS["kpi"]})

    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    upp_cfg = {str(k): float(v) for k, v in (eff.get("units_per_pallet") or {}).items()}
    # El mismo factor con el que el enriquecido saca los HL de cada línea. Hace falta
    # para el camino de vuelta: pasar una meta en hectolitros a blísters.
    mult_cfg = {str(k): float(v) for k, v in (eff.get("size_mult") or {}).items()}

    df = only_valid(enrich_for_sucursal(report, eff), keys)
    if not df.empty and solo_cerveza:
        df = df[df["IsMalta"] | df["IsParranda"]].copy()
    if not df.empty and grupos and "GrupoComercial" in df.columns:
        df = df[df["GrupoComercial"].astype(str).isin([str(g) for g in grupos])].copy()

    fec, merc, cant = STD_COLS["fecha"], STD_COLS["merc"], STD_COLS["cant"]
    imp, socio, op, suma, size_col = (
        STD_COLS["importe"], STD_COLS["socio"], STD_COLS["op"], STD_COLS["suma"], STD_COLS["size"],
    )
    # Mapa columna-real por clave lógica; solo las que existen en el df.
    real = {"__op__": op, "__fecha__": fec, "__socio__": socio, "__merc__": merc,
            "__cant__": cant, "__importe__": imp, "__suma__": suma, "Hectolitros": "Hectolitros"}
    inv = [(k, h, t) for (k, h, t) in _INV_COLS if real[k] in df.columns or k == "Hectolitros"]

    def hl(sub, is_col, size):
        if sub.empty or "Hectolitros" not in sub.columns:
            return 0.0
        return round(float(sub.loc[sub[is_col] & (sub[size_col] == size), "Hectolitros"].sum()), 2)

    meta_total = float(eff.get("meta_hectolitros_total", 0.0) or 0.0)
    supervisor = []

    # Se deciden UNA vez para todo el libro, no por hoja: si cada vendedor tuviera sus
    # columnas, dos hojas del mismo fichero no se podrían comparar de un vistazo.
    con_grupo = (not df.empty and "GrupoComercial" in df.columns
                 and df["GrupoComercial"].astype(str).nunique() > 1)
    con_hl = (not df.empty and "Hectolitros" in df.columns
              and float(pd.to_numeric(df["Hectolitros"], errors="coerce").fillna(0).abs().sum()) > 0)
    con_pallets = (not df.empty and "Pallets" in df.columns
                   and float(pd.to_numeric(df["Pallets"], errors="coerce").fillna(0).abs().sum()) > 0)

    for g in keys:
        nombre = str(gestores_cfg.get(g, {}).get("nombre", g))
        sub = df[df["GestorDetectado"] == g].copy() if not df.empty else df.copy()
        if not sub.empty and fec in sub.columns:
            by = [fec] + ([merc] if merc in sub.columns else [])
            sub = sub.sort_values(by=by)

        ws = wb.add_worksheet(nombre[:31])
        ws.freeze_panes(1, 0)
        for j, (k, h, t) in enumerate(inv):
            ws.write(0, j, h, f["header"])
            ws.set_column(j, j, 30 if t == "text" else 14)

        r = 1
        for _, row in sub.iterrows():
            for j, (k, h, t) in enumerate(inv):
                v = row.get(real[k])
                if t == "date":
                    if pd.notna(v):
                        ws.write_datetime(r, j, pd.Timestamp(v).to_pydatetime(), date_fmt)
                    else:
                        ws.write(r, j, "", f["num"])
                elif t == "int":
                    ws.write_number(r, j, float(v) if pd.notna(v) else 0.0, f["int"])
                elif t == "money":
                    ws.write_number(r, j, float(v) if pd.notna(v) else 0.0, f["money"])
                elif t == "num":
                    ws.write_number(r, j, float(v) if pd.notna(v) else 0.0, f["num"])
                else:
                    ws.write(r, j, "" if (v is None or pd.isna(v)) else str(v))
            r += 1

        total_importe = round(float(sub[imp].sum()) if imp in sub.columns and not sub.empty else 0.0, 2)
        M330, M500, M1500 = hl(sub, "IsMalta", "330"), hl(sub, "IsMalta", "500"), hl(sub, "IsMalta", "1500")
        P330, P500, P1500 = hl(sub, "IsParranda", "330"), hl(sub, "IsParranda", "500"), hl(sub, "IsParranda", "1500")
        total_hl = round(M330 + M500 + M1500 + P330 + P500 + P1500, 2)
        cuota = float(gestores_cfg.get(g, {}).get("cuota_hl", 0.0) or 0.0)

        kr = r + 1
        ws.write(kr, 0, "VENTAS", f["block_txt"]); ws.write_number(kr, 1, total_importe, f["money_b"])
        ws.write(kr + 1, 0, "Total Hectolitros", f["block_txt"]); ws.write_number(kr + 1, 1, total_hl, f["block"])
        ws.write(kr + 1, 2, "Cumplimiento", f["block_txt"])
        ws.write(kr + 1, 3, (total_hl / cuota) if cuota else 0.0, pct_ctr)

        # Conversión a Blisters/Pallets por producto, CON LA META AL LADO.
        #
        # Cada meta va pegada a su vecina y en su misma unidad: la de blísters junto a
        # Blísters y la de hectolitros junto a Hectolitros. Una sola columna de meta
        # obligaría a convertir de cabeza para saber si se llegó o no, que es justo lo
        # que esta tabla viene a evitar.
        #
        # Y son las metas DE ESTE VENDEDOR (`metas_formato_de`), no la suma de la
        # sucursal. Su hoja mide lo que vende él; ponerle enfrente el plan de los diez
        # es el 3 % de Santiago del 25/09/2026 otra vez.
        metas_fmt = metas_formato_de(gestores_cfg.get(g))
        cr = kr + 3
        ws.merge_range(cr, 0, cr, 6, "Conversión Cantidad → Blisters y Pallets", f["kpi_txt"])
        conv_hdr = ["Producto", "Tamaño", "Meta (blísters)", "Blisters", "Pallets",
                    "Meta (HL)", "Hectolitros"]
        for j, h in enumerate(conv_hdr):
            ws.write(cr + 1, j, h, f["header"])
        # LOS SEIS FORMATOS, no cuatro.
        #
        # Faltaban Malta 500 y Malta 1500, así que la tabla no cuadraba con el «Total
        # Hectolitros» de tres filas más arriba y nadie sabía por qué. En la hoja de
        # Gari del 26/09/2026: 105,10 aquí contra 153,34 allí — los 48,24 que faltaban
        # eran exactamente la Malta de 1500, que sí se había vendido y aquí no salía.
        # Con la columna de metas encima era peor: una meta puesta a M1500 no tendría
        # fila donde ponerse y desaparecería sin avisar.
        conv_rows = [("Malta", "330", M330), ("Malta", "500", M500), ("Malta", "1500", M1500),
                     ("Parranda", "330", P330), ("Parranda", "500", P500), ("Parranda", "1500", P1500)]
        for i, (prod, size, hlv) in enumerate(conv_rows):
            iscol = "IsMalta" if prod == "Malta" else "IsParranda"
            bl = 0.0
            if not sub.empty and cant in sub.columns:
                bl = round(float(sub.loc[sub[iscol] & (sub[size_col] == size), cant].sum()), 2)
            upp = upp_cfg.get(size, _UNITS_PP.get(size, 0))
            pal = round(bl / upp, 2) if upp else 0.0
            # La meta se guarda en hectolitros. A blísters se vuelve por el mismo factor
            # con el que se sacaron los HL de la venta (HL = blísters × size_mult), para
            # que las dos columnas de meta digan lo mismo contado de dos maneras.
            meta_hl = float(metas_fmt.get(_codigo_fmt(prod, size), 0.0))
            mult = mult_cfg.get(size, SIZE_MULT.get(size, 0.0))
            meta_bl = round(meta_hl / mult, 2) if mult else 0.0
            rr = cr + 2 + i
            ws.write(rr, 0, prod, f["band"]); ws.write(rr, 1, size, f["band"])
            ws.write_number(rr, 2, meta_bl, f["num"]); ws.write_number(rr, 3, bl, f["num"])
            ws.write_number(rr, 4, pal, f["num"])
            ws.write_number(rr, 5, meta_hl, f["num"]); ws.write_number(rr, 6, hlv, f["num"])

        # Las metas de lo que NO es cerveza, en su propia tabla: un saco de arroz no
        # tiene blísters ni hectolitros, y meterlo arriba sería escribir números en
        # columnas donde no aplican.
        sig = _metas_por_cantidad(ws, f, sub, cr + 2 + len(conv_rows) + 1,
                                  metas=(gestores_cfg.get(g) or {}).get("metas_cantidad") or {},
                                  merc=merc, cant=cant)

        # Desglose por producto, al pie. Lo pidió Santiago el 17/09/2026: la tabla de
        # conversión de arriba solo habla de cerveza y en el fichero general no dice nada.
        _resumen_por_producto(ws, f, sub, sig,
                              merc=merc, cant=cant, imp=imp,
                              con_grupo=con_grupo, con_hl=con_hl, con_pallets=con_pallets)

        supervisor.append({"gestor": nombre, "venta": total_importe,
                           "M330": M330, "P330": P330, "P500": P500, "P1500": P1500, "hl": total_hl})

    # ---- Hoja Supervisor ----
    ws = wb.add_worksheet("Supervisor")
    # El título dice lo que lleva dentro: el mismo libro sirve ahora para la cerveza
    # sola, para un grupo comercial o para todo lo que se vende.
    que = ("Parranda / Malta" if solo_cerveza
           else (" · ".join(str(g) for g in grupos) if grupos else "Todos los productos"))
    ws.merge_range(0, 0, 1, 6, f"Resumen de Ventas — Supervisor ({que})", f["title"])
    ws.merge_range(0, 7, 1, 8, f"Rango: {report.rango_str}", f["subtitle"])
    hdr = ["Gestor", "Total Venta", "M330", "P330", "P500", "P1500", "Total HL"]
    for j, h in enumerate(hdr):
        ws.write(3, j, h, f["header"])
        ws.set_column(j, j, 18 if j == 0 else 13)
    r = 4
    for s in supervisor:
        ws.write(r, 0, s["gestor"], f["band"])
        ws.write_number(r, 1, s["venta"], f["money"])
        for j, key in enumerate(["M330", "P330", "P500", "P1500", "hl"]):
            ws.write_number(r, 2 + j, s[key], f["num"])
        r += 1
    # Totales
    ws.write(r, 0, "TOTAL", f["block_txt"])
    ws.write_number(r, 1, round(sum(s["venta"] for s in supervisor), 2), f["money_b"])
    for j, key in enumerate(["M330", "P330", "P500", "P1500", "hl"]):
        ws.write_number(r, 2 + j, round(sum(s[key] for s in supervisor), 2), f["block"])
    # Meta y cumplimiento
    total_hl_all = round(sum(s["hl"] for s in supervisor), 2)
    ws.write(r + 2, 0, "META HECTOLITROS", f["block_txt"]); ws.write_number(r + 2, 1, meta_total, f["block"])
    ws.write(r + 3, 0, "% CUMPLIMIENTO", f["block_txt"])
    ws.write(r + 3, 1, (total_hl_all / meta_total) if meta_total else 0.0, pct_ctr)

    # El mismo desglose pero de toda la sucursal: es el que se mira para no tener que
    # ir sumando hoja por hoja.
    _resumen_por_producto(ws, f, df, r + 5, merc=merc, cant=cant, imp=imp,
                          con_grupo=con_grupo, con_hl=con_hl, con_pallets=con_pallets,
                          titulo="Desglose por Producto — Todos los gestores")

    wb.close()
    return bio.getvalue()


# ---------------------------------------------------------------- ALL
def export_all(report, eff: dict) -> bytes:
    """Consolidado: Supervisor + gestores + cumplimiento."""
    bio, wb = _new_wb()
    f = _formats(wb)
    v = compute_ventas(report, eff)
    _sheet_supervisor(wb, f, v)
    for g in v["gestores"]:
        _sheet_gestor_ventas(wb, f, g)
    p = compute_productos(report, eff)
    ws = wb.add_worksheet("Cumplimiento")
    ws.merge_range(0, 0, 0, 5, "Cumplimiento de Metas — CES", f["title"])
    for j, h in enumerate(["Producto", "Meta", "Real", "% Cumpl.", "Delta", "Estado"]):
        ws.write(2, j, h, f["header"])
    r = 3
    for row in p["cumplimiento"]:
        ok = row["delta"] >= 0
        ws.write(r, 0, row["producto"], f["label"]); ws.write_number(r, 1, row["meta"], f["num"])
        ws.write_number(r, 2, row["real"], f["num"])
        ws.write_number(r, 3, row["cumplimiento_pct"] / 100.0, _pct_fmt(f, row["cumplimiento_pct"] >= 100))
        ws.write_number(r, 4, row["delta"], f["green"] if ok else f["red"])
        ws.write(r, 5, "OK" if ok else "FALTA", f["green"] if ok else f["red"]); r += 1
    ws.set_column(0, 0, 18); ws.set_column(1, 5, 13)
    wb.close()
    return bio.getvalue()


def export_gestor_sku(report, eff: dict, grupos: list[str] | None = None,
                      metrica: str = "importe") -> bytes:
    """
    Cruce gestor x producto para trabajar los datos en Excel.

    Los PRODUCTOS van de cabecera y los gestores en las filas, que es como se
    lee: una fila por persona y una columna por lo que vende. Con totales por
    gestor (a la derecha) y por producto (abajo), para no tener que sumar a mano.

    Se congelan los encabezados y la primera columna: con muchos productos hay
    que desplazarse en horizontal y sin eso se pierde de vista de quien es cada
    fila.
    """
    data = compute_gestor_sku(report, eff, grupos=grupos, metrica=metrica)
    es_cantidad = data.get("metrica") == "cantidad"
    bio, wb = _new_wb()
    f = _formats(wb)

    productos = data["productos"]
    gestores = data["gestores"]
    # Importe de cada celda, indexado para no recorrer la matriz por cada casilla.
    celda = {
        (g["clave"], m["producto"]): m["por_gestor"].get(g["clave"], 0.0)
        for m in data["matriz"]
        for g in gestores
    }

    ws = wb.add_worksheet("Gestor x Producto")
    ancho = max(1, len(productos) + 1)
    # El título dice qué se está midiendo y de qué grupos. Es lo único que lo
    # aclara dentro del archivo, ya lejos de la pantalla que lo generó.
    ws.merge_range(0, 0, 1, ancho,
                   ("CANTIDAD" if es_cantidad else "IMPORTE") + " POR GESTOR Y PRODUCTO",
                   f["title"])
    sub = f"Periodo: {data['rango']}"
    if grupos:
        sub += f" · Grupos: {', '.join(grupos)}"
    ws.merge_range(2, 0, 2, ancho, sub, f["subtitle"])

    FILA_CAB = 4
    ws.write(FILA_CAB, 0, "Gestor", f["header"])
    for j, p in enumerate(productos, start=1):
        ws.write(FILA_CAB, j, p, f["header"])
    ws.write(FILA_CAB, len(productos) + 1, "TOTAL", f["header"])

    r = FILA_CAB + 1
    for g in gestores:
        ws.write(r, 0, g["nombre"], f["label"])
        for j, p in enumerate(productos, start=1):
            # Se escribe CERO donde no hay venta, no una casilla vacia. Excel trata
            # los huecos como texto ausente: rompen las sumas, las tablas
            # dinamicas y cualquier formula que cruce esta hoja. Con esto el
            # fichero sirve para trabajar los datos, que es para lo que se baja.
            ws.write_number(r, j, celda.get((g["clave"], p), 0.0), f["money0"])
        tot = next((t.get("medida", t["importe"]) for t in data["totales_gestor"] if t["gestor"] == g["clave"]), 0.0)
        ws.write_number(r, len(productos) + 1, tot, f["money0"])
        r += 1

    ws.write(r, 0, "TOTAL", f["header"])
    for j, p in enumerate(productos, start=1):
        tot_p = next((t.get("medida", t["importe"]) for t in data["totales_producto"] if t["producto"] == p), 0.0)
        ws.write_number(r, j, tot_p, f["money0"])
    ws.write_number(r, len(productos) + 1, data.get("total_medida", data["total_importe"]), f["money0"])

    ws.freeze_panes(FILA_CAB + 1, 1)
    ws.set_column(0, 0, 24)
    ws.set_column(1, len(productos) + 1, 16)

    # Hoja plana: una fila por (gestor, producto). Es la que sirve para tablas
    # dinamicas y para cruzar con otras fuentes.
    ws2 = wb.add_worksheet("Detalle")
    for j, h in enumerate(["Gestor", "Producto", "Importe", "Cantidad", "Hectolitros", "Operaciones"]):
        ws2.write(0, j, h, f["header"])
    for i, fila in enumerate(data["filas"], start=1):
        ws2.write(i, 0, fila["gestor_nombre"], f["label"])
        ws2.write(i, 1, fila["producto"], f["label"])
        ws2.write_number(i, 2, fila["importe"], f["money0"])
        ws2.write_number(i, 3, fila["cantidad"])
        ws2.write_number(i, 4, fila["hectolitros"])
        ws2.write_number(i, 5, fila["operaciones"])
    ws2.freeze_panes(1, 0)
    ws2.set_column(0, 0, 24)
    ws2.set_column(1, 1, 38)
    ws2.set_column(2, 5, 14)

    wb.close()
    return bio.getvalue()


# ====================================================== MODELO DE VENTAS POR CLIENTE
#
# La hoja que Procovar lleva a mano, reproducida: una de resumen con un VENDEDOR por
# fila y una por vendedor con un CLIENTE por fila, las dos con las mismas columnas y en
# el mismo orden, partidas en dos bloques —CCSA y PROCOVAR— cada uno con su subtotal.
#
# Es otra pregunta que la del `clientes-analisis` de siempre. Aquél saca una columna por
# SKU tal como viene del catálogo, que sirve para trabajar los datos; éste es el modelo
# con el que se habla de la sucursal: dos bloques, nombres cortos, y la misma rejilla
# todos los meses aunque un mes falte un producto.

#: Los cinco formatos de cerveza, con el nombre corto de la hoja y EN SU ORDEN.
#:
#: El bloque CCSA no va por producto sino por FORMATO: da igual que la cerveza se llame
#: «CERVEZA PARRANDA 1500 ML BLISTER 6U» o cambie de envase, la columna es `P 1.5`. Por
#: eso son cinco fijas y no salen de los datos — una rejilla que cambia de columnas cada
#: mes no se puede comparar con la del mes pasado, que es justo para lo que se usa.
_CCSA_FORMATOS = [
    ("P1500", "P 1.5"), ("P500", "P 500"), ("P330", "P 330"),
    ("M1500", "M 1.5"), ("M330", "M 330"),
]

#: Lo que se recorta del nombre del catálogo para dejar el nombre corto.
#:
#: `ARROZ PATEKO 1 KG PACA 10U` -> `Arroz Pateko`. Se corta en el primer trozo que es
#: una MEDIDA —un número, o una unidad— porque de ahí en adelante el nombre describe el
#: envase, no el producto, y el envase cambia sin que cambie lo que se vende.
_MEDIDAS = {
    "ML", "L", "LT", "LTS", "KG", "G", "GR", "M", "MM", "CM", "U", "UD", "UDS", "P",
    "PACA", "PACAS", "CAJA", "CAJAS", "BLISTER", "BLISTERS", "BARRA", "BARRAS",
    "SACO", "SACOS", "PAQUETE", "BOLSA", "DE", "X",
}

#: Y las dos abreviaturas que usa la hoja. No se inventan más: lo que no esté aquí sale
#: con su nombre entero en minúsculas de título, que es legible y no engaña.
_ABREVIA = {"SERVILLETA": "Serv.", "PAPEL HIGIENICO": "Papel", "REFRESCO": "Refr"}


def nombre_corto(nombre: str) -> str:
    """`PAPEL HIGIENICO MANATI 15 M PACA 12P DE 4U` -> `Papel Manatí`.

    Puro y exportado para poder probarlo: es lo único de este informe que TRANSFORMA un
    dato en vez de sumarlo, y un recorte que se pase de listo junta dos productos
    distintos en una columna sin que nadie lo note.

    La regla es conservadora a propósito: si no sabe recortar, devuelve el nombre entero.
    Una columna con un nombre largo se lee; dos arroces sumados en una, no se ve.
    """
    t = " ".join(str(nombre or "").split()).upper()
    if not t:
        return ""
    for largo, corto in _ABREVIA.items():
        if t.startswith(largo):
            t = corto.upper() + t[len(largo):]
            break
    palabras = t.split()
    utiles: list[str] = []
    for p in palabras:
        limpio = p.strip(".")
        # Un número, algo que empieza por número (`15`, `12P`, `100`) o una unidad: de
        # aquí en adelante es el envase.
        if limpio[:1].isdigit() or limpio in _MEDIDAS:
            break
        utiles.append(p)
    if not utiles:
        return str(nombre).title()
    corto = " ".join(utiles).title()
    # Las abreviaturas se dejan como están («Serv.», «Refr»), que `title()` las estropea.
    for abrev in _ABREVIA.values():
        if corto.upper().startswith(abrev.upper()):
            corto = abrev + corto[len(abrev):]
            break
    return corto


def _modelo_filas(df, imp, op):
    """Suma un trozo del reporte en la forma de una fila del modelo.

    Devuelve `(renglones, por_formato, por_producto)`, donde `por_producto` va indexado
    por **(grupo, nombre corto)**: el grupo forma parte de la llave porque las columnas
    se agrupan por él, y dos grupos podrían tener un producto que se llame parecido.

    Se usa igual para una fila de cliente y para una de vendedor, que es lo que garantiza
    que la hoja de resumen y la del vendedor digan lo mismo: la misma función con otro
    agrupador, no dos cuentas.
    """
    # RENGLONES, no facturas. Es lo que cuenta la hoja de Procovar: comprobado contra la
    # de Camagüey de agosto de 2026, los nueve vendedores cuadran al número (302, 225,
    # 266, 250, 67, 366, 217, 57). Las facturas darían 1.684 donde su hoja dice 2.148.
    renglones = int(len(df))
    por_fmt, por_prod = {}, {}
    if df.empty:
        return renglones, por_fmt, por_prod
    cerveza = df["IsMalta"] | df["IsParranda"]
    for cod, _ in _CCSA_FORMATOS:
        letra, size = cod[0], cod[1:]
        es = df["IsMalta"] if letra == "M" else df["IsParranda"]
        sel = cerveza & es & (df[STD_COLS["size"]].astype(str) == size)
        v = round(float(df.loc[sel, imp].sum()), 2)
        if v:
            por_fmt[cod] = v
    resto = df[~cerveza]
    if not resto.empty:
        llaves = list(zip(resto["GrupoComercial"].astype(str), resto[STD_COLS["merc"]].astype(str)))
        for (grupo, nombre), v in resto.groupby([[g for g, _ in llaves], [n for _, n in llaves]])[imp].sum().items():
            v = round(float(v), 2)
            if v:
                k = (str(grupo), nombre_corto(nombre))
                por_prod[k] = round(por_prod.get(k, 0.0) + v, 2)
    return renglones, por_fmt, por_prod


def export_modelo_ventas_cliente(report, eff: dict, grupos: list[str] | None = None) -> bytes:
    """El MODELO ESTANDARIZADO DE VENTAS POR CLIENTE, con la hoja que usa Procovar.

    Una «Resumen» con un VENDEDOR por fila y una hoja por vendedor con un CLIENTE por
    fila. Misma rejilla en todas, copiada del fichero de Camagüey de agosto de 2026:

        A  Cliente              (en el resumen, el vendedor)
        B  «Agosto 2026»        los RENGLONES del mes
        C  Ingresos totales
        D..H  Ingresos CCSA     P 1.5 · P 500 · P 330 · M 1.5 · M 330
        I  Total CCSA
        J..   Ingresos PROCOVAR un producto por columna
        ..    Total PROCO

    # Los productos son LOS QUE HAY, no una lista fija

    La plantilla de Procovar trae 26 columnas y el catálogo real de las diez sucursales
    tiene 80 productos. Copiarla tal cual dejaría fuera dinero de verdad —VODKA REGIO son
    39.114 en Santiago en agosto, y están además CERVEZA SANTA ISABEL, CONGELADOR ROYAL,
    GALLETAS TOCO, ESPAGUETTI ALLEGRA, EXHIBIDOR ICOOL…— y un informe del que desaparece
    una venta no sirve para cuadrar nada. Jose, 02/10/2026: «ponlo como lo tenemos
    nosotros para que no perdamos, pero los colores y la organización igual, y pon los
    productos que tengamos».

    Así que la estructura es la suya y las columnas salen de los datos. Van ordenadas por
    GRUPO y dentro del grupo por nombre, que es como está su hoja —los arroces juntos, los
    papeles juntos— y así la rejilla no se reordena de un mes a otro.

    **Un producto no puede salir dos veces**: `GrupoComercial` es una sola etiqueta por
    línea y la cerveza va por formato, así que cada venta cae en una columna y nada más.
    La garantía es estructural, no un filtro que alguien pueda quitar.

    # La invariante

    La fila de un vendedor en el Resumen es EXACTAMENTE el Grand Total de su hoja — lo
    dijo Jose mirando la suya— y se cumple porque salen de la misma función con otro
    agrupador. Hay una prueba que lo fija.

    `grupos` acota a los grupos comerciales que se quieran; vacío son todos.
    """
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    df = only_valid(enrich_for_sucursal(report, eff), keys)
    pedidos = [str(g) for g in (grupos or [])]
    if not df.empty and pedidos and "GrupoComercial" in df.columns:
        df = df[df["GrupoComercial"].astype(str).isin(pedidos)].copy()

    imp, merc, socio = STD_COLS["importe"], STD_COLS["merc"], STD_COLS["socio"]

    # Las columnas de PROCOVAR: por grupo (en el orden de la sucursal) y dentro del grupo
    # por nombre. Se guarda el nombre corto Y de qué grupo es, para poder ordenarlas.
    orden_grupos = [str(g) for g in (eff.get("groups_order") or [])]
    columnas: list[tuple[str, str]] = []          # (grupo, nombre corto)
    if not df.empty:
        resto = df[~(df["IsMalta"] | df["IsParranda"])]
        if not resto.empty:
            vistas = {(str(g), nombre_corto(n))
                      for g, n in zip(resto["GrupoComercial"].astype(str), resto[merc].astype(str))}
            def clave(x):
                g, n = x
                return (orden_grupos.index(g) if g in orden_grupos else len(orden_grupos), g, n)
            columnas = sorted(vistas, key=clave)

    hay_ccsa = (not pedidos) or any(str(g).upper() == "PARRANDA" for g in pedidos)

    bio, wb = _new_wb()
    periodo = getattr(report, "rango_str", "") or ""

    """
    LOS COLORES Y LA TIPOGRAFÍA SON LOS DE SU HOJA, no los del resto de informes.

    Sacados del fichero que mandó Jose —`MODELO ESTANDARIZADO DE VENTAS POR CLIENTES -
    Agosto - new.xlsx`, Camagüey— resolviendo los colores de tema con su tinte:

        bandas    «Mes:», «Ingresos CCSA», «Ingresos PROCOVAR»   #FFF2CA  (crema)
        totales   «Cliente», «Ingresos totales», los dos Total   #E3F2D9  (verde claro)
        producto  las columnas de cada SKU                       sin fondo, sólo borde

    Todo Arial 12 en las cabeceras. Y los números como los suyos: las columnas de total
    sin decimales y en rojo si bajan de cero; los productos con dos decimales.

    Va aquí y no en `_formats` a propósito: aquélla es la paleta de los demás informes
    —azules— y mezclarlas haría que este fichero dejara de parecerse al suyo en cuanto
    alguien tocara la otra. Este informe se imprime y se compara con el de ellos.
    """
    CREMA, VERDE = "#FFF2CA", "#E3F2D9"
    _base_cab = {"bold": True, "border": 1, "font_name": "Arial", "font_size": 12,
                 "align": "center", "valign": "vcenter", "text_wrap": True}
    f = {
        "banda": wb.add_format({**_base_cab, "bg_color": CREMA}),
        "tot_cab": wb.add_format({**_base_cab, "bg_color": VERDE}),
        "cab": wb.add_format({**_base_cab}),
        "txt": wb.add_format({"border": 1, "font_name": "Arial", "font_size": 10}),
        "num": wb.add_format({"border": 1, "font_name": "Arial", "font_size": 10,
                              "num_format": "#,##0.00;[Red]-#,##0.00"}),
        "int": wb.add_format({"border": 1, "font_name": "Arial", "font_size": 10,
                              "num_format": "#,##0;[Red]#,##0"}),
        "tot": wb.add_format({"border": 1, "font_name": "Arial", "font_size": 12,
                              "num_format": "#,##0;[Red]#,##0"}),
        # El Grand Total: lo mismo pero en negrita y con el verde, que es la fila que se
        # mira y en su hoja va resaltada.
        "gt_txt": wb.add_format({"bold": True, "border": 1, "font_name": "Arial",
                                 "font_size": 12, "bg_color": VERDE}),
        "gt_num": wb.add_format({"bold": True, "border": 1, "font_name": "Arial",
                                 "font_size": 12, "bg_color": VERDE,
                                 "num_format": "#,##0.00;[Red]-#,##0.00"}),
        "gt_int": wb.add_format({"bold": True, "border": 1, "font_name": "Arial",
                                 "font_size": 12, "bg_color": VERDE,
                                 "num_format": "#,##0;[Red]#,##0"}),
    }
    # La etiqueta de la columna de conteo es el MES EN PALABRAS, como en su hoja
    # («Agosto 2026»), no `2026-08`: la hoja se imprime y se pasa a gente que no lee
    # fechas de ordenador.
    _MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                 "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    etiqueta_mes = str(eff.get("_period") or "") or (periodo or "Mes")
    try:
        _y, _m = etiqueta_mes.split("-")[:2]
        etiqueta_mes = f"{_MESES_ES[int(_m) - 1]} {_y}"
    except (ValueError, IndexError):
        pass

    def hoja(nombre_hoja: str, etiqueta_primera: str, filas: list[dict]):
        ws = wb.add_worksheet(nombre_hoja[:31])
        BANDA, CAB = 1, 2                      # filas 2 y 3 del Excel, como su fichero
        c_ccsa = 3
        c_tot_ccsa = c_ccsa + (len(_CCSA_FORMATOS) if hay_ccsa else 0)
        c_proco = c_tot_ccsa + 1
        c_tot_proco = c_proco + len(columnas)
        ncols = c_tot_proco + 1

        # --- Fila de BANDAS (la crema), con las mismas combinaciones que su hoja.
        ws.write(BANDA, 0, "Mes:", f["banda"])
        ws.merge_range(BANDA, 1, CAB, 1, etiqueta_mes, f["banda"])
        ws.merge_range(BANDA, 2, CAB, 2, "Ingresos totales", f["tot_cab"])
        if hay_ccsa:
            ws.merge_range(BANDA, c_ccsa, BANDA, c_tot_ccsa - 1, "Ingresos CCSA", f["banda"])
        ws.merge_range(BANDA, c_tot_ccsa, CAB, c_tot_ccsa, "Total CCSA", f["tot_cab"])
        if columnas:
            ws.merge_range(BANDA, c_proco, BANDA, c_tot_proco - 1, "Ingresos PROCOVAR", f["banda"])
        ws.merge_range(BANDA, c_tot_proco, CAB, c_tot_proco, "Total PROCO", f["tot_cab"])

        # --- Fila de CABECERA.
        ws.write(CAB, 0, etiqueta_primera, f["tot_cab"])
        if hay_ccsa:
            for j, (_, corto) in enumerate(_CCSA_FORMATOS):
                ws.write(CAB, c_ccsa + j, corto, f["cab"])
        for j, (_g, p) in enumerate(columnas):
            ws.write(CAB, c_proco + j, p, f["cab"])

        def pinta(r, fila, f_txt, f_num, f_tot, f_int):
            ws.write(r, 0, fila["nombre"], f_txt)
            ws.write_number(r, 1, fila["renglones"], f_int)
            ws.write_number(r, 2, fila["total"], f_tot)
            if hay_ccsa:
                for j, (cod, _) in enumerate(_CCSA_FORMATOS):
                    ws.write_number(r, c_ccsa + j, fila["fmt"].get(cod, 0.0), f_num)
            ws.write_number(r, c_tot_ccsa, fila["total_ccsa"], f_tot)
            for j, k in enumerate(columnas):
                ws.write_number(r, c_proco + j, fila["prod"].get(k, 0.0), f_num)
            ws.write_number(r, c_tot_proco, fila["total_proco"], f_tot)

        r = CAB + 1
        for fila in filas:
            pinta(r, fila, f["txt"], f["num"], f["tot"], f["int"])
            r += 1

        # El GRAND TOTAL se SUMA de las filas de arriba y no se recalcula aparte: si se
        # recalculara podría no cuadrar con lo que hay encima y nadie sabría cuál creerse.
        def suma(g):
            return round(sum(g(x) for x in filas), 2)

        gt = {
            "nombre": "Grand Total",
            "renglones": int(sum(x["renglones"] for x in filas)),
            "total": suma(lambda x: x["total"]),
            "total_ccsa": suma(lambda x: x["total_ccsa"]),
            "total_proco": suma(lambda x: x["total_proco"]),
            "fmt": {c: suma(lambda x, cc=c: x["fmt"].get(cc, 0.0)) for c, _ in _CCSA_FORMATOS},
            "prod": {k: suma(lambda x, kk=k: x["prod"].get(kk, 0.0)) for k in columnas},
        }
        pinta(r, gt, f["gt_txt"], f["gt_num"], f["gt_int"], f["gt_int"])

        if filas:
            ws.autofilter(CAB, 0, r - 1, ncols - 1)
        ws.freeze_panes(CAB + 1, 1)
        ws.set_column(0, 0, 34)          # el ancho que tiene su hoja
        ws.set_column(1, max(1, ncols - 1), 14)
        ws.set_row(BANDA, 28)
        ws.set_row(CAB, 34)

    def fila_de(sub, nombre: str) -> dict:
        renglones, fmt, prod = _modelo_filas(sub, imp, STD_COLS["op"])
        t_ccsa = round(sum(fmt.values()), 2) if hay_ccsa else 0.0
        t_proco = round(sum(v for k, v in prod.items() if k in set(columnas)), 2)
        return {"nombre": nombre, "renglones": renglones, "fmt": fmt, "prod": prod,
                "total_ccsa": t_ccsa, "total_proco": t_proco,
                "total": round(t_ccsa + t_proco, 2)}

    por_vendedor = []
    for g in keys:
        sub = df[df["GestorDetectado"] == g] if not df.empty else df
        por_vendedor.append(fila_de(sub, str(gestores_cfg.get(g, {}).get("nombre", g))))
    hoja("Resumen", "Vendedor", por_vendedor)

    for g in keys:
        sub = df[df["GestorDetectado"] == g] if not df.empty else df
        clientes = []
        if not sub.empty and socio in sub.columns:
            for cli, grp in sub.groupby(sub[socio].astype(str)):
                clientes.append(fila_de(grp, cli))
            clientes.sort(key=lambda x: -x["total"])
        hoja(str(gestores_cfg.get(g, {}).get("nombre", g)), "Cliente", clientes)

    wb.close()
    return bio.getvalue()
