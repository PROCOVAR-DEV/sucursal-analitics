import pandas as pd

import re, unicodedata

from datetime import datetime



# =========================

# CONFIGURACION

# =========================

INPUT_FILE = "RV JUNIO 1-19.xls"  # Cambia si corresponde (xlsx/xls)

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



# Multiplicadores por tamaño para Hectolitros (electrolitros)

SIZE_MULT = {"330": 0.02, "500": 0.03, "1500": 0.09}



# Clasificacion de todos los productos por grupo comercial

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

GRP_BAR_COLORS = {

    "PARRANDA":             ("#4F81BD", "#2F5597"),

    "IMPORTACIONES":        ("#70AD47", "#38761D"),

    "CONSIGNACION":         ("#FF9900", "#CC7A00"),

    "TECNOLOGIA Y KAPITAL": ("#7030A0", "#4A1080"),

    "OTRO":                 ("#A0A0A0", "#808080"),

}



# Factores de unidades por Pallet

UNITS_PER_PALLET = {

    ("MALTA", "330"): 496,

    ("PARRANDA", "330"): 496,

    ("MALTA", "500"): 336,

    ("PARRANDA", "500"): 336,

    ("MALTA", "1500"): 110,

    ("PARRANDA", "1500"): 110,

}



# METAS (referencia supervisor)

META_DINERO = 350000.0

META_HECTOLITROS = 1829.0



# Metas individuales por gestor (hectolitros)

GESTOR_METAS = {

    "ALEXANDER": 260,

    "DEYANIRA": 352,

    "GEORLIS": 260,

    "JEAN MICHEL": 260,

    "ERNESTO": 211,

    "ANDY": 211,

    "MAYLEN": 260,

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

        # comparamos alias sin espacios contra texto sin espacios

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





def is_malta(text: str) -> bool:

    t = str(text).upper()

    return "MALTA" in t and "GUAJIRA" in t





def is_parranda(text: str) -> bool:

    t = str(text).upper()

    return "PARRANDA" in t





def detect_product_group(grupo_val: str, merc_val: str) -> str:

    """Clasifica una transaccion en su grupo comercial."""

    t_g = str(grupo_val).upper().strip() if grupo_val else ""

    t_m = str(merc_val).upper().strip() if merc_val else ""

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



def smart_to_numeric(series):

    if pd.api.types.is_numeric_dtype(series):

        return series

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

    return round(

        float(sub.loc[mask & (sub["Hectolitros_SIZE"] == size), "Hectolitros"].sum()), 2

    )





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

col_merc = find_col(cols, ["Mercancía"]) or find_col(cols, ["Mercancia"])

col_cant = find_col(cols, ["Cant"])

col_importe = find_col(cols, ["Importe"])

col_fecha = find_col(cols, ["Fecha"])

col_op = find_col(cols, ["No.", "Operación"]) or find_col(cols, ["Operación"])

col_sumat = find_col(cols, ["Suma", "Total"])

col_grupo = find_col(cols, ["Grupo"])  # "Grupo de la Mercancía" (PARRANDA/CES)



if col_cant in df.columns:

    df[col_cant] = smart_to_numeric(df[col_cant])

if col_importe in df.columns:

    df[col_importe] = smart_to_numeric(df[col_importe]).round(2)

if col_sumat in df.columns:

    df[col_sumat] = smart_to_numeric(df[col_sumat]).round(2)

if col_fecha in df.columns:

    df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")

if col_op in df.columns:

    df[col_op] = pd.to_numeric(df[col_op], errors="coerce").astype("Int64")



# Gestor

df["__GESTOR__"] = (

    df[col_obs].apply(detect_gestor_from_obs) if col_obs in df.columns else None

)

df = df[df["__GESTOR__"].isin(GESTORES_PERMITIDOS)].copy()



# Tamaño y producto

df["Hectolitros_SIZE"] = (

    df[col_merc].apply(detect_size) if col_merc in df.columns else None

)

df["__IS_MALTA__"] = df[col_merc].apply(is_malta) if col_merc in df.columns else False

df["__IS_PARRANDA__"] = (

    df[col_merc].apply(is_parranda) if col_merc in df.columns else False

)



# Grupo comercial para mix de ventas

df["__GRUPO__"] = df.apply(

    lambda r: detect_product_group(

        r.get(col_grupo, "") if col_grupo else "",

        r.get(col_merc, "") if col_merc else "",

    ),

    axis=1,

)



# Hectolitros

mult_series = df["Hectolitros_SIZE"].map(SIZE_MULT).fillna(0)

if col_cant in df.columns:

    df["Hectolitros"] = (df[col_cant].fillna(0) * mult_series).round(2)

else:

    df["Hectolitros"] = 0.00



# Columnas a exportar (del No. de Operación a Suma Total) + Hectolitros al final

if col_op in df.columns and col_sumat in df.columns:

    cols_list = list(df.columns)

    start_idx = cols_list.index(col_op)

    end_idx = cols_list.index(col_sumat)

    export_cols = cols_list[start_idx : end_idx + 1]

else:

    export_cols = list(df.columns)

aux_cols = [

    "__GESTOR__",

    "Hectolitros_SIZE",

    "__IS_MALTA__",

    "__IS_PARRANDA__",

    col_obs,

]

export_cols = [c for c in export_cols if c not in aux_cols]

if "Hectolitros" not in export_cols:

    export_cols.append("Hectolitros")



# Nombre de salida y rango de fechas

if col_fecha in df.columns and not df[col_fecha].isna().all():

    fmin, fmax = df[col_fecha].min(), df[col_fecha].max()

    OUT_FILE = f"VENTAS-{fmin.day:02d}-{fmax.day:02d}-{MESES_ES.get(fmin.month,'MES')}-{fmin.year}.xlsx"

    rango_fechas_str = f"{fmin.strftime('%d-%m-%Y')} a {fmax.strftime('%d-%m-%Y')}"

else:

    OUT_FILE = f"VENTAS_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"

    rango_fechas_str = "Rango de fechas no disponible"



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

color_header = "#1F4E79"

color_band = "#D9E1F2"

color_block = "#FCE4D6"

color_kpi = "#E2EFDA"

color_title = "#203864"

border_thin = 1



fmt_header = wb.add_format(

    {

        "bold": True,

        "font_color": "white",

        "bg_color": color_header,

        "border": border_thin,

        "align": "center",

    }

)

fmt_num = wb.add_format({"num_format": "0.00"})

fmt_int = wb.add_format({"num_format": "0"})

fmt_band = wb.add_format({"bg_color": color_band})

fmt_block = wb.add_format(

    {"bg_color": color_block, "border": border_thin, "bold": True, "num_format": "0.00"}

)

fmt_block_text = wb.add_format(

    {"bg_color": color_block, "border": border_thin, "bold": True}

)

fmt_kpi = wb.add_format(

    {

        "bg_color": color_kpi,

        "border": border_thin,

        "bold": True,

        "num_format": "#,##0.00",

    }

)

fmt_kpi_text = wb.add_format(

    {"bg_color": color_kpi, "border": border_thin, "bold": True}

)

fmt_big_title = wb.add_format(

    {

        "bold": True,

        "font_size": 16,

        "font_color": "white",

        "align": "left",

        "valign": "vcenter",

        "bg_color": color_title,

    }

)

fmt_subtitle = wb.add_format(

    {

        "italic": True,

        "font_color": "white",

        "align": "right",

        "valign": "vcenter",

        "bg_color": color_title,

    }

)

fmt_small = wb.add_format({"font_size": 9})



percent_fmt_center = wb.add_format(

    {"num_format": "0%", "align": "center", "valign": "vcenter"}

)

percent_hidden = wb.add_format(

    {"num_format": ";;;"}

)  # oculta número dentro de la barra





def autosize_worksheet(ws, df_like, header_fmt):

    for col_idx, col_name in enumerate(df_like.columns):

        max_len = max(

            [len(str(col_name))]

            + [len(str(x)) for x in df_like[col_name].astype(str).values[:500]]

        )

        width = min(max(10, max_len + 2), 60)

        ws.set_column(col_idx, col_idx, width)

    ws.set_row(0, 20, header_fmt)





def apply_bands(ws, start_row, end_row, start_col, end_col, band_fmt):

    for r in range(start_row, end_row + 1):

        if (r - start_row) % 2 == 1:

            ws.set_row(r, None, band_fmt)





# =========================

# Hojas por Gestor

# =========================

supervisor_rows = []



for gestor in GESTORES_PERMITIDOS:

    sub = df[df["__GESTOR__"] == gestor].copy()

    sub = sort_df(sub, col_fecha, col_merc)



    total_importe = round(

        float(sub[col_importe].sum()) if col_importe in sub.columns else 0.0, 2

    )



    # Hectolitros por categoría/tamaño

    M330 = sum_hectolitros(sub, sub["__IS_MALTA__"], "330")

    M500 = sum_hectolitros(sub, sub["__IS_MALTA__"], "500")

    M1500 = sum_hectolitros(sub, sub["__IS_MALTA__"], "1500")

    P330 = sum_hectolitros(sub, sub["__IS_PARRANDA__"], "330")

    P500 = sum_hectolitros(sub, sub["__IS_PARRANDA__"], "500")

    P1500 = sum_hectolitros(sub, sub["__IS_PARRANDA__"], "1500")



    total_hecto = round(M330 + M500 + M1500 + P330 + P500 + P1500, 2)



    # NETAS y descuentos (netas = 1% comisión gestor)

    netas = round(total_importe * 0.01, 2)

    descuento_supervisor = round(netas * 0.10, 2)

    comision_real = round(

        netas - descuento_supervisor, 2

    )  # se mantiene para cálculo interno, no se muestra



    # Datos principales a escribir

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

        if c == col_op:

            ws.set_column(idx, idx, None, fmt_int)

        elif pd.api.types.is_numeric_dtype(to_write[c]):

            ws.set_column(idx, idx, None, fmt_num)



    if len(to_write) > 0:

        apply_bands(ws, 1, len(to_write), 0, len(to_write.columns) - 1, fmt_band)



    last_row = len(to_write)

    last_col = len(to_write.columns) - 1

    if len(to_write) >= 1:

        tabla_name = "Tabla_" + gestor.replace(" ", "")[:20]

        ws.add_table(

            0,

            0,

            last_row,

            last_col,

            {

                "name": tabla_name,

                "style": "Table Style Medium 2",

                "columns": [{"header": h} for h in to_write.columns],

            },

        )



    # KPIs limpios: solo Ventas y Comisión (1%) que ganan los gestores

    kpi_row = len(to_write) + 2

    ws.write(kpi_row, 0, "VENTAS", fmt_block_text)

    ws.write_number(kpi_row, 1, total_importe, fmt_block)

    ws.write(kpi_row + 1, 0, "COMISIÓN", fmt_block_text)

    ws.write_number(kpi_row + 1, 1, comision_real, fmt_block)  # Aquí netas = 1%



    # Aquí escribimos Total Hectolitros y al lado el % de cumplimiento de la meta individual

    meta_gestor = GESTOR_METAS.get(gestor, META_HECTOLITROS)

    cumplimiento_hecto_gestor = 0.0 if meta_gestor == 0 else (total_hecto / meta_gestor)



    ws.write(kpi_row + 3, 0, "Total Hectolitros", fmt_block_text)

    ws.write_number(kpi_row + 3, 1, total_hecto, fmt_block)

    ws.write(kpi_row + 3, 3, cumplimiento_hecto_gestor, percent_fmt_center)  # % al lado



    # ========= Bloque 1: Mix de Ventas por Grupo Comercial =========

    grp_row = kpi_row + 7

    ws.merge_range(grp_row, 0, grp_row, 5, "Mix de Ventas por Grupo Comercial", fmt_kpi_text)

    tot_gestor = float(sub[col_importe].sum()) if col_importe in sub.columns else 0.0

    for _i, _grp in enumerate(ALL_GROUPS):

        _bar_color, _border_color = GRP_BAR_COLORS.get(_grp, GRP_BAR_COLORS["OTRO"])

        _g_total = (

            round(float(sub.loc[sub["__GRUPO__"] == _grp, col_importe].sum()), 2)

            if col_importe in sub.columns else 0.0

        )

        _pct_grp = 0.0 if tot_gestor == 0 else _g_total / tot_gestor

        _r_off = grp_row + 2 + _i

        ws.write(_r_off, 0, _grp, fmt_block_text)

        ws.merge_range(_r_off, 1, _r_off, 3, _pct_grp, percent_hidden)

        ws.write(_r_off, 4, _pct_grp, percent_fmt_center)

        ws.write(_r_off, 5, _g_total, fmt_num)

        ws.conditional_format(_r_off, 1, _r_off, 3, {

            "type": "data_bar",

            "bar_color": _bar_color,

            "min_type": "num",

            "min_value": 0,

            "max_type": "num",

            "max_value": 1,

            "bar_only": True,

            "bar_border_color": _border_color,

        })

    ws.set_column(0, 0, 14)

    ws.set_column(1, 3, 20)

    ws.set_column(4, 4, 10)

    ws.set_column(5, 5, 14)



    # ========= Bloque 2: Blisters y Pallets por Producto/Tamaño =========

    conv_row = grp_row + 8

    ws.merge_range(

        conv_row,

        0,

        conv_row,

        6,

        "Conversión de Cantidad a Blisters y Pallets por Producto",

        fmt_kpi_text,

    )



    # Prepara agregación

    sub["_SIZE_"] = sub["Hectolitros_SIZE"].fillna("")

    sub["_PROD_"] = sub.apply(

        lambda r: (

            "MALTA"

            if r["__IS_MALTA__"]

            else ("PARRANDA" if r["__IS_PARRANDA__"] else "")

        ),

        axis=1,

    )



    # Filtramos solo Malta/Parranda y tamaños conocidos

    conv = sub[

        (sub["_PROD_"] != "") & (sub["_SIZE_"].isin(["330", "500", "1500"]))

    ].copy()

    if col_cant in conv.columns:

        conv["Blisters"] = conv[col_cant].fillna(0.0)

    else:

        conv["Blisters"] = 0.0



    # Pallets = Blisters / unidades_por_pallet

    def calc_pallets(row):

        key = (row["_PROD_"], row["_SIZE_"])

        units = UNITS_PER_PALLET.get(key, None)

        if not units or units == 0:

            return 0.0

        return float(row["Blisters"]) / float(units)



    conv["Pallets"] = conv.apply(calc_pallets, axis=1)



    # Resumen por filas requeridas

    def sum_cond(prod, size, col):

        m = (conv["_PROD_"] == prod) & (conv["_SIZE_"] == size)

        return round(float(conv.loc[m, col].sum()), 2)



    rows = [

        (

            "Malta",

            "330",

            sum_cond("MALTA", "330", "Blisters"),

            sum_cond("MALTA", "330", "Pallets"),

            M330,

        ),

        (

            "Malta",

            "500",

            sum_cond("MALTA", "500", "Blisters"),

            sum_cond("MALTA", "500", "Pallets"),

            M500,

        ),

        (

            "Malta",

            "1500",

            sum_cond("MALTA", "1500", "Blisters"),

            sum_cond("MALTA", "1500", "Pallets"),

            M1500,

        ),

        (

            "Parranda",

            "330",

            sum_cond("PARRANDA", "330", "Blisters"),

            sum_cond("PARRANDA", "330", "Pallets"),

            P330,

        ),

        (

            "Parranda",

            "500",

            sum_cond("PARRANDA", "500", "Blisters"),

            sum_cond("PARRANDA", "500", "Pallets"),

            P500,

        ),

        (

            "Parranda",

            "1500",

            sum_cond("PARRANDA", "1500", "Blisters"),

            sum_cond("PARRANDA", "1500", "Pallets"),

            P1500,

        ),

    ]

    conv_df = pd.DataFrame(

        rows, columns=["Producto", "Tamaño", "Blisters", "Pallets", "Hectolitros"]

    )



    # Escribir tabla ordenada y formateada

    start_r = conv_row + 2

    start_c = 0

    conv_df.to_excel(

        writer, sheet_name=sheet_name, index=False, startrow=start_r, startcol=start_c

    )

    # Encabezado de la subtabla

    for j, coln in enumerate(conv_df.columns):

        ws.write(start_r, start_c + j, coln, fmt_header)



    # Formatos

    for j, coln in enumerate(conv_df.columns):

        colx = start_c + j

        if coln in ("Blisters", "Pallets", "Hectolitros"):

            ws.set_column(colx, colx, 12, fmt_num)

        elif coln == "Producto":

            ws.set_column(colx, colx, 14)

        elif coln == "Tamaño":

            ws.set_column(colx, colx, 10)



    # Banding de esa subtabla

    if len(conv_df) > 0:

        apply_bands(

            ws,

            start_r + 1,

            start_r + len(conv_df),

            start_c,

            start_c + len(conv_df.columns) - 1,

            fmt_band,

        )



    # Tabla con estilo

    ws.add_table(

        start_r,

        start_c,

        start_r + len(conv_df),

        start_c + len(conv_df.columns) - 1,

        {

            "name": f"TablaConv_{gestor.replace(' ','')[:15]}",

            "style": "Table Style Medium 9",

            "columns": [{"header": h} for h in conv_df.columns],

        },

    )



    # Guardar para Supervisor

    _grp_ventas = {

        grp: round(

            float(sub.loc[sub["__GRUPO__"] == grp, col_importe].sum())

            if col_importe in sub.columns else 0.0,

            2,

        )

        for grp in ALL_GROUPS

    }

    supervisor_rows.append(

        {

            "Gestor": gestor,

            "Total Venta": total_importe,

            "Comisión Gestor": netas,

            "PARRANDA $": _grp_ventas.get("PARRANDA", 0.0),

            "IMPORTACIONES $": _grp_ventas.get("IMPORTACIONES", 0.0),

            "CONSIGNACION $": _grp_ventas.get("CONSIGNACION", 0.0),

            "TECNOLOGIA $": _grp_ventas.get("TECNOLOGIA Y KAPITAL", 0.0),

            "M330": M330,

            "M500": M500,

            "M1500": M1500,

            "P330": P330,

            "P500": P500,

            "P1500": P1500,

            "Total Hectolitros": total_hecto,

        }

    )



# =========================

# Hoja Supervisor (igual a la versión anterior mejorada)

# =========================

super_df = pd.DataFrame(supervisor_rows)

super_df = super_df[

    [

        "Gestor",

        "Total Venta",

        "Comisión Gestor",

        "PARRANDA $",

        "IMPORTACIONES $",

        "CONSIGNACION $",

        "TECNOLOGIA $",

        "M330",

        "M500",

        "M1500",

        "P330",

        "P500",

        "P1500",

        "Total Hectolitros",

    ]

]



super_df.to_excel(writer, sheet_name="Supervisor", index=False, startrow=5)

ws = writer.sheets["Supervisor"]



ws.merge_range(0, 0, 1, 7, "Resumen de Ventas - Supervisor", fmt_big_title)

ws.merge_range(0, 8, 1, 11, f"Periodo: {rango_fechas_str}", fmt_subtitle)

ws.set_row(0, 28)

ws.set_row(1, 20)

ws.freeze_panes(6, 0)

autosize_worksheet(ws, super_df, fmt_header)



if len(super_df) > 0:

    apply_bands(ws, 7, 6 + len(super_df), 0, len(super_df.columns) - 1, fmt_band)



if len(super_df) >= 1:

    ws.add_table(

        5,

        0,

        5 + len(super_df),

        len(super_df.columns) - 1,

        {

            "name": "Tabla_Supervisor",

            "style": "Table Style Medium 9",

            "columns": [{"header": h} for h in super_df.columns],

        },

    )



total_ventas = round(float(super_df["Total Venta"].sum()), 2)

total_comision_gestores = round(float(super_df["Comisión Gestor"].sum()), 2)

comision_supervisor = round(total_comision_gestores * 0.10, 2)



kpi_start_row = 3

ws.merge_range(kpi_start_row, 0, kpi_start_row, 2, "VENTAS TOTALES", fmt_kpi_text)

ws.merge_range(

    kpi_start_row, 3, kpi_start_row, 5, "TOTAL COMISIÓN GESTORES", fmt_kpi_text

)

ws.merge_range(kpi_start_row, 6, kpi_start_row, 8, "COMISIÓN SUPERVISOR", fmt_kpi_text)



ws.merge_range(kpi_start_row + 1, 0, kpi_start_row + 1, 2, total_ventas, fmt_kpi)

ws.merge_range(

    kpi_start_row + 1, 3, kpi_start_row + 1, 5, total_comision_gestores, fmt_kpi

)

ws.merge_range(kpi_start_row + 1, 6, kpi_start_row + 1, 8, comision_supervisor, fmt_kpi)



# ============================================================================

# BLOQUE FINAL DE RESUMEN Y METAS (Reemplaza desde aquí hasta el final)

# ============================================================================



prod_row = 8 + len(super_df) + 2



# 1. TOTAL M330 (Fila base)

ws.merge_range(prod_row, 0, prod_row, 2, "TOTAL M330", fmt_block_text)

ws.merge_range(

    prod_row, 3, prod_row, 5, round(float(super_df["M330"].sum()), 2), fmt_block

)



# 2. TOTAL M500 (Fila base + 1)

ws.merge_range(prod_row + 1, 0, prod_row + 1, 2, "TOTAL M500", fmt_block_text)

ws.merge_range(

    prod_row + 1, 3, prod_row + 1, 5, round(float(super_df["M500"].sum()), 2), fmt_block

)



# 3. TOTAL M1500 (Fila base + 2)

ws.merge_range(prod_row + 2, 0, prod_row + 2, 2, "TOTAL M1500", fmt_block_text)

ws.merge_range(

    prod_row + 2,

    3,

    prod_row + 2,

    5,

    round(float(super_df["M1500"].sum()), 2),

    fmt_block,

)



# 4. TOTAL P330 (Fila base + 3)

ws.merge_range(prod_row + 3, 0, prod_row + 3, 2, "TOTAL P330", fmt_block_text)

ws.merge_range(

    prod_row + 3, 3, prod_row + 3, 5, round(float(super_df["P330"].sum()), 2), fmt_block

)



# 5. TOTAL P500 (Fila base + 4)

ws.merge_range(prod_row + 4, 0, prod_row + 4, 2, "TOTAL P500", fmt_block_text)

ws.merge_range(

    prod_row + 4, 3, prod_row + 4, 5, round(float(super_df["P500"].sum()), 2), fmt_block

)



# 6. TOTAL P1500 (Fila base + 5)

ws.merge_range(prod_row + 5, 0, prod_row + 5, 2, "TOTAL P1500", fmt_block_text)

ws.merge_range(

    prod_row + 5,

    3,

    prod_row + 5,

    5,

    round(float(super_df["P1500"].sum()), 2),

    fmt_block,

)



# 7. TOTAL HECTOLITROS (Fila base + 6)

total_hecto_visible = round(float(super_df["Total Hectolitros"].sum()), 2)

ws.merge_range(prod_row + 6, 0, prod_row + 6, 2, "TOTAL HECTOLITROS", fmt_block_text)

ws.merge_range(prod_row + 6, 3, prod_row + 6, 5, total_hecto_visible, fmt_block)





# ============================================================================

# SECCIÓN DE METAS (Más abajo para no chocar)

# ============================================================================



# Dejamos espacio suficiente: prod_row + 9

meta_row = prod_row + 9



ws.merge_range(meta_row, 0, meta_row, 2, "META DINERO", fmt_block_text)

ws.merge_range(meta_row, 3, meta_row, 5, META_DINERO, fmt_block)



ws.merge_range(meta_row + 1, 0, meta_row + 1, 2, "META HECTOLITROS", fmt_block_text)

ws.merge_range(meta_row + 1, 3, meta_row + 1, 5, META_HECTOLITROS, fmt_block)



# Cálculos de cumplimiento

cumpl_dinero = 0.0 if META_DINERO == 0 else (total_ventas / META_DINERO)

cumpl_hecto = 0.0 if META_HECTOLITROS == 0 else (total_hecto_visible / META_HECTOLITROS)



# Visualización Metas (% y Barra)

ws.merge_range(meta_row, 6, meta_row, 7, "% CUMPL. DINERO", fmt_kpi_text)

ws.merge_range(meta_row, 8, meta_row, 10, cumpl_dinero, percent_hidden)

ws.write(meta_row, 11, cumpl_dinero, percent_fmt_center)



ws.merge_range(meta_row + 1, 6, meta_row + 1, 7, "% CUMPL. HECTO", fmt_kpi_text)

ws.merge_range(meta_row + 1, 8, meta_row + 1, 10, cumpl_hecto, percent_hidden)

ws.write(meta_row + 1, 11, cumpl_hecto, percent_fmt_center)



# Formato Condicional (Barras de progreso)

ws.conditional_format(

    meta_row,

    8,

    meta_row,

    10,

    {

        "type": "data_bar",

        "bar_color": "#4F81BD",

        "min_type": "num",

        "min_value": 0,

        "max_type": "num",

        "max_value": 1,

        "bar_only": True,

        "bar_border_color": "#2F5597",

    },

)

ws.conditional_format(

    meta_row + 1,

    8,

    meta_row + 1,

    10,

    {

        "type": "data_bar",

        "bar_color": "#70AD47",

        "min_type": "num",

        "min_value": 0,

        "max_type": "num",

        "max_value": 1,

        "bar_only": True,

        "bar_border_color": "#38761D",

    },

)



# Ajuste final de anchos de columna

for c in range(0, 16):

    ws.set_column(c, c, 14)

ws.set_column(0, 0, 18)

ws.set_row(5, 22)



writer.close()

print(f"✓ Archivo generado: {OUT_FILE}")