"""Exportación a Excel con el formato y los colores de los reportes originales.

Cada función recibe (report, eff) y devuelve los bytes de un .xlsx. Todo es
dinámico: gestores, metas, factores y grupos salen de la config de la sucursal.
"""
from __future__ import annotations

import io

import pandas as pd

from core.constants import COLORS, GROUP_BG_COLORS
from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS
from services.market import WEEKS, compute_market
from services.productos import compute_productos
from services.ranking import compute_ranking
from services.ventas import compute_ventas
from services.clientes_analisis import compute_clientes_analisis


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
def _sheet_clientes(wb, f, sheet_name: str, titulo: str, blk: dict) -> None:
    """Escribe una hoja: clientes (filas, ranking por $) × SKU (columnas) en dólares."""
    ws = wb.add_worksheet(sheet_name[:31])
    skus = blk.get("skus", [])
    clientes = blk.get("clientes", [])
    has_gestor = bool(clientes and "gestor" in clientes[0])

    # columnas fijas + una por SKU
    fixed = ["#", "Cliente"] + (["Gestor"] if has_gestor else []) + ["Total $", "# SKUs"]
    ncols = len(fixed) + len(skus)
    ws.merge_range(0, 0, 0, max(1, ncols - 1), titulo, f["title"])
    ws.merge_range(1, 0, 1, max(1, ncols - 1),
                   f"{len(clientes)} clientes · {len(skus)} SKUs · total ${blk.get('total', 0):,.2f}", f["subtitle"])

    hdr_row = 3
    for j, h in enumerate(fixed):
        ws.write(hdr_row, j, h, f["header"])
    for k, s in enumerate(skus):
        ws.write(hdr_row, len(fixed) + k, s["sku"], f["header"])

    r = hdr_row + 1
    for i, c in enumerate(clientes, start=1):
        col = 0
        ws.write_number(r, col, i, f["int"]); col += 1
        ws.write(r, col, c["cliente"], f["label"]); col += 1
        if has_gestor:
            ws.write(r, col, c.get("gestor", ""), f["band"]); col += 1
        ws.write_number(r, col, c["total"], f["money_b"]); col += 1
        ws.write_number(r, col, c["num_skus"], f["int"]); col += 1
        montos = c.get("sku_montos", {})
        for k, s in enumerate(skus):
            v = montos.get(s["sku"])
            if v:
                ws.write_number(r, len(fixed) + k, v, f["money"])
            else:
                ws.write(r, len(fixed) + k, "", f["num"])
        r += 1

    # fila de totales por SKU
    tcol = 0
    ws.write(r, tcol, "", f["block_txt"]); tcol += 1
    ws.write(r, tcol, "TOTAL POR SKU", f["block_txt"]); tcol += 1
    if has_gestor:
        ws.write(r, tcol, "", f["block_txt"]); tcol += 1
    ws.write_number(r, tcol, blk.get("total", 0.0), f["money_b"]); tcol += 1
    ws.write(r, tcol, "", f["block_txt"]); tcol += 1
    for k, s in enumerate(skus):
        ws.write_number(r, len(fixed) + k, s["total"], f["block"])

    ws.set_column(0, 0, 5)
    ws.set_column(1, 1, 34)
    ws.set_column(2, len(fixed) - 1, 13)
    ws.set_column(len(fixed), max(len(fixed), ncols - 1), 16)
    ws.freeze_panes(hdr_row + 1, 2)


def export_clientes_analisis(report, eff: dict) -> bytes:
    data = compute_clientes_analisis(report, eff)
    bio, wb = _new_wb()
    f = _formats(wb)
    _sheet_clientes(wb, f, "Oficina", "Análisis de clientes — Oficina (total)", data["oficina"])
    for g in data["por_gestor"]:
        titulo = f"Clientes de {g['gestor']}"
        _sheet_clientes(wb, f, g["gestor"], titulo, g)
    wb.close()
    return bio.getvalue()


# ------------------------------------------------ PARRANDA/MALTA POR FACTURA
# Reproduce el script `automatizar_parranda.py`: una hoja por vendedor con CADA
# factura (No. Operación, Fecha, Cliente, Mercancía, Cantidad, Importe, Suma Total,
# Hectolitros) SOLO de Parranda/Malta, KPIs y conversión a Blisters/Pallets; más una
# hoja Supervisor con el resumen. Sirve para revisar factura por factura.
_UNITS_PP = {"330": 496, "500": 336, "1500": 110}  # unidades por pallet (fallback del script)
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


def export_parranda_facturas(report, eff: dict) -> bytes:
    bio, wb = _new_wb()
    f = _formats(wb)
    date_fmt = wb.add_format({"num_format": "dd/mm/yyyy", "border": 1})
    pct_ctr = wb.add_format({"num_format": "0%", "border": 1, "align": "center", "bold": True, "bg_color": COLORS["kpi"]})

    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    upp_cfg = {str(k): float(v) for k, v in (eff.get("units_per_pallet") or {}).items()}

    df = only_valid(enrich_for_sucursal(report, eff), keys)
    if not df.empty:
        df = df[df["IsMalta"] | df["IsParranda"]].copy()

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

        # Conversión a Blisters/Pallets por producto (como el script)
        cr = kr + 3
        ws.merge_range(cr, 0, cr, 4, "Conversión Cantidad → Blisters y Pallets", f["kpi_txt"])
        conv_hdr = ["Producto", "Tamaño", "Blisters", "Pallets", "Hectolitros"]
        for j, h in enumerate(conv_hdr):
            ws.write(cr + 1, j, h, f["header"])
        conv_rows = [("Malta", "330", M330), ("Parranda", "330", P330),
                     ("Parranda", "500", P500), ("Parranda", "1500", P1500)]
        for i, (prod, size, hlv) in enumerate(conv_rows):
            iscol = "IsMalta" if prod == "Malta" else "IsParranda"
            bl = 0.0
            if not sub.empty and cant in sub.columns:
                bl = round(float(sub.loc[sub[iscol] & (sub[size_col] == size), cant].sum()), 2)
            upp = upp_cfg.get(size, _UNITS_PP.get(size, 0))
            pal = round(bl / upp, 2) if upp else 0.0
            rr = cr + 2 + i
            ws.write(rr, 0, prod, f["band"]); ws.write(rr, 1, size, f["band"])
            ws.write_number(rr, 2, bl, f["num"]); ws.write_number(rr, 3, pal, f["num"])
            ws.write_number(rr, 4, hlv, f["num"])

        supervisor.append({"gestor": nombre, "venta": total_importe,
                           "M330": M330, "P330": P330, "P500": P500, "P1500": P1500, "hl": total_hl})

    # ---- Hoja Supervisor ----
    ws = wb.add_worksheet("Supervisor")
    ws.merge_range(0, 0, 1, 6, "Resumen de Ventas — Supervisor (Parranda / Malta)", f["title"])
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
