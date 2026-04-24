import pandas as pd
import re
import unicodedata
from datetime import datetime

# =========================
# CONFIGURACION
# =========================
INPUT_FILE = "REPORTE DE VENTA MARZO 2026.xls"  # Cambia al archivo que corresponda

GESTORES_PERMITIDOS = [
    "ALEXANDER",
    "DEYANIRA",
    "GEORLIS",
    "JEAN MICHEL",
    "JELEN",
    "MAYLEN",
]

# Aliases/variantes escritas en la Nota
ALIAS_MAP = {
    "ALELEXANDER": "ALEXANDER",
    "ALENXANDER":  "ALEXANDER",
    "ALEXANDR":    "ALEXANDER",
    "ALEJANDER":   "ALEXANDER",
    "ALEX":        "ALEXANDER",
    "DEIANIRA":    "DEYANIRA",
    "DEYANNIRA":   "DEYANIRA",
    "DEYANI":      "DEYANIRA",
    "DEY":         "DEYANIRA",
    "GEORLI":      "GEORLIS",
    "GEIRLIS":     "GEORLIS",
    "JEANMICHEL":  "JEAN MICHEL",
    "JEANMIC":     "JEAN MICHEL",
    "JEANMICHE":   "JEAN MICHEL",
    "JEAN":        "JEAN MICHEL",
    "JAEN":        "JEAN MICHEL",
    "MICHEL":      "JEAN MICHEL",
    "MAYELIN":     "MAYLEN",
    "MAYELEN":     "MAYLEN",
    "MAYLIN":      "MAYLEN",
}

MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}


# =========================
# Utilidades
# =========================
def find_col(cols, subs):
    for c in cols:
        if isinstance(c, str) and all(s.lower() in c.lower() for s in subs):
            return c
    return None


def detect_gestor_punto(obs_val):
    """Detecta si la nota tiene NOMBRE!! o NOMBRE!!! (2+ exclamaciones).
    Eso significa que el cliente vino por su cuenta (punto), no por el gestor."""
    if obs_val is None:
        return None
    raw = str(obs_val).strip()
    if not raw or raw.upper() == "NAN":
        return None
    t = unicodedata.normalize("NFKD", raw.upper())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    for g in GESTORES_PERMITIDOS:
        if re.search(rf"(?:^|\b){re.escape(g)}\s*!{{2,}}", t):
            return g
    for alias, gestor in ALIAS_MAP.items():
        alias_norm = unicodedata.normalize("NFKD", alias.upper())
        alias_norm = "".join(ch for ch in alias_norm if not unicodedata.combining(ch))
        if re.search(rf"(?:^|\b){re.escape(alias_norm)}\s*!{{2,}}", t):
            return gestor
    return None


def smart_to_numeric(series):
    if pd.api.types.is_numeric_dtype(series):
        return series
    s = series.astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


# =========================
# Carga del archivo
# =========================
print(f"Leyendo: {INPUT_FILE}")
raw = pd.read_excel(INPUT_FILE, header=None)

header_row_idx = None
for i in range(min(30, len(raw))):
    row_vals = [str(v).strip() for v in raw.iloc[i].tolist()]
    if any("Operaci" in v for v in row_vals) and any("Fecha" in v for v in row_vals):
        header_row_idx = i
        break
if header_row_idx is None:
    header_row_idx = 2
print(f"  Encabezado encontrado en fila: {header_row_idx}")

df = pd.read_excel(INPUT_FILE, header=header_row_idx)
df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
df.columns = [str(c).strip() for c in df.columns]
cols = df.columns

# Detectar columnas
col_op     = find_col(cols, ["No.", "Operación"]) or find_col(cols, ["Operación"])
col_fecha  = find_col(cols, ["Fecha"])
col_socio  = find_col(cols, ["socio"])
col_merc   = find_col(cols, ["Mercancía"]) or find_col(cols, ["Mercancia"])
col_grupo  = find_col(cols, ["Grupo"])
col_cant   = find_col(cols, ["Cant"])
col_import = find_col(cols, ["Importe"])
col_sumat  = find_col(cols, ["Suma", "Total"])
col_obs    = find_col(cols, ["Nota"])

print(f"  Columnas: op={col_op}, fecha={col_fecha}, socio={col_socio}, "
      f"merc={col_merc}, cant={col_cant}, importe={col_import}, suma={col_sumat}, nota={col_obs}")

if col_fecha  and col_fecha  in df.columns:
    df[col_fecha]  = pd.to_datetime(df[col_fecha], errors="coerce")
if col_import and col_import in df.columns:
    df[col_import] = smart_to_numeric(df[col_import]).round(2)
if col_sumat  and col_sumat  in df.columns:
    df[col_sumat]  = smart_to_numeric(df[col_sumat]).round(2)
if col_cant   and col_cant   in df.columns:
    df[col_cant]   = smart_to_numeric(df[col_cant])
if col_op     and col_op     in df.columns:
    df[col_op]     = pd.to_numeric(df[col_op], errors="coerce").astype("Int64")

# =========================
# Identificar clientes punto
# =========================
df["__GESTOR_PUNTO__"] = (
    df[col_obs].apply(detect_gestor_punto) if col_obs and col_obs in df.columns else None
)
punto_df = df[df["__GESTOR_PUNTO__"].notna()].copy()
print(f"  Filas identificadas como clientes punto: {len(punto_df)}")

if col_fecha and col_fecha in punto_df.columns:
    sort_by = [col_fecha] + ([col_merc] if col_merc and col_merc in punto_df.columns else [])
    punto_df = punto_df.sort_values(by=sort_by)

# Columnas a exportar
export_cols = [c for c in [col_op, col_fecha, col_socio, col_merc, col_grupo,
                            col_cant, col_import, col_sumat, col_obs]
               if c and c in punto_df.columns]
out = punto_df[export_cols].copy()
out.insert(len(out.columns), "Gestor", punto_df["__GESTOR_PUNTO__"].values)

# =========================
# Nombre archivo de salida
# =========================
if col_fecha and col_fecha in punto_df.columns and not punto_df[col_fecha].isna().all():
    fmin = punto_df[col_fecha].min()
    fmax = punto_df[col_fecha].max()
    OUT_FILE = (f"CLIENTES_PUNTO-{fmin.day:02d}-{fmax.day:02d}"
                f"-{MESES_ES.get(fmin.month,'MES')}-{fmin.year}.xlsx")
    rango_str = f"{fmin.strftime('%d/%m/%Y')} al {fmax.strftime('%d/%m/%Y')}"
else:
    OUT_FILE = f"CLIENTES_PUNTO_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
    rango_str = "Rango no disponible"

# =========================
# Generar Excel
# =========================
writer = pd.ExcelWriter(OUT_FILE, engine="xlsxwriter",
                        engine_kwargs={"options": {"nan_inf_to_errors": True}})
wb = writer.book

# Formatos
color_header = "#1F4E79"
color_band   = "#D9E1F2"
color_kpi    = "#E2EFDA"
color_blk    = "#FCE4D6"
color_title  = "#203864"

fmt_header  = wb.add_format({"bold": True, "font_color": "white", "bg_color": color_header,
                              "border": 1, "align": "center"})
fmt_num     = wb.add_format({"num_format": "#,##0.00"})
fmt_int     = wb.add_format({"num_format": "0"})
fmt_band    = wb.add_format({"bg_color": color_band})
fmt_kpi     = wb.add_format({"bg_color": color_kpi, "border": 1, "bold": True, "num_format": "#,##0.00"})
fmt_kpi_txt = wb.add_format({"bg_color": color_kpi, "border": 1, "bold": True})
fmt_blk     = wb.add_format({"bg_color": color_blk, "border": 1, "bold": True, "num_format": "#,##0.00"})
fmt_blk_txt = wb.add_format({"bg_color": color_blk, "border": 1, "bold": True})
fmt_title   = wb.add_format({"bold": True, "font_size": 14, "font_color": "white",
                              "bg_color": color_title, "align": "left", "valign": "vcenter"})
fmt_subtitle = wb.add_format({"italic": True, "font_color": "white", "bg_color": color_title,
                               "align": "right", "valign": "vcenter"})

# ---- Hoja principal ----
out.to_excel(writer, sheet_name="Clientes Punto", index=False, startrow=2)
ws = writer.sheets["Clientes Punto"]
ncols = len(out.columns)

ws.merge_range(0, 0, 0, max(ncols - 2, 0), "Clientes que vinieron por su cuenta (punto)", fmt_title)
ws.merge_range(0, max(ncols - 1, 1), 0, ncols - 1, f"Periodo: {rango_str}", fmt_subtitle)
ws.set_row(0, 26)
ws.set_row(1, 4)
ws.set_row(2, 20, fmt_header)
ws.freeze_panes(3, 0)

# Auto-ancho
for idx, cname in enumerate(out.columns):
    max_len = max([len(str(cname))] + [len(str(v)) for v in out[cname].astype(str).values[:500]])
    ws.set_column(idx, idx, min(max(12, max_len + 2), 55))

# Formatos numéricos
for idx, cname in enumerate(out.columns):
    if cname == col_op:
        ws.set_column(idx, idx, None, fmt_int)
    elif cname in (col_import, col_sumat):
        ws.set_column(idx, idx, None, fmt_num)

# Bandas de color
for r in range(1, len(out) + 1):
    if r % 2 == 0:
        ws.set_row(r + 2, None, fmt_band)

# Tabla Excel
if len(out) >= 1:
    ws.add_table(2, 0, 2 + len(out), ncols - 1, {
        "name": "Tabla_ClientesPunto",
        "style": "Table Style Medium 6",
        "columns": [{"header": h} for h in out.columns],
    })

# ---- Resumen por gestor ----
res_row = len(out) + 5
ws.merge_range(res_row, 0, res_row, 3, "Resumen por Gestor", fmt_kpi_txt)
res_row += 1
for j, h in enumerate(["Gestor", "Nro. Operaciones", "Clientes Únicos", "Total Importe"]):
    ws.write(res_row, j, h, fmt_header)
res_row += 1

grand_total = 0.0
for g in GESTORES_PERMITIDOS:
    sub_g = out[out["Gestor"] == g]
    n_filas     = len(sub_g)
    n_clientes  = sub_g[col_socio].nunique() if col_socio and col_socio in sub_g.columns else n_filas
    total_g     = round(float(sub_g[col_import].sum()), 2) if col_import and col_import in sub_g.columns else 0.0
    grand_total += total_g
    ws.write(res_row, 0, g, fmt_blk_txt)
    ws.write_number(res_row, 1, n_filas, fmt_int)
    ws.write_number(res_row, 2, n_clientes, fmt_int)
    ws.write_number(res_row, 3, total_g, fmt_blk)
    res_row += 1

# Total general
ws.write(res_row, 0, "TOTAL OFICINA", fmt_kpi_txt)
ws.write_number(res_row, 1, len(out), fmt_kpi)
n_unicos = out[col_socio].nunique() if col_socio and col_socio in out.columns else len(out)
ws.write_number(res_row, 2, n_unicos, fmt_kpi)
ws.write_number(res_row, 3, round(grand_total, 2), fmt_kpi)

writer.close()
print(f"Archivo generado: {OUT_FILE}")
print(f"  Total filas punto    : {len(out)}")
print(f"  Total importe oficina: {round(grand_total, 2)}")
