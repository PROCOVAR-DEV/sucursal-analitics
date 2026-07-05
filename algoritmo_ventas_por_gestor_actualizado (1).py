import pandas as pd
import re
import unicodedata
from datetime import datetime, date
from calendar import monthrange

# ==========================================================
# CONFIGURACION
# ==========================================================
INPUT_FILE = "RV JULIO 1-3.xls"
OUT_FILE = None  # Si queda en None, se genera automaticamente

GESTORES_PERMITIDOS = [
    "ALEXANDER",
    "DEYANIRA",
    "GEORLIS",
    "JEAN MICHEL",
    "ERNESTO",
    "ANDY",
    "MAYLEN",
]

ALIAS_MAP = {
    "ALELEXANDER": "ALEXANDER",
    "ALENXANDER": "ALEXANDER",
    "GEORLI": "GEORLIS",
    "MAYELIN": "MAYLEN",
    "JEANMICHEL": "JEAN MICHEL",
    "ALEXANDR": "ALEXANDER",
    "ALEX": "ALEXANDER",
    "ALEJANDER": "ALEXANDER",
    "ALEXANDER": "ALEXANDER",
    "DEYANIRA": "DEYANIRA",
    "DEIANIRA": "DEYANIRA",
    "DEYANNIRA": "DEYANIRA",
    "DEYANI": "DEYANIRA",
    "DEY": "DEYANIRA",
    "GEORLIS": "GEORLIS",
    "GEORLIS_": "GEORLIS",
    "GEORLIS.": "GEORLIS",
    "GEORLIS!!": "GEORLIS",
    "GEIRLIS": "GEORLIS",
    "JEANMIC": "JEAN MICHEL",
    "JEANMICHE": "JEAN MICHEL",
    "JEAN": "JEAN MICHEL",
    "JAEN": "JEAN MICHEL",
    "MICHEL": "JEAN MICHEL",
    "ERNESTO": "ERNESTO",
    "ERNESTO.": "ERNESTO",
    "ERNESTO_": "ERNESTO",
    "ANDY": "ANDY",
    "ANDY.": "ANDY",
    "ANDY_": "ANDY",
    "MAYELEN": "MAYLEN",
    "MAYLIN": "MAYLEN",
    "MAYLEN": "MAYLEN",
    "MAYLEN.": "MAYLEN",
    "MAYLEN_": "MAYLEN",
    "Maylen": "MAYLEN",
}

# Hectolitros por unidad/blister vendido segun tamano
SIZE_MULT = {"330": 0.02, "500": 0.03, "1500": 0.09}

# Factores de unidades por Pallet
UNITS_PER_PALLET = {
    ("MALTA", "330"): 496,
    ("PARRANDA", "330"): 496,
    ("MALTA", "500"): 336,
    ("PARRANDA", "500"): 336,
    ("MALTA", "1500"): 110,
    ("PARRANDA", "1500"): 110,
}

# Columnas finales del resumen, como la imagen
PRODUCT_COLS = ["P1500", "P500", "P330", "M1500", "M500", "M330"]

# METAS (referencia supervisor)
META_DINERO = 400000.0
META_HECTOLITROS = 1709.0

# Metas individuales por gestor en hectolitros
GESTOR_METAS = {
    "ALEXANDER": 235.0,
    "DEYANIRA": 321.0,
    "GEORLIS": 235.0,
    "JEAN MICHEL": 235.0,
    "ERNESTO": 224.0,
    "ANDY": 224.0,
    "MAYLEN": 235.0,
}

# Opcional: metas mensuales por gestor y producto.
# Si no tienes metas por producto, deja este diccionario vacio.
# El TOTAL siempre se toma de GESTOR_METAS.
METAS_GESTOR_PRODUCTO = {
    "ALEXANDER":   {"P1500": 91.08,  "P500": 20.16,  "P330": 39.68,  "M1500": 36.8775, "M330": 44.64},
    "DEYANIRA":    {"P1500": 118.8,  "P500": 27.216, "P330": 71.424, "M1500": 36.8775, "M330": 66.464},
    "GEORLIS":     {"P1500": 91.08,  "P500": 20.16,  "P330": 39.68,  "M1500": 36.8775, "M330": 44.64},
    "JEAN MICHEL": {"P1500": 91.08,  "P500": 20.16,  "P330": 39.68,  "M1500": 36.8775, "M330": 44.64},
    "ERNESTO":     {"P1500": 91.08,  "P500": 10.08,  "P330": 39.68,  "M1500": 36.8775, "M330": 44.64},
    "ANDY":        {"P1500": 91.08,  "P500": 10.08,  "P330": 39.68,  "M1500": 36.8775, "M330": 44.64},
    "MAYLEN":      {"P1500": 91.08,  "P500": 20.16,  "P330": 39.68,  "M1500": 36.8775, "M330": 44.64},
}

# Si tienes stock por gestor y producto, puedes ponerlo aqui.
# Si no lo tienes, el reporte coloca 0.
STOCK_GESTOR_PRODUCTO = {
    # "ALEXANDER": {"P1500": 0, "P500": 0, "P330": 0, "M1500": 0, "M330": 0},
}

MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

# ==========================================================
# UTILIDADES
# ==========================================================
def find_col(cols, subs):
    for c in cols:
        if isinstance(c, str) and all(s.lower() in c.lower() for s in subs):
            return c
    return None


def normalize_for_match(s: str) -> str:
    if s is None:
        return ""
    t = unicodedata.normalize("NFKD", str(s))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.upper()
    t = re.sub(r"\bTRANSFERENCIA\b", " ", t)
    t = re.sub(r"[^A-Z ]+", " ", t)
    return " ".join(t.split())


def extract_vendor_segment(obs_val: str) -> str:
    txt = str(obs_val) if obs_val else ""
    m = re.search(r'\bV[-:]\s*([^;]+)', txt, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return txt


def detect_gestor_from_obs(obs_val: str):
    txt = normalize_for_match(extract_vendor_segment(obs_val))
    for g in GESTORES_PERMITIDOS:
        if re.search(rf"(^|\b){re.escape(g)}(\b|$)", txt):
            return g
    txt_nospace = txt.replace(" ", "")
    for alias, gestor in ALIAS_MAP.items():
        alias_nospace = alias.replace(" ", "")
        if alias_nospace in txt_nospace:
            return gestor
    parts = txt.split()
    if "JEAN" in parts and "MICHEL" in parts:
        return "JEAN MICHEL"
    return None


def detect_size(text: str) -> str:
    t = str(text).upper()
    if "1,5" in t or "1.5" in t or "1500" in t:
        return "1500"
    if "500" in t:
        return "500"
    if "330" in t:
        return "330"
    return None


def detect_product_name(text: str) -> str:
    t = str(text).upper()
    if "PARRANDA" in t:
        return "PARRANDA"
    if "MALTA" in t or "GUAJIRA" in t:
        return "MALTA"
    return ""


def detect_product_code(row) -> str:
    prod = row.get("ProductoNombre", "")
    size = row.get("Hectolitros_SIZE")
    if not prod or not size:
        return None
    prefix = "P" if prod == "PARRANDA" else "M"
    return f"{prefix}{size}"


def smart_to_numeric(series):
    if pd.api.types.is_numeric_dtype(series):
        return series
    s = series.astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def pct(n, d):
    return 0 if d == 0 else n / d


def month_progress_factor(report_date: date) -> float:
    """
    Factor para meta acumulada del mes.
    Ejemplo: dia 15 de un mes de 30 dias = 15/30.
    Si prefieres contar dias laborales, cambia esta funcion.
    """
    days_in_month = monthrange(report_date.year, report_date.month)[1]
    return report_date.day / days_in_month


def calc_pallets(producto: str, size: str, cantidad: float) -> float:
    units = UNITS_PER_PALLET.get((producto, size), 0)
    if not units:
        return 0.0
    return float(cantidad or 0) / float(units)


def row_total(row_dict):
    return round(sum(float(row_dict.get(c, 0) or 0) for c in PRODUCT_COLS), 2)


def build_resumen(sub: pd.DataFrame, gestor: str, report_date: date, col_fecha: str):
    meta_producto = METAS_GESTOR_PRODUCTO.get(gestor, {})
    stock = STOCK_GESTOR_PRODUCTO.get(gestor, {})
    meta_total_gestor = float(GESTOR_METAS.get(gestor, 0))
    factor = month_progress_factor(report_date)
    days_in_month = monthrange(report_date.year, report_date.month)[1]

    month_mask = (
        (sub[col_fecha].dt.year == report_date.year)
        & (sub[col_fecha].dt.month == report_date.month)
        & (sub[col_fecha].dt.date <= report_date)
    )
    day_mask = sub[col_fecha].dt.date == report_date

    meta_total_row = {c: float(meta_producto.get(c, 0)) for c in PRODUCT_COLS}
    meta_acum_row = {c: round(meta_total_row[c] * factor, 2) for c in PRODUCT_COLS}

    venta_acum_row = {
        c: round(float(sub.loc[month_mask & (sub["ProductoCodigo"] == c), "Hectolitros"].sum()), 2)
        for c in PRODUCT_COLS
    }
    venta_dia_row = {
        c: round(float(sub.loc[day_mask & (sub["ProductoCodigo"] == c), "Hectolitros"].sum()), 2)
        for c in PRODUCT_COLS
    }
    stock_row = {c: float(stock.get(c, 0)) for c in PRODUCT_COLS}

    meta_total_total = meta_total_gestor
    meta_acum_total = round(meta_total_gestor * factor, 2)
    venta_acum_total = row_total(venta_acum_row)
    venta_dia_total = row_total(venta_dia_row)
    stock_total = row_total(stock_row)

    delta_acum_row = {c: round(venta_acum_row[c] - meta_acum_row[c], 2) for c in PRODUCT_COLS}
    delta_pct_row = {c: pct(delta_acum_row[c], meta_acum_row[c]) for c in PRODUCT_COLS}
    pct_total_row = {c: pct(venta_acum_row[c], meta_total_row[c]) for c in PRODUCT_COLS}

    rows = [
        ["Meta Total"] + [meta_total_row[c] for c in PRODUCT_COLS] + [meta_total_total],
        ["Meta Acumulada"] + [meta_acum_row[c] for c in PRODUCT_COLS] + [meta_acum_total],
        ["Venta Acumulada"] + [venta_acum_row[c] for c in PRODUCT_COLS] + [venta_acum_total],
        ["Ultimo Crecimiento"] + [venta_dia_row[c] for c in PRODUCT_COLS] + [venta_dia_total],
        ["Stock"] + [stock_row[c] for c in PRODUCT_COLS] + [stock_total],
        ["Delta Acumulada"] + [delta_acum_row[c] for c in PRODUCT_COLS] + [round(venta_acum_total - meta_acum_total, 2)],
        ["Delta Acumulada en %"] + [delta_pct_row[c] for c in PRODUCT_COLS] + [pct(venta_acum_total - meta_acum_total, meta_acum_total)],
        ["% del Total"] + [pct_total_row[c] for c in PRODUCT_COLS] + [pct(venta_acum_total, meta_total_total)],
    ]
    mensual = pd.DataFrame(rows, columns=["Indicador"] + PRODUCT_COLS + ["TOTAL"])

    meta_dia_row = {c: round(meta_total_row[c] / days_in_month, 2) for c in PRODUCT_COLS}
    meta_dia_total = round(meta_total_gestor / days_in_month, 2)
    delta_dia_row = {c: round(venta_dia_row[c] - meta_dia_row[c], 2) for c in PRODUCT_COLS}
    delta_dia_total = round(venta_dia_total - meta_dia_total, 2)
    delta_dia_pct_row = {c: pct(delta_dia_row[c], meta_dia_row[c]) for c in PRODUCT_COLS}
    pct_dia_row = {c: pct(venta_dia_row[c], meta_dia_row[c]) for c in PRODUCT_COLS}

    diario_rows = [
        ["Meta Dia"] + [meta_dia_row[c] for c in PRODUCT_COLS] + [meta_dia_total],
        ["Venta Dia"] + [venta_dia_row[c] for c in PRODUCT_COLS] + [venta_dia_total],
        ["Delta Dia"] + [delta_dia_row[c] for c in PRODUCT_COLS] + [delta_dia_total],
        ["Delta Dia en %"] + [delta_dia_pct_row[c] for c in PRODUCT_COLS] + [pct(delta_dia_total, meta_dia_total)],
        ["% Cumplimiento Dia"] + [pct_dia_row[c] for c in PRODUCT_COLS] + [pct(venta_dia_total, meta_dia_total)],
    ]
    diario = pd.DataFrame(diario_rows, columns=["Indicador"] + PRODUCT_COLS + ["TOTAL"])

    return mensual, diario


def build_totales_vendedor(sub: pd.DataFrame, gestor: str, mensual: pd.DataFrame, diario: pd.DataFrame, col_importe: str, col_cant: str):
    total_venta_dinero = round(float(sub[col_importe].sum()) if col_importe in sub.columns else 0.0, 2)
    total_hectolitros = round(float(sub["Hectolitros"].sum()), 2)
    meta_hectolitros = float(GESTOR_METAS.get(gestor, 0))
    delta_hectolitros = round(total_hectolitros - meta_hectolitros, 2)
    cumplimiento_hectolitros = pct(total_hectolitros, meta_hectolitros)
    total_blisters = round(float(sub[col_cant].sum()) if col_cant in sub.columns else 0.0, 2)
    total_pallets = round(float(sub["Pallets"].sum()), 2)
    comision_gestor = round(total_venta_dinero * 0.01, 2)

    venta_acum = float(mensual.loc[mensual["Indicador"] == "Venta Acumulada", "TOTAL"].iloc[0])
    meta_acum = float(mensual.loc[mensual["Indicador"] == "Meta Acumulada", "TOTAL"].iloc[0])
    venta_dia = float(diario.loc[diario["Indicador"] == "Venta Dia", "TOTAL"].iloc[0])
    meta_dia = float(diario.loc[diario["Indicador"] == "Meta Dia", "TOTAL"].iloc[0])

    return {
        "Gestor": gestor,
        "Total Venta Dinero": total_venta_dinero,
        "Comision Gestor 1%": comision_gestor,
        "Total Blisters": total_blisters,
        "Total Pallets": total_pallets,
        "Total Hectolitros": total_hectolitros,
        "Meta Hectolitros": meta_hectolitros,
        "Delta Hectolitros": delta_hectolitros,
        "% Cumpl. Hectolitros": cumplimiento_hectolitros,
        "Venta Acumulada": venta_acum,
        "Meta Acumulada": meta_acum,
        "Delta Acumulada": round(venta_acum - meta_acum, 2),
        "% Cumpl. Acum.": pct(venta_acum, meta_acum),
        "Venta Dia": venta_dia,
        "Meta Dia": meta_dia,
        "Delta Dia": round(venta_dia - meta_dia, 2),
        "% Cumpl. Dia": pct(venta_dia, meta_dia),
    }

# ==========================================================
# CARGA Y PREPROCESAMIENTO
# ==========================================================
raw = pd.read_excel(INPUT_FILE, header=None)
header_row_idx = None
for i in range(min(30, len(raw))):
    row_vals = raw.iloc[i].astype(str).str.strip().tolist()
    if any("No. de Operación" in str(v) for v in row_vals) and any("Fecha" in str(v) for v in row_vals):
        header_row_idx = i
        break
if header_row_idx is None:
    header_row_idx = 2

df = pd.read_excel(INPUT_FILE, header=header_row_idx)
df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
df.columns = [str(c).strip() for c in df.columns]
cols = df.columns

col_obs = find_col(cols, ["Nota"])
col_merc = find_col(cols, ["Mercancía"]) or find_col(cols, ["Mercancia"])
col_cant = find_col(cols, ["Cant"])
col_importe = find_col(cols, ["Importe"])
col_fecha = find_col(cols, ["Fecha"])
col_op = find_col(cols, ["No.", "Operación"]) or find_col(cols, ["Operación"])
col_sumat = find_col(cols, ["Suma", "Total"])

if not col_fecha:
    raise ValueError("No se encontro la columna de fecha.")
if not col_obs:
    raise ValueError("No se encontro la columna de Nota/Observacion para detectar gestor.")
if not col_merc:
    raise ValueError("No se encontro la columna de Mercancia.")
if not col_cant:
    raise ValueError("No se encontro la columna de Cantidad.")

if col_cant in df.columns:
    df[col_cant] = smart_to_numeric(df[col_cant])
if col_importe in df.columns:
    df[col_importe] = smart_to_numeric(df[col_importe]).round(2)
if col_sumat in df.columns:
    df[col_sumat] = smart_to_numeric(df[col_sumat]).round(2)
df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
if col_op in df.columns:
    df[col_op] = pd.to_numeric(df[col_op], errors="coerce").astype("Int64")

# Gestor, producto, tamano, hectolitros y pallets
df["__GESTOR__"] = df[col_obs].apply(detect_gestor_from_obs)
df = df[df["__GESTOR__"].isin(GESTORES_PERMITIDOS)].copy()
df["ProductoNombre"] = df[col_merc].apply(detect_product_name)
df["Hectolitros_SIZE"] = df[col_merc].apply(detect_size)
df["Hectolitros"] = (df[col_cant].fillna(0) * df["Hectolitros_SIZE"].map(SIZE_MULT).fillna(0)).round(2)
df["ProductoCodigo"] = df.apply(detect_product_code, axis=1)
df["Pallets"] = df.apply(lambda r: calc_pallets(r["ProductoNombre"], r["Hectolitros_SIZE"], r[col_cant]), axis=1).round(4)
df = df[df["ProductoCodigo"].isin(PRODUCT_COLS)].copy()

# Fecha de reporte: tomar la ultima fecha presente en el Excel.
# Si el Excel no contiene fechas válidas, usar la fecha de hoy.
dates_in_df = df[col_fecha].dropna()
if not dates_in_df.empty:
    try:
        report_date = dates_in_df.dt.date.max()
    except Exception:
        # En caso de que .dt no funcione (columna no datetime), convertir a datetime antes
        report_date = pd.to_datetime(dates_in_df, errors="coerce").dt.date.dropna()
        report_date = report_date.max() if not report_date.empty else datetime.now().date()
else:
    report_date = datetime.now().date()

# Para pruebas con un dia especifico, descomenta esta linea:
# report_date = date(2026, 5, 27)

if OUT_FILE is None:
    OUT_FILE = f"REPORTE-GESTORES-{report_date.strftime('%d-%m-%Y')}.xlsx"

# Columnas de detalle a exportar
if col_op in df.columns and col_sumat in df.columns:
    cols_list = list(df.columns)
    export_cols = cols_list[cols_list.index(col_op): cols_list.index(col_sumat) + 1]
else:
    export_cols = [c for c in df.columns if not c.startswith("__")]
for c in ["__GESTOR__", "ProductoNombre", "ProductoCodigo", "Hectolitros_SIZE", "Hectolitros", "Pallets"]:
    if c not in export_cols:
        export_cols.append(c)

# ==========================================================
# ESCRITURA DEL EXCEL
# ==========================================================
writer = pd.ExcelWriter(OUT_FILE, engine="xlsxwriter", engine_kwargs={"options": {"nan_inf_to_errors": True}})
wb = writer.book

fmt_title = wb.add_format({"bold": True, "font_size": 14, "font_color": "white", "bg_color": "#1F4E79", "align": "center", "border": 1})
fmt_header = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E79", "align": "center", "border": 1})
fmt_label = wb.add_format({"bold": True, "border": 1, "bg_color": "#D9EAF7"})
fmt_num = wb.add_format({"num_format": "0.00", "border": 1})
fmt_money = wb.add_format({"num_format": "$#,##0.00", "border": 1})
fmt_pct = wb.add_format({"num_format": "0%", "border": 1, "align": "center"})
fmt_green = wb.add_format({"num_format": "0.00", "border": 1, "bg_color": "#C6EFCE", "font_color": "#006100"})
fmt_red = wb.add_format({"num_format": "0.00", "border": 1, "bg_color": "#FFC7CE", "font_color": "#9C0006"})
fmt_green_pct = wb.add_format({"num_format": "0%", "border": 1, "bg_color": "#C6EFCE", "font_color": "#006100", "align": "center"})
fmt_red_pct = wb.add_format({"num_format": "0%", "border": 1, "bg_color": "#FFC7CE", "font_color": "#9C0006", "align": "center"})
fmt_yellow = wb.add_format({"num_format": "0.00", "border": 1, "bg_color": "#FFEB9C"})
fmt_info = wb.add_format({"italic": True, "font_color": "#666666"})
fmt_total = wb.add_format({"bold": True, "num_format": "0.00", "border": 1, "bg_color": "#E2EFDA"})
fmt_total_money = wb.add_format({"bold": True, "num_format": "$#,##0.00", "border": 1, "bg_color": "#E2EFDA"})

summary_rows = []

for gestor in GESTORES_PERMITIDOS:
    sub = df[df["__GESTOR__"] == gestor].copy().sort_values(by=[col_fecha, col_merc])
    mensual, diario = build_resumen(sub, gestor, report_date, col_fecha)
    totales = build_totales_vendedor(sub, gestor, mensual, diario, col_importe, col_cant)
    summary_rows.append(totales)

    sheet_name = gestor[:31]
    ws = wb.add_worksheet(sheet_name)
    writer.sheets[sheet_name] = ws

    ws.merge_range(0, 0, 0, 6, f"{gestor} - Resumen mensual", fmt_title)
    ws.write(1, 0, f"Fecha del informe: {report_date.strftime('%d-%m-%Y')}", fmt_info)

    mensual.to_excel(writer, sheet_name=sheet_name, index=False, startrow=3, startcol=0)
    for j, h in enumerate(mensual.columns):
        ws.write(3, j, h, fmt_header)

    for r in range(4, 4 + len(mensual)):
        label = mensual.iloc[r - 4, 0]
        ws.write(r, 0, label, fmt_label)
        for c in range(1, len(mensual.columns)):
            val = float(mensual.iloc[r - 4, c])
            if "%" in label:
                ws.write_number(r, c, val, fmt_green_pct if val >= 1 else fmt_red_pct)
            elif "Delta" in label:
                ws.write_number(r, c, val, fmt_green if val >= 0 else fmt_red)
            elif "Stock" in label:
                ws.write_number(r, c, val, fmt_yellow)
            else:
                ws.write_number(r, c, val, fmt_num)

    daily_start = 14
    ws.merge_range(daily_start, 0, daily_start, 6, f"{gestor} - Resumen diario", fmt_title)
    diario.to_excel(writer, sheet_name=sheet_name, index=False, startrow=daily_start + 2, startcol=0)
    for j, h in enumerate(diario.columns):
        ws.write(daily_start + 2, j, h, fmt_header)

    for r in range(daily_start + 3, daily_start + 3 + len(diario)):
        label = diario.iloc[r - (daily_start + 3), 0]
        ws.write(r, 0, label, fmt_label)
        for c in range(1, len(diario.columns)):
            val = float(diario.iloc[r - (daily_start + 3), c])
            if "%" in label:
                ws.write_number(r, c, val, fmt_green_pct if val >= 1 else fmt_red_pct)
            elif "Delta" in label:
                ws.write_number(r, c, val, fmt_green if val >= 0 else fmt_red)
            else:
                ws.write_number(r, c, val, fmt_num)

    # Bloque de totales finales por vendedor
    totals_start = daily_start + 10
    ws.merge_range(totals_start, 0, totals_start, 5, "Totales finales del vendedor", fmt_title)
    total_items = [
        ("Total Venta Dinero", totales["Total Venta Dinero"], fmt_total_money),
        ("Comisión Gestor 1%", totales["Comision Gestor 1%"], fmt_total_money),
        ("Total Blisters", totales["Total Blisters"], fmt_total),
        ("Total Pallets", totales["Total Pallets"], fmt_total),
        ("Total Hectolitros", totales["Total Hectolitros"], fmt_total),
        ("Meta Hectolitros", totales["Meta Hectolitros"], fmt_total),
        ("Delta Hectolitros", totales["Delta Hectolitros"], fmt_green if totales["Delta Hectolitros"] >= 0 else fmt_red),
        ("% Cumpl. Hectolitros", totales["% Cumpl. Hectolitros"], fmt_green_pct if totales["% Cumpl. Hectolitros"] >= 1 else fmt_red_pct),
    ]
    for i, (label, value, fmt) in enumerate(total_items, start=1):
        r = totals_start + i
        ws.merge_range(r, 0, r, 2, label, fmt_label)
        ws.merge_range(r, 3, r, 5, value, fmt)

    detail_start = totals_start + len(total_items) + 3
    ws.merge_range(detail_start, 0, detail_start, min(8, len(export_cols)-1), "Detalle de operaciones del gestor", fmt_title)
    detail = sub[export_cols].copy()
    detail.to_excel(writer, sheet_name=sheet_name, index=False, startrow=detail_start + 2, startcol=0)

    for j, h in enumerate(detail.columns):
        ws.write(detail_start + 2, j, h, fmt_header)

    if len(detail) > 0:
        ws.add_table(detail_start + 2, 0, detail_start + 2 + len(detail), len(detail.columns) - 1, {
            "name": f"Detalle_{gestor.replace(' ', '')[:18]}",
            "style": "Table Style Medium 2",
            "columns": [{"header": h} for h in detail.columns],
        })

    ws.set_column(0, 0, 24)
    ws.set_column(1, 6, 13)
    ws.set_column(7, max(7, len(export_cols)), 16)

# Hoja resumen general
summary = pd.DataFrame(summary_rows)

# Fila final total de todos los vendedores
total_row = {"Gestor": "TOTAL GENERAL"}
for col in summary.columns:
    if col == "Gestor":
        continue
    if col.startswith("%"):
        continue
    total_row[col] = round(float(summary[col].sum()), 2)

total_row["% Cumpl. Hectolitros"] = pct(total_row.get("Total Hectolitros", 0), total_row.get("Meta Hectolitros", 0))
total_row["% Cumpl. Acum."] = pct(total_row.get("Venta Acumulada", 0), total_row.get("Meta Acumulada", 0))
total_row["% Cumpl. Dia"] = pct(total_row.get("Venta Dia", 0), total_row.get("Meta Dia", 0))
summary = pd.concat([summary, pd.DataFrame([total_row])], ignore_index=True)

# Hectolitros del dia por SKU (global, todos los gestores)
day_mask_global = df[col_fecha].dt.date == report_date
day_by_sku = {
    c: round(float(df.loc[day_mask_global & (df["ProductoCodigo"] == c), "Hectolitros"].sum()), 2)
    for c in PRODUCT_COLS
}
day_sku_total = round(sum(day_by_sku.values()), 2)

summary.to_excel(writer, sheet_name="Resumen General", index=False, startrow=3)
ws = writer.sheets["Resumen General"]
ws.merge_range(0, 0, 0, len(summary.columns) - 1, f"Resumen general por gestor - {report_date.strftime('%d-%m-%Y')}", fmt_title)

for j, h in enumerate(summary.columns):
    ws.write(3, j, h, fmt_header)

for r in range(4, 4 + len(summary)):
    is_total_general = summary.iloc[r - 4, 0] == "TOTAL GENERAL"
    ws.write(r, 0, summary.iloc[r - 4, 0], fmt_label)
    for c in range(1, len(summary.columns)):
        val = float(summary.iloc[r - 4, c]) if pd.notna(summary.iloc[r - 4, c]) else 0.0
        col_name = summary.columns[c]
        if "%" in col_name:
            fmt = fmt_green_pct if val >= 1 else fmt_red_pct
        elif "Delta" in col_name:
            fmt = fmt_green if val >= 0 else fmt_red
        elif "Dinero" in col_name or "Comision" in col_name or "Comisión" in col_name:
            fmt = fmt_total_money if is_total_general else fmt_money
        else:
            fmt = fmt_total if is_total_general else fmt_num
        ws.write_number(r, c, val, fmt)

ws.add_table(3, 0, 3 + len(summary), len(summary.columns) - 1, {
    "name": "ResumenGeneralGestores",
    "style": "Table Style Medium 9",
    "columns": [{"header": h} for h in summary.columns],
})
ws.set_column(0, 0, 20)
ws.set_column(1, len(summary.columns) - 1, 17)
ws.freeze_panes(4, 0)

# Desglose del dia por SKU - Hectolitros
sku_section_start = 3 + len(summary) + 3
n_sku_cols = len(PRODUCT_COLS) + 1  # PRODUCT_COLS + TOTAL
ws.merge_range(
    sku_section_start, 0, sku_section_start, n_sku_cols,
    f"Desglose del día por SKU - Hectolitros  ({report_date.strftime('%d-%m-%Y')})",
    fmt_title,
)
ws.write(sku_section_start + 1, 0, "Indicador", fmt_header)
for j, h in enumerate(PRODUCT_COLS + ["TOTAL"]):
    ws.write(sku_section_start + 1, j + 1, h, fmt_header)
ws.write(sku_section_start + 2, 0, "Venta Día", fmt_label)
for j, c in enumerate(PRODUCT_COLS):
    ws.write_number(sku_section_start + 2, j + 1, day_by_sku[c], fmt_num)
ws.write_number(sku_section_start + 2, len(PRODUCT_COLS) + 1, day_sku_total, fmt_total)

writer.close()
print(f"[OK] Archivo generado: {OUT_FILE}")
