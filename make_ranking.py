import pandas as pd
import re, unicodedata
from datetime import datetime

# =========================
# CONFIGURACION
# =========================
INPUT_FILE = "RV JULIO 1-3.xls"  # Cambia si corresponde (xlsx/xls)
GESTORES_PERMITIDOS = [
    "ALEXANDER",
    "DEYANIRA",
    "GEORLIS",
    "JEAN MICHEL",
    "ERNESTO",
    "ANDY",
    "MAYLEN",
]

# Aliases comunes por errores en Observación
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

MESES_ES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
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


def smart_to_numeric(series):
    if pd.api.types.is_numeric_dtype(series):
        return series
    s = series.astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


# =========================
# Carga y preprocesamiento
# =========================
raw = pd.read_excel(INPUT_FILE, header=None)
header_row_idx = None
for i in range(min(30, len(raw))):
    row_vals = raw.iloc[i].astype(str).str.strip().tolist()
    if any("No. de Operación" in str(v) for v in row_vals) and any(
        "Fecha" in str(v) for v in row_vals
    ):
        header_row_idx = i
        break
if header_row_idx is None:
    header_row_idx = 2

df = pd.read_excel(INPUT_FILE, header=header_row_idx)
df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
df.columns = [str(c).strip() for c in df.columns]
cols = df.columns

col_obs = find_col(cols, ["Nota"]) or find_col(cols, ["Nota"])
col_importe = find_col(cols, ["Importe"])
col_fecha = find_col(cols, ["Fecha"])

if col_importe in df.columns:
    df[col_importe] = smart_to_numeric(df[col_importe]).round(2)
if col_fecha in df.columns:
    df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")

# Detectar gestor
df["__GESTOR__"] = (
    df[col_obs].apply(detect_gestor_from_obs) if col_obs in df.columns else None
)
# Normalizar: eliminar espacios y forzar mayúsculas para evitar duplicados ocultos
df["__GESTOR__"] = df["__GESTOR__"].astype(str).str.strip().str.upper()
df["__GESTOR__"] = df["__GESTOR__"].where(df["__GESTOR__"].isin(GESTORES_PERMITIDOS), other=None)
df = df[df["__GESTOR__"].isin(GESTORES_PERMITIDOS)].copy()

# Validar columnas críticas
if col_fecha not in df.columns or df[col_fecha].isna().all():
    raise SystemExit("ERROR: No se encontró columna de Fecha válida en el archivo.")
if col_importe not in df.columns:
    raise SystemExit("ERROR: No se encontró columna de Importe en el archivo.")

# Eliminar filas sin fecha
df = df.dropna(subset=[col_fecha])

# Calcular semana (lunes a viernes)
def week_label(ts):
    monday = ts - pd.Timedelta(days=ts.dayofweek)  # lunes de esa semana
    friday = monday + pd.Timedelta(days=4)          # viernes de esa semana
    return f"{monday.strftime('%d/%m')} - {friday.strftime('%d/%m')}"

def week_start(ts):
    return (ts - pd.Timedelta(days=ts.dayofweek)).normalize()

df["__SEMANA__"] = df[col_fecha].apply(week_label)
df["__SEMANA_START__"] = df[col_fecha].apply(week_start)

# Rango de fechas
fmin, fmax = df[col_fecha].min(), df[col_fecha].max()
rango_fechas_str = f"{fmin.strftime('%d-%m-%Y')} a {fmax.strftime('%d-%m-%Y')}"
OUT_FILE = f"RANKING-{fmin.day:02d}-{fmax.day:02d}-{MESES_ES.get(fmin.month,'MES')}-{fmin.year}.xlsx"

# =========================
# Construir datos de ranking
# =========================

# --- Ranking GENERAL (acumulado total) ---
general = (
    df.groupby("__GESTOR__")[col_importe]
    .sum()
    .reindex(GESTORES_PERMITIDOS, fill_value=0.0)  # fuerza exactamente las filas de gestores permitidos
    .round(2)
    .sort_values(ascending=False)
    .reset_index()
)
general.columns = ["Vendedor", "Ventas (USD)"]
general.insert(0, "Posición", range(1, len(general) + 1))

# --- Ranking POR SEMANA ---
semanal = (
    df.groupby(["__SEMANA_START__", "__SEMANA__", "__GESTOR__"])[col_importe]
    .sum()
    .round(2)
    .reset_index()
)
semanal.columns = ["__SORT__", "Semana", "Vendedor", "Ventas (USD)"]
# Forzar que solo aparezcan los gestores permitidos (sin duplicados ocultos)
semanal = semanal[semanal["Vendedor"].isin(GESTORES_PERMITIDOS)].copy()
# Segunda agrupación defensiva: si aún hay duplicados por semana+vendedor, sumarlos
semanal = (
    semanal.groupby(["__SORT__", "Semana", "Vendedor"], as_index=False)["Ventas (USD)"]
    .sum()
    .round(2)
)
semanal["Posición"] = semanal.groupby("Semana")["Ventas (USD)"].rank(
    ascending=False, method="min"
).astype(int)
semanal = semanal.sort_values(["__SORT__", "Posición"])

# --- Ranking POR DÍA (acumulado progresivo día a día) ---
dias_unicos = sorted(df[col_fecha].dt.normalize().unique())
acum_rows = []
for dia in dias_unicos:
    corte = df[df[col_fecha].dt.normalize() <= dia]
    totales = corte.groupby("__GESTOR__")[col_importe].sum().round(2)
    for gestor in GESTORES_PERMITIDOS:
        acum_rows.append({
            "Fecha": pd.Timestamp(dia),
            "Vendedor": gestor,
            "Acumulado (USD)": round(float(totales.get(gestor, 0.0)), 2),
        })
diario_df = pd.DataFrame(acum_rows)
diario_df["Posición"] = diario_df.groupby("Fecha")["Acumulado (USD)"].rank(
    ascending=False, method="min"
).astype(int)
diario_df = diario_df.sort_values(["Fecha", "Posición"])

# =========================
# Escritura Excel (xlsxwriter)
# =========================
writer = pd.ExcelWriter(
    OUT_FILE,
    engine="xlsxwriter",
    engine_kwargs={"options": {"nan_inf_to_errors": True}},
)
wb = writer.book

# Paleta y formatos
color_title = "#203864"
color_header = "#1F4E79"
color_gold = "#FFD700"
color_silver = "#C0C0C0"
color_bronze = "#CD7F32"
color_band = "#D9E1F2"
border_thin = 1

fmt_big_title = wb.add_format({
    "bold": True, "font_size": 18, "font_color": "white",
    "align": "center", "valign": "vcenter", "bg_color": color_title,
    "border": border_thin,
})
fmt_subtitle = wb.add_format({
    "italic": True, "font_size": 11, "font_color": "white",
    "align": "center", "valign": "vcenter", "bg_color": color_title,
})
fmt_header = wb.add_format({
    "bold": True, "font_color": "white", "bg_color": color_header,
    "border": border_thin, "align": "center", "valign": "vcenter",
    "font_size": 11,
})
fmt_num = wb.add_format({
    "num_format": "#,##0", "align": "center", "border": border_thin,
})
fmt_pos = wb.add_format({
    "bold": True, "align": "center", "border": border_thin, "font_size": 13,
})
fmt_name = wb.add_format({
    "bold": True, "align": "left", "border": border_thin, "font_size": 11,
    "indent": 1,
})
fmt_band = wb.add_format({"bg_color": color_band})
fmt_gold = wb.add_format({
    "bold": True, "bg_color": color_gold, "border": border_thin,
    "align": "center", "font_size": 14,
})
fmt_gold_name = wb.add_format({
    "bold": True, "bg_color": color_gold, "border": border_thin,
    "align": "left", "font_size": 12, "indent": 1,
})
fmt_gold_num = wb.add_format({
    "bold": True, "bg_color": color_gold, "border": border_thin,
    "num_format": "#,##0", "align": "center", "font_size": 12,
})
fmt_silver = wb.add_format({
    "bold": True, "bg_color": color_silver, "border": border_thin,
    "align": "center", "font_size": 13,
})
fmt_silver_name = wb.add_format({
    "bold": True, "bg_color": color_silver, "border": border_thin,
    "align": "left", "font_size": 11, "indent": 1,
})
fmt_silver_num = wb.add_format({
    "bold": True, "bg_color": color_silver, "border": border_thin,
    "num_format": "#,##0", "align": "center", "font_size": 11,
})
fmt_bronze = wb.add_format({
    "bold": True, "bg_color": color_bronze, "font_color": "white",
    "border": border_thin, "align": "center", "font_size": 13,
})
fmt_bronze_name = wb.add_format({
    "bold": True, "bg_color": color_bronze, "font_color": "white",
    "border": border_thin, "align": "left", "font_size": 11, "indent": 1,
})
fmt_bronze_num = wb.add_format({
    "bold": True, "bg_color": color_bronze, "font_color": "white",
    "border": border_thin, "num_format": "#,##0", "align": "center", "font_size": 11,
})
fmt_week_title = wb.add_format({
    "bold": True, "font_size": 13, "font_color": "white",
    "bg_color": "#2E75B6", "align": "left", "valign": "vcenter",
    "border": border_thin, "indent": 1,
})
fmt_date = wb.add_format({
    "num_format": "dd/mm/yyyy", "align": "center", "border": border_thin,
})

medal_fmts = {
    1: (fmt_gold, fmt_gold_name, fmt_gold_num),
    2: (fmt_silver, fmt_silver_name, fmt_silver_num),
    3: (fmt_bronze, fmt_bronze_name, fmt_bronze_num),
}
MEDAL_EMOJI = {1: "🥇", 2: "🥈", 3: "🥉"}


def write_ranking_block(ws, start_row, ranking_df, pos_col, name_col, val_col):
    """Escribe un bloque de ranking con medallas para top 3."""
    for i, (_, row) in enumerate(ranking_df.iterrows()):
        r = start_row + i
        pos = int(row[pos_col])
        medal = MEDAL_EMOJI.get(pos, "")
        label = f"{medal} {pos}" if medal else str(pos)

        if pos in medal_fmts:
            fp, fn, fv = medal_fmts[pos]
            ws.write(r, 0, label, fp)
            ws.write(r, 1, row[name_col], fn)
            ws.write_number(r, 2, float(row[val_col]), fv)
        else:
            ws.write(r, 0, label, fmt_pos)
            ws.write(r, 1, row[name_col], fmt_name)
            ws.write_number(r, 2, float(row[val_col]), fmt_num)
    return start_row + len(ranking_df)


# ========================================
# HOJA 1: RANKING GENERAL
# ========================================
ws_gen = wb.add_worksheet("Ranking General")

# Título
ws_gen.merge_range(0, 0, 1, 2, "RANKING DE VENTAS", fmt_big_title)
ws_gen.merge_range(2, 0, 2, 2, f"Periodo: {rango_fechas_str}", fmt_subtitle)
ws_gen.set_row(0, 30)
ws_gen.set_row(1, 22)
ws_gen.set_row(2, 20)

# Encabezados
r = 4
ws_gen.write(r, 0, "Posición", fmt_header)
ws_gen.write(r, 1, "Vendedor", fmt_header)
ws_gen.write(r, 2, "Ventas (USD)", fmt_header)

# Datos
write_ranking_block(ws_gen, r + 1, general, "Posición", "Vendedor", "Ventas (USD)")

# Total
total_row = r + 1 + len(general) + 1
fmt_total_label = wb.add_format({
    "bold": True, "font_size": 12, "border": border_thin, "align": "right",
    "bg_color": "#203864", "font_color": "white", "indent": 1,
})
fmt_total_val = wb.add_format({
    "bold": True, "font_size": 12, "border": border_thin, "align": "center",
    "bg_color": "#203864", "font_color": "white", "num_format": "#,##0",
})
ws_gen.merge_range(total_row, 0, total_row, 1, "TOTAL VENTAS", fmt_total_label)
ws_gen.write_number(total_row, 2, float(general["Ventas (USD)"].sum()), fmt_total_val)

# Barra de datos visual en la columna de ventas
ws_gen.conditional_format(r + 1, 2, r + len(general), 2, {
    "type": "data_bar",
    "bar_color": "#4472C4",
    "bar_only": False,
    "min_type": "num",
    "min_value": 0,
})

# Anchos
ws_gen.set_column(0, 0, 12)
ws_gen.set_column(1, 1, 22)
ws_gen.set_column(2, 2, 20)
ws_gen.freeze_panes(5, 0)

# ========================================
# HOJA 2: RANKING POR SEMANA
# ========================================
ws_sem = wb.add_worksheet("Ranking Semanal")

ws_sem.merge_range(0, 0, 1, 2, "RANKING SEMANAL", fmt_big_title)
ws_sem.merge_range(2, 0, 2, 2, f"Periodo: {rango_fechas_str}", fmt_subtitle)
ws_sem.set_row(0, 30)
ws_sem.set_row(1, 22)
ws_sem.set_row(2, 20)

current_row = 4
semanas_ordenadas = semanal.drop_duplicates("Semana").sort_values("__SORT__")["Semana"]

for semana in semanas_ordenadas:
    bloque = semanal[semanal["Semana"] == semana].sort_values("Posición")

    # Título de semana
    ws_sem.merge_range(
        current_row, 0, current_row, 2,
        f"Semana: {semana}", fmt_week_title,
    )
    current_row += 1

    # Encabezados
    ws_sem.write(current_row, 0, "Posición", fmt_header)
    ws_sem.write(current_row, 1, "Vendedor", fmt_header)
    ws_sem.write(current_row, 2, "Ventas (USD)", fmt_header)
    current_row += 1

    # Datos
    end = write_ranking_block(ws_sem, current_row, bloque, "Posición", "Vendedor", "Ventas (USD)")

    # Barra de datos
    ws_sem.conditional_format(current_row, 2, end - 1, 2, {
        "type": "data_bar",
        "bar_color": "#4472C4",
        "bar_only": False,
        "min_type": "num",
        "min_value": 0,
    })

    current_row = end + 1  # espacio entre semanas

ws_sem.set_column(0, 0, 12)
ws_sem.set_column(1, 1, 22)
ws_sem.set_column(2, 2, 20)
ws_sem.freeze_panes(4, 0)

# ========================================
# HOJA 3: PROGRESO DIARIO (acumulado)
# ========================================
ws_dia = wb.add_worksheet("Progreso Diario")

ws_dia.merge_range(0, 0, 1, 3, "PROGRESO DIARIO ACUMULADO", fmt_big_title)
ws_dia.merge_range(2, 0, 2, 3, f"Periodo: {rango_fechas_str}", fmt_subtitle)
ws_dia.set_row(0, 30)
ws_dia.set_row(1, 22)
ws_dia.set_row(2, 20)

# Encabezados
r = 4
ws_dia.write(r, 0, "Fecha", fmt_header)
ws_dia.write(r, 1, "Posición", fmt_header)
ws_dia.write(r, 2, "Vendedor", fmt_header)
ws_dia.write(r, 3, "Acumulado (USD)", fmt_header)

current_row = r + 1
for dia in dias_unicos:
    dia_ts = pd.Timestamp(dia)
    bloque = diario_df[diario_df["Fecha"] == dia_ts].sort_values("Posición")

    for i, (_, row) in enumerate(bloque.iterrows()):
        pos = int(row["Posición"])
        medal = MEDAL_EMOJI.get(pos, "")
        label = f"{medal} {pos}" if medal else str(pos)

        if i == 0:
            ws_dia.write_datetime(current_row, 0, dia_ts.to_pydatetime(), fmt_date)
        else:
            ws_dia.write(current_row, 0, "", fmt_date)

        if pos in medal_fmts:
            fp, fn, fv = medal_fmts[pos]
            ws_dia.write(current_row, 1, label, fp)
            ws_dia.write(current_row, 2, row["Vendedor"], fn)
            ws_dia.write_number(current_row, 3, float(row["Acumulado (USD)"]), fv)
        else:
            ws_dia.write(current_row, 1, label, fmt_pos)
            ws_dia.write(current_row, 2, row["Vendedor"], fmt_name)
            ws_dia.write_number(current_row, 3, float(row["Acumulado (USD)"]), fmt_num)
        current_row += 1

    current_row += 1  # espacio entre días

ws_dia.set_column(0, 0, 14)
ws_dia.set_column(1, 1, 12)
ws_dia.set_column(2, 2, 22)
ws_dia.set_column(3, 3, 20)
ws_dia.freeze_panes(5, 0)

# ========================================
# HOJA 4: GRÁFICO DE EVOLUCIÓN
# ========================================
# Tabla pivot para el gráfico: fecha x gestor
pivot = diario_df.pivot_table(
    index="Fecha", columns="Vendedor", values="Acumulado (USD)", fill_value=0
).reset_index()
pivot.columns.name = None

# Escribir datos del pivot en hoja oculta para el gráfico
ws_chart_data = wb.add_worksheet("_datos_grafico")
ws_chart_data.hide()

# Encabezados
ws_chart_data.write(0, 0, "Fecha")
gestores_en_pivot = [c for c in pivot.columns if c != "Fecha"]
for j, g in enumerate(gestores_en_pivot):
    ws_chart_data.write(0, j + 1, g)

# Datos
fmt_date_hidden = wb.add_format({"num_format": "dd/mm/yyyy"})
for i, (_, row) in enumerate(pivot.iterrows()):
    ws_chart_data.write_datetime(i + 1, 0, row["Fecha"].to_pydatetime(), fmt_date_hidden)
    for j, g in enumerate(gestores_en_pivot):
        ws_chart_data.write_number(i + 1, j + 1, float(row[g]))

n_rows = len(pivot)
n_cols = len(gestores_en_pivot)

# Crear gráfico de líneas
chart = wb.add_chart({"type": "line"})
chart.set_title({"name": "Evolución de Ventas Acumuladas por Vendedor"})
chart.set_x_axis({"name": "Fecha", "num_format": "dd/mm", "date_axis": True})
chart.set_y_axis({"name": "Ventas Acumuladas (USD)", "num_format": "#,##0"})
chart.set_size({"width": 900, "height": 500})
chart.set_style(10)

colors = ["#4472C4", "#ED7D31", "#70AD47", "#FFC000", "#5B9BD5", "#FF6384"]
for j, g in enumerate(gestores_en_pivot):
    chart.add_series({
        "name": g,
        "categories": ["_datos_grafico", 1, 0, n_rows, 0],
        "values": ["_datos_grafico", 1, j + 1, n_rows, j + 1],
        "line": {"color": colors[j % len(colors)], "width": 2.5},
        "marker": {"type": "circle", "size": 5},
    })

chart.set_legend({"position": "bottom"})

ws_chart = wb.add_worksheet("Evolución")
ws_chart.merge_range(0, 0, 1, 8, "EVOLUCIÓN DE VENTAS ACUMULADAS", fmt_big_title)
ws_chart.set_row(0, 30)
ws_chart.set_row(1, 22)
ws_chart.insert_chart("A4", chart)

# ========================================
writer.close()
print(f"✓ Archivo generado: {OUT_FILE}")
