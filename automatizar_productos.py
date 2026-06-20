import pandas as pd
from datetime import date
import calendar
import re
import unicodedata

# --- CONFIGURACIÓN DE METAS (Importaciones) ---
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

ALLOWED_GESTORES = ["ALEXANDER", "DEYANIRA", "GEORLIS", "JEAN MICHEL", "ERNESTO", "ANDY", "MAYLEN"]

ALIAS_MAP = {
    "ALELEXANDER": "ALEXANDER", "ALENXANDER": "ALEXANDER", "GEORLI": "GEORLIS",
    "MAYELIN": "MAYLEN", "JEANMICHEL": "JEAN MICHEL", "JEAN": "JEAN MICHEL",
    "MICHEL": "JEAN MICHEL", "ERNESTO": "ERNESTO", "MAYLIN": "MAYLEN", "DEIANIRA": "DEYANIRA"
}

# --- CLASIFICACIÓN POR GRUPO COMERCIAL ---
PRODUCT_GROUPS_KEYWORDS = {
    "PARRANDA": ["PARRANDA", "MALTA GUAJIRA", "MALTA"],
    "IMPORTACIONES": [
        "ACEITE SOYA", "ACEITE",
        "ARROZ CAMIL", "ARROZ ENERGY", "ARROZ PATEKO", "ARROZ RIVIERA", "ARROZ BLANCO", "ARROZ",
        "AZUCAR CAMIL", "AZUCAR ENERGY", "AZUCAR PATEKO", "AZUCAR MORENA", "AZUCAR",
        "QUESO GOUDA", "QUESO", "SANTA ISABEL",
        "REFRESCO SANTA", "REFRESCO",
        "ESPAGUETTI ALLEGRA", "ALLEGRA",
        "SOPA DE POLLO", "CREMA DE POLLO", "CREMA DE LENTEJAS", "DETERGENTE BOW",
    ],
    "CONSIGNACION": [
        "PAPEL HIGIENICO LIRIO", "PAPEL HIGIENICO MANATI", "PAPEL HIGIENICO PROSITO",
        "PAPEL HIGIENICO", "PAPEL LIRIO", "PAPEL MANATI", "PAPEL PROSITO",
        "SERVILLETA PROSITO", "SERVILLETA", "RON SANTIAGO",
        "ENERGIZANTE GO+", "ENERGIZANTE FLASH", "ENERGIZANTE",
    ],
    "TECNOLOGIA Y KAPITAL": [
        "BATERIA INVERSOR HUAN TAI", "BATERIA INVERSOR", "HUAN TAI", "KIT BATERIA",
        "PANEL SOLAR BIFACIAL", "PANEL SOLAR",
        "CONGELADOR HORIZONTAL MILEXUS", "CONGELADOR HORIZONTAL ROYAL",
        "CONGELADOR MILEXUS", "CONGELADOR ROYAL", "CONGELADOR",
        "EXHIBIDOR VERTICAL ICOOL", "EXHIBIDOR ICOOL", "EXHIBIDOR",
        "DETERGENTE KAPITAL",
    ],
}

ALL_GROUPS = list(PRODUCT_GROUPS_KEYWORDS.keys())

GROUP_BG_COLORS = {
    "PARRANDA":             "#1F4E78",
    "IMPORTACIONES":        "#375623",
    "CONSIGNACION":         "#7B3900",
    "TECNOLOGIA Y KAPITAL": "#4A1080",
}

GROUP_CHART_COLORS = {
    "PARRANDA":             "#4F81BD",
    "IMPORTACIONES":        "#70AD47",
    "CONSIGNACION":         "#FF9900",
    "TECNOLOGIA Y KAPITAL": "#7030A0",
}

# Paleta de 24 colores distintos para rebanadas individuales de pie charts
SLICE_PALETTE = [
    "#4472C4", "#ED7D31", "#A9D18E", "#FFC000", "#5B9BD5",
    "#70AD47", "#FF0000", "#7030A0", "#00B0F0", "#FF6384",
    "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40",
    "#C9CBCF", "#7B68EE", "#FFA07A", "#20B2AA", "#FF6B6B",
    "#48CAE4", "#52B788", "#F4A261", "#E9C46A",
]


def pie_points(n: int) -> list:
    return [{"fill": {"color": SLICE_PALETTE[i % len(SLICE_PALETTE)]}} for i in range(n)]


def detect_product_group(group_val: str, merc_val: str) -> str:
    t_g = str(group_val).upper().strip()
    t_m = str(merc_val).upper().strip()
    if "PROCOVAR" in t_g or "PARRANDA" in t_g:
        return "PARRANDA"
    if "IMPORT" in t_g:
        return "IMPORTACIONES"
    if "CONSIGN" in t_g:
        return "CONSIGNACION"
    if "TECNOLOG" in t_g or "KAPITAL" in t_g:
        return "TECNOLOGIA Y KAPITAL"
    for group, keywords in PRODUCT_GROUPS_KEYWORDS.items():
        for kw in keywords:
            if kw in t_m:
                return group
    return "OTRO"


file_in = "RV JUNIO 1-19.xls"
_engine = "xlrd" if file_in.lower().endswith(".xls") else "openpyxl"


# --- FUNCIONES DE LIMPIEZA ---
def normalize_text(s):
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('utf-8').upper()
    return " ".join(s.split())


def extract_vendor_segment(obs_val: str) -> str:
    txt = str(obs_val) if obs_val else ""
    m = re.search(r'\bV[-:]\s*([^;]+)', txt, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return txt


def detect_gestor(obs):
    txt = normalize_text(extract_vendor_segment(str(obs) if obs else ""))
    for g in ALLOWED_GESTORES:
        if g in txt:
            return g
    for alias, formal in ALIAS_MAP.items():
        if alias in txt:
            return formal
    return "OTRO"


# --- PROCESAMIENTO DE DATOS ---
df = pd.read_excel(file_in, header=3, engine=_engine)
df.columns = [str(c).strip() for c in df.columns]

df["Fecha/Hora"] = pd.to_datetime(df["Fecha/Hora"], errors="coerce")
valid_dates = df["Fecha/Hora"].dropna()
start_date = valid_dates.min().date() if not valid_dates.empty else date.today()
end_date = valid_dates.max().date() if not valid_dates.empty else date.today()

weekmask = "1111100" if not TRABAJA_SABADO else "1111110"
ultimo_dia_mes = date(end_date.year, end_date.month, calendar.monthrange(end_date.year, end_date.month)[1])
dias_laborales_totales = len(pd.bdate_range(start=FECHA_INICIO_LABORAL, end=ultimo_dia_mes, freq="C", weekmask=weekmask))
dias_laborales_transcurridos = len(pd.bdate_range(start=FECHA_INICIO_LABORAL, end=end_date, freq="C", weekmask=weekmask))
dias_laborales_transcurridos = max(1, dias_laborales_transcurridos)
dias_restantes = max(1, dias_laborales_totales - dias_laborales_transcurridos)

group_col = next((c for c in df.columns if "grupo" in c.lower()), df.columns[1])
product_col = next((c for c in df.columns if "merc" in c.lower()), df.columns[2])
gestor_col = next((c for c in df.columns if "nota" in c.lower()), df.columns[6])
metric = next((m for m in ["Importe", "Suma Total", "Total"] if m in df.columns), df.columns[-1])
qcol = next((c for c in df.columns if any(x in c.lower() for x in ["cant", "unid"])), "Cantidad")

df["gestor_norm"] = df[gestor_col].apply(detect_gestor)
df["product_clean"] = df[product_col].astype(str).str.strip()
df[metric] = pd.to_numeric(df[metric], errors="coerce").fillna(0)
df[qcol] = pd.to_numeric(df[qcol], errors="coerce").fillna(0)

# Clasificar cada fila en su grupo comercial
df["__GRUPO__"] = df.apply(
    lambda r: detect_product_group(str(r[group_col]), r["product_clean"]),
    axis=1,
)

# DataFrames por grupo (solo gestores permitidos)
df_valid = df[df["gestor_norm"].isin(ALLOWED_GESTORES)].copy()
group_dfs = {grp: df_valid[df_valid["__GRUPO__"] == grp].copy() for grp in ALL_GROUPS}

# Alias para la hoja Cumplimiento (metas son todas de Importaciones)
df_importaciones = group_dfs["IMPORTACIONES"]

months_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
out_filename = (
    f"Productos del {start_date.day} al {end_date.day} "
    f"de {months_es[start_date.month - 1]} de {start_date.year}.xlsx"
)


def build_resumen(df_source):
    if df_source.empty:
        return pd.DataFrame(columns=["Producto", "Total", "Cantidad"])
    r = df_source.groupby("product_clean").agg({metric: "sum", qcol: "sum"}).reset_index()
    r.columns = ["Producto", "Total", "Cantidad"]
    return r[r["Total"] != 0].sort_values("Total", ascending=False).reset_index(drop=True)


group_resumenes = {grp: build_resumen(group_dfs[grp]) for grp in ALL_GROUPS}

# --- ESCRITURA EXCEL ---
with pd.ExcelWriter(out_filename, engine="xlsxwriter") as writer:
    workbook = writer.book

    f_header_base = workbook.add_format({"bold": True, "bg_color": "#1F4E78", "font_color": "white", "border": 1})
    f_num = workbook.add_format({"num_format": "#,##0.00", "border": 1})
    f_perc = workbook.add_format({"num_format": "0.00%", "border": 1})
    f_red = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006", "border": 1, "num_format": "#,##0.00"})
    f_green = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#006100", "border": 1, "num_format": "#,##0.00"})
    f_border = workbook.add_format({"border": 1})
    f_italic = workbook.add_format({"italic": True, "font_color": "#555555"})

    group_header_fmts = {
        grp: workbook.add_format({
            "bold": True,
            "bg_color": GROUP_BG_COLORS[grp],
            "font_color": "white",
            "border": 1,
        })
        for grp in ALL_GROUPS
    }

    # =========================================================
    # 1. HOJA CUMPLIMIENTO — productos de Importaciones con meta
    # =========================================================
    ws_cumpl = workbook.add_worksheet("Cumplimiento")
    ws_cumpl.write(
        0, 0,
        f"Días: {dias_laborales_transcurridos} de {dias_laborales_totales} (Quedan {dias_restantes})",
        workbook.add_format({"bold": True}),
    )
    ws_cumpl.write(1, 0, "Grupo: IMPORTACIONES", f_italic)

    headers = ["Producto", "Meta Mes", "Venta Real", "% Cumpl.", "Debería ir", "Estado", "Prom. Diario", "Nec. x Día"]
    for i, h in enumerate(headers):
        ws_cumpl.write(3, i, h, f_header_base)

    row = 4
    for prod, meta in METAS_MENSUALES.items():
        real = df_importaciones[
            df_importaciones["product_clean"].str.contains(prod, case=False, na=False)
        ][qcol].sum()
        deberia = (meta / dias_laborales_totales) * dias_laborales_transcurridos
        delta = real - deberia
        ws_cumpl.write(row, 0, prod, f_border)
        ws_cumpl.write(row, 1, meta, f_num)
        ws_cumpl.write(row, 2, real, f_num)
        ws_cumpl.write(row, 3, (real / meta if meta > 0 else 0), f_perc)
        ws_cumpl.write(row, 4, deberia, f_num)
        ws_cumpl.write(row, 5, delta, f_green if delta >= 0 else f_red)
        ws_cumpl.write(row, 6, (real / dias_laborales_transcurridos), f_num)
        ws_cumpl.write(row, 7, max(0, (meta - real) / dias_restantes), f_num)
        row += 1

    ws_cumpl.set_column("A:H", 15)

    # =========================================================
    # 2. HOJA RESUMEN GLOBAL — 4 secciones, una por grupo
    # =========================================================
    ws_res = workbook.add_worksheet("Resumen")
    cur_res = 0

    for grp in ALL_GROUPS:
        resumen = group_resumenes[grp]
        hfmt = group_header_fmts[grp]

        ws_res.write(cur_res, 0, f"Resumen Global — {grp}", hfmt)
        cur_res += 1

        if not resumen.empty:
            resumen.to_excel(writer, sheet_name="Resumen", index=False, startrow=cur_res)
            for j, col_name in enumerate(resumen.columns):
                ws_res.write(cur_res, j, col_name, hfmt)

            if len(resumen) > 1:
                chart = workbook.add_chart({"type": "pie"})
                chart.add_series({
                    "name": f"Ventas {grp}",
                    "categories": ["Resumen", cur_res + 1, 0, cur_res + len(resumen), 0],
                    "values":     ["Resumen", cur_res + 1, 1, cur_res + len(resumen), 1],
                    "data_labels": {
                        "percentage": True,
                        "position": "outside_end",
                    },
                    "points": pie_points(len(resumen)),
                })
                chart.set_size({"width": 600, "height": 400})
                chart.set_legend({"position": "right"})
                ws_res.insert_chart(f"E{cur_res + 1}", chart)

            cur_res += len(resumen) + 1
        else:
            ws_res.write(cur_res, 0, "(Sin datos)", f_border)
            cur_res += 1

        cur_res += 3  # espacio entre grupos

    ws_res.set_column("A:A", 45)
    ws_res.set_column("B:D", 16)

    # =========================================================
    # 3. HOJAS POR GESTOR — 4 secciones por gestor
    # =========================================================
    for g in ALLOWED_GESTORES:
        # Solo crear hoja si el gestor tiene al menos un dato en algún grupo
        if all(
            group_dfs[grp][group_dfs[grp]["gestor_norm"] == g].empty
            for grp in ALL_GROUPS
        ):
            continue

        ws_g = workbook.add_worksheet(g[:31])
        cur_g = 0

        for grp in ALL_GROUPS:
            df_g_grp = build_resumen(group_dfs[grp][group_dfs[grp]["gestor_norm"] == g])
            hfmt = group_header_fmts[grp]

            ws_g.write(cur_g, 0, f"{grp} — {g}", hfmt)
            cur_g += 1

            if not df_g_grp.empty:
                df_g_grp.to_excel(writer, sheet_name=ws_g.name, index=False, startrow=cur_g)
                for j, col_name in enumerate(df_g_grp.columns):
                    ws_g.write(cur_g, j, col_name, hfmt)

                if len(df_g_grp) > 1:
                    ch = workbook.add_chart({"type": "pie"})
                    ch.add_series({
                        "name": f"{grp} {g}",
                        "categories": [ws_g.name, cur_g + 1, 0, cur_g + len(df_g_grp), 0],
                        "values":     [ws_g.name, cur_g + 1, 1, cur_g + len(df_g_grp), 1],
                        "data_labels": {
                            "percentage": True,
                            "position": "outside_end",
                        },
                        "points": pie_points(len(df_g_grp)),
                    })
                    ch.set_size({"width": 600, "height": 400})
                    ch.set_legend({"position": "right"})
                    ws_g.insert_chart(f"E{cur_g + 1}", ch)

                cur_g += len(df_g_grp) + 1
            else:
                ws_g.write(cur_g, 0, "(Sin datos)", f_border)
                cur_g += 1

            cur_g += 3  # espacio entre grupos

        ws_g.set_column("A:A", 45)
        ws_g.set_column("B:D", 16)

print("Proceso completado. Archivo:", out_filename)
