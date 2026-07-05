import pandas as pd
import re, unicodedata
from datetime import datetime

# =========================
# CONFIGURACION
# =========================
INPUT_FILE = "RV JULIO 1-3.xls"  # Asegúrate que este sea tu archivo de entrada
GESTORES_PERMITIDOS = [
    "ALEXANDER",
    "DEYANIRA",
    "GEORLIS",
    "JEAN MICHEL",
    "ERNESTO",
    "ANDY",
    "MAYLEN",
]

# Aliases comunes
ALIAS_MAP = {
    "ALELEXANDER": "ALEXANDER", "ALENXANDER": "ALEXANDER", "GEORLI": "GEORLIS",
    "MAYELIN": "MAYLEN", "JEANMICHEL": "JEAN MICHEL", "ALEXANDR": "ALEXANDER",
    "ALEX": "ALEXANDER", "ALEJANDER": "ALEXANDER", "ALEXANDER": "ALEXANDER",
    "DEYANIRA": "DEYANIRA", "DEIANIRA": "DEYANIRA", "DEYANNIRA": "DEYANIRA",
    "DEYANI": "DEYANIRA", "DEY": "DEYANIRA", "GEORLIS": "GEORLIS",
    "GEORLIS_": "GEORLIS", "GEORLIS.": "GEORLIS", "GEORLIS!!": "GEORLIS",
    "GEIRLIS": "GEORLIS", "JEANMIC": "JEAN MICHEL", "JEANMICHE": "JEAN MICHEL",
    "JEAN": "JEAN MICHEL", "JAEN": "JEAN MICHEL", "MICHEL": "JEAN MICHEL",
    "ERNESTO": "ERNESTO", "ANDY": "ANDY", "ANDY.": "ANDY", "ANDY_": "ANDY",
    "MAYELEN": "MAYLEN",
    "MAYLIN": "MAYLEN", "MAYLEN": "MAYLEN", "MAYLEN.": "MAYLEN",
    "MAYLEN_": "MAYLEN", "Maylen": "MAYLEN",
}

# Multiplicadores Hectolitros
SIZE_MULT = {"330": 0.02, "500": 0.03, "1500": 0.09}

# Unidades por Pallet
UNITS_PER_PALLET = {
    ("MALTA", "330"): 496, ("PARRANDA", "330"): 496,
    ("MALTA", "500"): 336, ("PARRANDA", "500"): 336,
    ("MALTA", "1500"): 110, ("PARRANDA", "1500"): 110,
}

# METAS
META_HECTOLITROS = 1709.0
GESTOR_METAS = {
    "ALEXANDER": 235,
    "DEYANIRA": 321,
    "GEORLIS": 235,
    "JEAN MICHEL": 235,
    "ERNESTO": 224,
    "ANDY": 224,
    "MAYLEN": 235,
}

MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

# =========================
# Utilidades
# =========================
def find_col(cols, subs):
    for c in cols:
        if isinstance(c, str) and all(s.lower() in c.lower() for s in subs):
            return c
    return None

def normalize_for_match(s: str) -> str:
    if s is None: return ""
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
        if alias.replace(" ", "") in txt_nospace:
            return gestor
    parts = txt.split()
    if "JEAN" in parts and "MICHEL" in parts:
        return "JEAN MICHEL"
    return None

def detect_size(text: str) -> str:
    t = str(text).upper()
    if "1,5" in t or "1.5" in t or "1500" in t: return "1500"
    if "500" in t: return "500"
    if "330" in t: return "330"
    return None

def is_malta(text: str) -> bool:
    t = str(text).upper()
    return "MALTA" in t and "GUAJIRA" in t

def is_parranda(text: str) -> bool:
    t = str(text).upper()
    return "PARRANDA" in t

def smart_to_numeric(series):
    if pd.api.types.is_numeric_dtype(series): return series
    s = series.astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")

def sort_df(d: pd.DataFrame, col_fecha: str, col_merc: str) -> pd.DataFrame:
    if col_fecha in d.columns:
        by = [col_fecha] + ([col_merc] if col_merc in d.columns else [])
        return d.sort_values(by=by, ascending=True)
    return d

def sum_hectolitros(sub: pd.DataFrame, mask: pd.Series, size: str) -> float:
    return round(float(sub.loc[mask & (sub["Hectolitros_SIZE"] == size), "Hectolitros"].sum()), 2)

# =========================
# Carga y preprocesamiento
# =========================
raw = pd.read_excel(INPUT_FILE, header=None)
header_row_idx = None
for i in range(min(30, len(raw))):
    row_vals = raw.iloc[i].astype(str).str.strip().tolist()
    if any("No. de Operación" in str(v) for v in row_vals) and any("Fecha" in str(v) for v in row_vals):
        header_row_idx = i
        break
if header_row_idx is None: header_row_idx = 2

df = pd.read_excel(INPUT_FILE, header=header_row_idx)
df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
df.columns = [str(c).strip() for c in df.columns]
cols = df.columns

col_obs = find_col(cols, ["Nota"]) or find_col(cols, ["Nota"])
col_merc = find_col(cols, ["Mercancía"]) or find_col(cols, ["Mercancia"])
col_cant = find_col(cols, ["Cant"])
col_importe = find_col(cols, ["Importe"])
col_fecha = find_col(cols, ["Fecha"])
col_op = find_col(cols, ["No.", "Operación"]) or find_col(cols, ["Operación"])
col_sumat = find_col(cols, ["Suma", "Total"])

if col_cant in df.columns: df[col_cant] = smart_to_numeric(df[col_cant])
if col_importe in df.columns: df[col_importe] = smart_to_numeric(df[col_importe]).round(2)
if col_sumat in df.columns: df[col_sumat] = smart_to_numeric(df[col_sumat]).round(2)
if col_fecha in df.columns: df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
if col_op in df.columns: df[col_op] = pd.to_numeric(df[col_op], errors="coerce").astype("Int64")

df["__GESTOR__"] = df[col_obs].apply(detect_gestor_from_obs) if col_obs in df.columns else None
df = df[df["__GESTOR__"].isin(GESTORES_PERMITIDOS)].copy()

df["Hectolitros_SIZE"] = df[col_merc].apply(detect_size) if col_merc in df.columns else None
df["__IS_MALTA__"] = df[col_merc].apply(is_malta) if col_merc in df.columns else False
df["__IS_PARRANDA__"] = df[col_merc].apply(is_parranda) if col_merc in df.columns else False

# === FILTRO CRITICO: SOLO PARRANDA O MALTA ===
df = df[df["__IS_MALTA__"] | df["__IS_PARRANDA__"]].copy()

mult_series = df["Hectolitros_SIZE"].map(SIZE_MULT).fillna(0)
if col_cant in df.columns:
    df["Hectolitros"] = (df[col_cant].fillna(0) * mult_series).round(2)
else:
    df["Hectolitros"] = 0.00

if col_op in df.columns and col_sumat in df.columns:
    cols_list = list(df.columns)
    start_idx = cols_list.index(col_op)
    end_idx = cols_list.index(col_sumat)
    export_cols = cols_list[start_idx : end_idx + 1]
else:
    export_cols = list(df.columns)
aux_cols = ["__GESTOR__", "Hectolitros_SIZE", "__IS_MALTA__", "__IS_PARRANDA__", col_obs]
export_cols = [c for c in export_cols if c not in aux_cols]
if "Hectolitros" not in export_cols: export_cols.append("Hectolitros")

# =========================
# NOMBRE DEL ARCHIVO DE SALIDA
# =========================
if col_fecha in df.columns and not df[col_fecha].isna().all():
    fmin, fmax = df[col_fecha].min(), df[col_fecha].max()
    # Genera nombre tipo: "Venta Vendedores 01-07 DICIEMBRE.xlsx"
    OUT_FILE = f"Venta Vendedores {fmin.day:02d}-{fmax.day:02d} {MESES_ES.get(fmin.month,'MES')}.xlsx"
    rango_fechas_str = f"{fmin.strftime('%d-%m-%Y')} a {fmax.strftime('%d-%m-%Y')}"
else:
    # Si no detecta fechas, pone la fecha de hoy
    OUT_FILE = f"Venta Vendedores_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    rango_fechas_str = "Rango no disponible"

# =========================
# Escritura Excel
# =========================
writer = pd.ExcelWriter(OUT_FILE, engine="xlsxwriter", engine_kwargs={"options": {"nan_inf_to_errors": True}})
wb = writer.book

# Formatos
color_header = "#1F4E79"
color_band = "#D9E1F2"
color_block = "#FCE4D6"
color_kpi = "#E2EFDA"
color_title = "#203864"
border_thin = 1

fmt_header = wb.add_format({"bold": True, "font_color": "white", "bg_color": color_header, "border": border_thin, "align": "center"})
fmt_num = wb.add_format({"num_format": "0.00"})
fmt_int = wb.add_format({"num_format": "0"})
fmt_band = wb.add_format({"bg_color": color_band})
fmt_block = wb.add_format({"bg_color": color_block, "border": border_thin, "bold": True, "num_format": "0.00"})
fmt_block_text = wb.add_format({"bg_color": color_block, "border": border_thin, "bold": True})
fmt_kpi = wb.add_format({"bg_color": color_kpi, "border": border_thin, "bold": True, "num_format": "#,##0.00"})
fmt_kpi_text = wb.add_format({"bg_color": color_kpi, "border": border_thin, "bold": True})
fmt_big_title = wb.add_format({"bold": True, "font_size": 16, "font_color": "white", "align": "left", "valign": "vcenter", "bg_color": color_title})
fmt_subtitle = wb.add_format({"italic": True, "font_color": "white", "align": "right", "valign": "vcenter", "bg_color": color_title})
percent_fmt_center = wb.add_format({"num_format": "0%", "align": "center", "valign": "vcenter"})
percent_hidden = wb.add_format({"num_format": ";;;"})

def autosize_worksheet(ws, df_like, header_fmt):
    for col_idx, col_name in enumerate(df_like.columns):
        max_len = max([len(str(col_name))] + [len(str(x)) for x in df_like[col_name].astype(str).values[:500]])
        width = min(max(10, max_len + 2), 60)
        ws.set_column(col_idx, col_idx, width)
    ws.set_row(0, 20, header_fmt)

def apply_bands(ws, start_row, end_row, start_col, end_col, band_fmt):
    for r in range(start_row, end_row + 1):
        if (r - start_row) % 2 == 1:
            ws.set_row(r, None, band_fmt)

# =========================
# Generación Hojas
# =========================
supervisor_rows = []

for gestor in GESTORES_PERMITIDOS:
    sub = df[df["__GESTOR__"] == gestor].copy()
    sub = sort_df(sub, col_fecha, col_merc)

    total_importe = round(float(sub[col_importe].sum()) if col_importe in sub.columns else 0.0, 2)
    M330 = sum_hectolitros(sub, sub["__IS_MALTA__"], "330")
    M500 = sum_hectolitros(sub, sub["__IS_MALTA__"], "500")
    M1500 = sum_hectolitros(sub, sub["__IS_MALTA__"], "1500")
    P330 = sum_hectolitros(sub, sub["__IS_PARRANDA__"], "330")
    P500 = sum_hectolitros(sub, sub["__IS_PARRANDA__"], "500")
    P1500 = sum_hectolitros(sub, sub["__IS_PARRANDA__"], "1500")
    total_hecto = round(M330 + M500 + M1500 + P330 + P500 + P1500, 2)

    to_write = sub[export_cols].copy()
    for c in to_write.columns:
        if c != col_op and pd.api.types.is_numeric_dtype(to_write[c]):
            to_write[c] = to_write[c].round(2)

    sheet_name = gestor[:31]
    to_write.to_excel(writer, sheet_name=sheet_name, index=False)
    ws = writer.sheets[sheet_name]
    ws.freeze_panes(1, 0)
    autosize_worksheet(ws, to_write, fmt_header)

    for idx, c in enumerate(to_write.columns):
        if c == col_op: ws.set_column(idx, idx, None, fmt_int)
        elif pd.api.types.is_numeric_dtype(to_write[c]): ws.set_column(idx, idx, None, fmt_num)

    if len(to_write) > 0:
        apply_bands(ws, 1, len(to_write), 0, len(to_write.columns) - 1, fmt_band)
        ws.add_table(0, 0, len(to_write), len(to_write.columns) - 1, {
            "name": "Tabla_" + gestor.replace(" ", "")[:20],
            "style": "Table Style Medium 2",
            "columns": [{"header": h} for h in to_write.columns],
        })

    # KPIs Vendedor (Sin comisiones)
    kpi_row = len(to_write) + 2
    ws.write(kpi_row, 0, "VENTAS", fmt_block_text)
    ws.write_number(kpi_row, 1, total_importe, fmt_block)
    
    meta_gestor = GESTOR_METAS.get(gestor, META_HECTOLITROS)
    cumplimiento = 0.0 if meta_gestor == 0 else (total_hecto / meta_gestor)
    ws.write(kpi_row + 1, 0, "Total Hectolitros", fmt_block_text)
    ws.write_number(kpi_row + 1, 1, total_hecto, fmt_block)
    ws.write(kpi_row + 1, 3, cumplimiento, percent_fmt_center)

    # Conversión Blisters/Pallets
    conv_row = kpi_row + 4
    ws.merge_range(conv_row, 0, conv_row, 6, "Conversión de Cantidad a Blisters y Pallets por Producto", fmt_kpi_text)
    sub["_SIZE_"] = sub["Hectolitros_SIZE"].fillna("")
    sub["_PROD_"] = sub.apply(lambda r: ("MALTA" if r["__IS_MALTA__"] else ("PARRANDA" if r["__IS_PARRANDA__"] else "")), axis=1)
    
    conv = sub[(sub["_PROD_"] != "") & (sub["_SIZE_"].isin(["330", "500", "1500"]))].copy()
    conv["Blisters"] = conv[col_cant].fillna(0.0) if col_cant in conv.columns else 0.0
    
    def calc_pallets(row):
        units = UNITS_PER_PALLET.get((row["_PROD_"], row["_SIZE_"]), 0)
        return float(row["Blisters"]) / float(units) if units else 0.0
    conv["Pallets"] = conv.apply(calc_pallets, axis=1)

    def sum_cond(prod, size, col):
        return round(float(conv.loc[(conv["_PROD_"] == prod) & (conv["_SIZE_"] == size), col].sum()), 2)

    rows = [
        ("Malta", "330", sum_cond("MALTA", "330", "Blisters"), sum_cond("MALTA", "330", "Pallets"), M330),
        ("Parranda", "330", sum_cond("PARRANDA", "330", "Blisters"), sum_cond("PARRANDA", "330", "Pallets"), P330),
        ("Parranda", "500", sum_cond("PARRANDA", "500", "Blisters"), sum_cond("PARRANDA", "500", "Pallets"), P500),
        ("Parranda", "1500", sum_cond("PARRANDA", "1500", "Blisters"), sum_cond("PARRANDA", "1500", "Pallets"), P1500),
    ]
    conv_df = pd.DataFrame(rows, columns=["Producto", "Tamaño", "Blisters", "Pallets", "Hectolitros"])
    
    start_r = conv_row + 2
    conv_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_r, startcol=0)
    for j, coln in enumerate(conv_df.columns):
        ws.write(start_r, j, coln, fmt_header)
        col_type = fmt_num if coln in ("Blisters", "Pallets", "Hectolitros") else None
        if col_type: ws.set_column(j, j, 12, col_type)

    if len(conv_df) > 0:
        apply_bands(ws, start_r + 1, start_r + len(conv_df), 0, len(conv_df.columns) - 1, fmt_band)
        ws.add_table(start_r, 0, start_r + len(conv_df), len(conv_df.columns) - 1, {
            "name": f"TablaConv_{gestor.replace(' ','')[:15]}",
            "style": "Table Style Medium 9",
            "columns": [{"header": h} for h in conv_df.columns],
        })

    supervisor_rows.append({
        "Gestor": gestor, "Total Venta": total_importe,
        "M330": M330, "P330": P330, "P500": P500, "P1500": P1500,
        "Total Hectolitros": total_hecto,
    })

# =========================
# Hoja Supervisor
# =========================
super_df = pd.DataFrame(supervisor_rows)[["Gestor", "Total Venta", "M330", "P330", "P500", "P1500", "Total Hectolitros"]]
super_df.to_excel(writer, sheet_name="Supervisor", index=False, startrow=5)
ws = writer.sheets["Supervisor"]

ws.merge_range(0, 0, 1, 6, "Resumen de Ventas - Supervisor (SOLO PARRANDA/MALTA)", fmt_big_title)
ws.merge_range(0, 7, 1, 9, f"Semana: {rango_fechas_str}", fmt_subtitle)
ws.set_row(0, 28)
ws.set_row(1, 20)
ws.freeze_panes(6, 0)
autosize_worksheet(ws, super_df, fmt_header)

if len(super_df) > 0:
    apply_bands(ws, 7, 6 + len(super_df), 0, len(super_df.columns) - 1, fmt_band)
    ws.add_table(5, 0, 5 + len(super_df), len(super_df.columns) - 1, {
        "name": "Tabla_Supervisor",
        "style": "Table Style Medium 9",
        "columns": [{"header": h} for h in super_df.columns],
    })

total_ventas = round(float(super_df["Total Venta"].sum()), 2)
ws.merge_range(3, 0, 3, 2, "VENTAS TOTALES", fmt_kpi_text)
ws.merge_range(4, 0, 4, 2, total_ventas, fmt_kpi)

prod_row = 8 + len(super_df) + 2
totales_map = [("TOTAL M330", "M330"), ("TOTAL P330", "P330"), ("TOTAL P500", "P500"), ("TOTAL P1500", "P1500")]
for i, (lbl, col) in enumerate(totales_map):
    ws.merge_range(prod_row + i, 0, prod_row + i, 2, lbl, fmt_block_text)
    ws.merge_range(prod_row + i, 3, prod_row + i, 5, round(float(super_df[col].sum()), 2), fmt_block)

total_hecto_visible = round(float(super_df["Total Hectolitros"].sum()), 2)
ws.merge_range(prod_row + 4, 0, prod_row + 4, 2, "TOTAL HECTOLITROS", fmt_block_text)
ws.merge_range(prod_row + 4, 3, prod_row + 4, 5, total_hecto_visible, fmt_block)

meta_row = prod_row + 8
ws.merge_range(meta_row, 0, meta_row, 2, "META HECTOLITROS", fmt_block_text)
ws.merge_range(meta_row, 3, meta_row, 5, META_HECTOLITROS, fmt_block)
cumpl_hecto = 0.0 if META_HECTOLITROS == 0 else (total_hecto_visible / META_HECTOLITROS)
ws.merge_range(meta_row, 6, meta_row, 7, "% CUMPL. HECTO", fmt_kpi_text)
ws.merge_range(meta_row, 8, meta_row, 10, cumpl_hecto, percent_hidden)
ws.write(meta_row, 11, cumpl_hecto, percent_fmt_center)
ws.conditional_format(meta_row, 8, meta_row, 10, {"type": "data_bar", "bar_color": "#70AD47", "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 1, "bar_only": True})

for c in range(12): ws.set_column(c, c, 14)
ws.set_column(0, 0, 20)

writer.close()
print(f"✓ Reporte generado: {OUT_FILE}")