import pandas as pd
import numpy as np
from datetime import datetime, date
import calendar
import xlsxwriter
import re
import unicodedata

# --- CONFIGURACIÓN DE METAS ---
METAS_MENSUALES = {
    "ACEITE": 1000,
    "ARROZ": 2500,
    "AZUCAR": 5000,
    "REFRESCO": 2418,
    "SANTA ISABEL": 8000,
}

# --- CONFIGURACIÓN DE CALENDARIO LABORAL ---
FECHA_INICIO_LABORAL = date(2026, 4, 1)
TRABAJA_SABADO = False
TRABAJA_DOMINGO = False

ALLOWED_GESTORES = ["ALEXANDER", "DEYANIRA", "GEORLIS", "JEAN MICHEL", "JELEN", "MAYLEN"]

# Mapa de alias para corregir errores de escritura en las observaciones
ALIAS_MAP = {
    "ALELEXANDER": "ALEXANDER", "ALENXANDER": "ALEXANDER", "GEORLI": "GEORLIS",
    "MAYELIN": "MAYLEN", "JEANMICHEL": "JEAN MICHEL", "JEAN": "JEAN MICHEL",
    "MICHEL": "JEAN MICHEL", "MAYLIN": "MAYLEN", "DEIANIRA": "DEYANIRA"
}

file_in = "RV ABRIL 1-17.xls"

# --- FUNCIONES DE LIMPIEZA ---
def normalize_text(s):
    if not isinstance(s, str): return ""
    # Quitar acentos y poner en mayúsculas
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('utf-8').upper()
    return " ".join(s.split())

def detect_gestor(obs):
    txt = normalize_text(obs)
    # 1. Buscar coincidencia exacta
    for g in ALLOWED_GESTORES:
        if g in txt: return g
    # 2. Buscar en alias
    for alias, formal in ALIAS_MAP.items():
        if alias in txt: return formal
    return "OTRO"

# --- PROCESAMIENTO DE DATOS ---
df = pd.read_excel(file_in, header=3, engine="xlrd")
df.columns = [str(c).strip() for c in df.columns]

# Fechas
df["Fecha/Hora"] = pd.to_datetime(df["Fecha/Hora"], errors="coerce")
valid_dates = df["Fecha/Hora"].dropna()
start_date = valid_dates.min().date() if not valid_dates.empty else date.today()
end_date = valid_dates.max().date() if not valid_dates.empty else date.today()

# Lógica de días laborales
weekmask = "1111100" if not TRABAJA_SABADO else "1111110"
ultimo_dia_mes = date(end_date.year, end_date.month, calendar.monthrange(end_date.year, end_date.month)[1])
dias_laborales_totales = len(pd.bdate_range(start=FECHA_INICIO_LABORAL, end=ultimo_dia_mes, freq="C", weekmask=weekmask))
dias_laborales_transcurridos = len(pd.bdate_range(start=FECHA_INICIO_LABORAL, end=end_date, freq="C", weekmask=weekmask))
dias_laborales_transcurridos = max(1, dias_laborales_transcurridos)
dias_restantes = max(1, dias_laborales_totales - dias_laborales_transcurridos)

# Identificar columnas
group_col = next((c for c in df.columns if "grupo" in c.lower()), df.columns[1])
product_col = next((c for c in df.columns if "merc" in c.lower()), df.columns[2])
gestor_col = next((c for c in df.columns if "nota" in c.lower()), df.columns[6])
metric = next((m for m in ["Importe", "Suma Total", "Total"] if m in df.columns), df.columns[-1])
qcol = next((c for c in df.columns if any(x in c.lower() for x in ["cant", "unid"])), "Cantidad")

# Limpieza de datos
df["gestor_norm"] = df[gestor_col].apply(detect_gestor)
df["product_clean"] = df[product_col].astype(str).str.strip()
df[metric] = pd.to_numeric(df[metric], errors="coerce").fillna(0)
df[qcol] = pd.to_numeric(df[qcol], errors="coerce").fillna(0)

# Separar CES y PROCOVAR
procovar_mask = df[group_col].astype(str).str.contains("PROCOVAR|PARRANDA", case=False, na=False)
ces_allowed = df[~procovar_mask & df["gestor_norm"].isin(ALLOWED_GESTORES)].copy()
procovar_allowed = df[procovar_mask & df["gestor_norm"].isin(ALLOWED_GESTORES)].copy()

# --- NOMBRE DE SALIDA ---
months_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
out_filename = f"Productos del {start_date.day} al {end_date.day} de {months_es[start_date.month-1]} de {start_date.year}.xlsx"

# --- FUNCIONES DE RESUMEN ---
def build_resumen(df_source):
    if df_source.empty: return pd.DataFrame(columns=["Producto", "Total", "Cantidad"])
    r = df_source.groupby("product_clean").agg({metric: "sum", qcol: "sum"}).reset_index()
    r.columns = ["Producto", "Total", "Cantidad"]
    return r[r["Total"] != 0].sort_values("Total", ascending=False).reset_index(drop=True)

resumen_ces = build_resumen(ces_allowed)
resumen_procovar = build_resumen(procovar_allowed)

# --- ESCRITURA EXCEL ---
with pd.ExcelWriter(out_filename, engine="xlsxwriter") as writer:
    workbook = writer.book
    # Formatos
    f_header = workbook.add_format({"bold": True, "bg_color": "#1F4E78", "font_color": "white", "border": 1})
    f_num = workbook.add_format({"num_format": "#,##0.00", "border": 1})
    f_perc = workbook.add_format({"num_format": "0.00%", "border": 1})
    f_red = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006", "border": 1, "num_format": "#,##0.00"})
    f_green = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#006100", "border": 1, "num_format": "#,##0.00"})
    f_border = workbook.add_format({"border": 1})

    # 1. HOJA CUMPLIMIENTO
    ws_cumpl = workbook.add_worksheet("Cumplimiento")
    ws_cumpl.write(0, 0, f"Días: {dias_laborales_transcurridos} de {dias_laborales_totales} (Quedan {dias_restantes})", workbook.add_format({"bold": True}))
    headers = ["Producto", "Meta Mes", "Venta Real", "% Cumpl.", "Debería ir", "Estado", "Prom. Diario", "Nec. x Día"]
    for i, h in enumerate(headers): ws_cumpl.write(2, i, h, f_header)
    
    row = 3
    for prod, meta in METAS_MENSUALES.items():
        real = ces_allowed[ces_allowed["product_clean"].str.contains(prod, case=False, na=False)][qcol].sum()
        deberia = (meta / dias_laborales_totales) * dias_laborales_transcurridos
        delta = real - deberia
        ws_cumpl.write(row, 0, prod, f_border)
        ws_cumpl.write(row, 1, meta, f_num)
        ws_cumpl.write(row, 2, real, f_num)
        ws_cumpl.write(row, 3, (real/meta if meta > 0 else 0), f_perc)
        ws_cumpl.write(row, 4, deberia, f_num)
        ws_cumpl.write(row, 5, delta, f_green if delta >= 0 else f_red)
        ws_cumpl.write(row, 6, (real/dias_laborales_transcurridos), f_num)
        ws_cumpl.write(row, 7, max(0, (meta-real)/dias_restantes), f_num)
        row += 1
    ws_cumpl.set_column("A:H", 15)

    # 2. HOJA RESUMEN
    ws_res = workbook.add_worksheet("Resumen")
    ws_res.write(0, 0, "Resumen Global CES", f_header)
    resumen_ces.to_excel(writer, sheet_name="Resumen", index=False, startrow=1)
    
    # Gráfico CES Global
    if not resumen_ces.empty:
        chart_ces = workbook.add_chart({"type": "pie"})
        chart_ces.add_series({
            "name": "Ventas CES",
            "categories": ["Resumen", 2, 0, 1+len(resumen_ces), 0],
            "values": ["Resumen", 2, 1, 1+len(resumen_ces), 1],
            "data_labels": {"percentage": True, "position": "outside_end"}
        })
        ws_res.insert_chart("J2", chart_ces)

    # Procovar debajo
    start_proc = len(resumen_ces) + 6
    ws_res.write(start_proc - 1, 0, "Resumen Global PROCOVAR", f_header)
    resumen_procovar.to_excel(writer, sheet_name="Resumen", index=False, startrow=start_proc)
    
    if not resumen_procovar.empty:
        chart_proc = workbook.add_chart({"type": "pie"})
        chart_proc.add_series({
            "name": "Ventas PROCOVAR",
            "categories": ["Resumen", start_proc+1, 0, start_proc+len(resumen_procovar), 0],
            "values": ["Resumen", start_proc+1, 1, start_proc+len(resumen_procovar), 1],
            "data_labels": {"percentage": True}
        })
        ws_res.insert_chart(f"J{start_proc+1}", chart_proc)

    # 3. HOJAS POR GESTOR
    for g in ALLOWED_GESTORES:
        df_g_ces = build_resumen(ces_allowed[ces_allowed["gestor_norm"] == g])
        df_g_proc = build_resumen(procovar_allowed[procovar_allowed["gestor_norm"] == g])
        
        if df_g_ces.empty and df_g_proc.empty: continue
        
        ws_g = workbook.add_worksheet(g[:31])
        # CES del gestor
        ws_g.write(0, 0, f"CES - {g}", f_header)
        df_g_ces.to_excel(writer, sheet_name=ws_g.name, index=False, startrow=1)
        if not df_g_ces.empty:
            ch = workbook.add_chart({"type": "pie"})
            ch.add_series({
                "categories": [ws_g.name, 2, 0, 1+len(df_g_ces), 0],
                "values": [ws_g.name, 2, 1, 1+len(df_g_ces), 1],
                "data_labels": {"percentage": True}
            })
            ws_g.insert_chart("J2", ch)
            
        # PROCOVAR del gestor
        row_p = len(df_g_ces) + 6
        ws_g.write(row_p - 1, 0, f"PROCOVAR - {g}", f_header)
        df_g_proc.to_excel(writer, sheet_name=ws_g.name, index=False, startrow=row_p)
        if not df_g_proc.empty:
            chp = workbook.add_chart({"type": "pie"})
            chp.add_series({
                "categories": [ws_g.name, row_p+1, 0, row_p+len(df_g_proc), 0],
                "values": [ws_g.name, row_p+1, 1, row_p+len(df_g_proc), 1],
                "data_labels": {"percentage": True}
            })
            ws_g.insert_chart(f"J{row_p+1}", chp)

print("Proceso completado. Archivo:", out_filename)