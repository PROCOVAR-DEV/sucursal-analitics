"""Carga y normalización del archivo 'Reporte de Venta'.

Soporta DOS formatos:
  A) Multi-hoja: una hoja por gestor (ALEXANDER, DEYANIRA, GEORLIS, JEAN MICHEL,
     JELEN, MAYLEN) + una hoja "Supervisor" consolidada. Sin columna "Nota":
     el gestor se toma del nombre de la hoja.
  B) Mono-hoja legacy con columna "Nota": el gestor se detecta desde la nota.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd

from core.utils import (
    detect_gestor,
    detect_gestor_punto,
    detect_size,
    find_col,
    is_malta,
    is_parranda,
    smart_to_numeric,
)
from core.constants import GESTORES_PERMITIDOS, SIZE_MULT


@dataclass
class ReportData:
    """Resultado normalizado del reporte de venta."""
    df: pd.DataFrame
    date_min: pd.Timestamp | None
    date_max: pd.Timestamp | None
    filename: str

    @property
    def rango_str(self) -> str:
        if self.date_min is None or self.date_max is None:
            return "Rango no disponible"
        return f"{self.date_min.strftime('%d/%m/%Y')} - {self.date_max.strftime('%d/%m/%Y')}"


# Nombres estándar usados en todo el backend
STD_COLS = {
    "op":      "Operacion",
    "fecha":   "Fecha",
    "socio":   "Socio",
    "merc":    "Mercancia",
    "grupo":   "Grupo",
    "cant":    "Cantidad",
    "importe": "Importe",
    "suma":    "SumaTotal",
    "nota":    "Nota",
}


def _engine_for(filename: str) -> str | None:
    return "xlrd" if filename.lower().endswith(".xls") else None


def _find_header_row(raw: pd.DataFrame) -> int:
    for i in range(min(30, len(raw))):
        row_vals = [str(v).strip() for v in raw.iloc[i].tolist()]
        has_op    = any("Operaci" in v for v in row_vals)
        has_fecha = any("Fecha" in v for v in row_vals)
        if has_op and has_fecha:
            return i
    return 0


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    cols = df.columns
    mapping = {
        find_col(cols, ["No.", "Operación"]) or find_col(cols, ["Operación"]) or find_col(cols, ["Operaci"]): STD_COLS["op"],
        find_col(cols, ["Fecha", "Hora"]) or find_col(cols, ["Fecha"]):         STD_COLS["fecha"],
        find_col(cols, ["socio"]) or find_col(cols, ["Nombre"]):                STD_COLS["socio"],
        find_col(cols, ["Mercancía"]) or find_col(cols, ["Mercancia"]):         STD_COLS["merc"],
        find_col(cols, ["Grupo"]):                                              STD_COLS["grupo"],
        find_col(cols, ["Cant"]):                                               STD_COLS["cant"],
        find_col(cols, ["Importe"]):                                            STD_COLS["importe"],
        find_col(cols, ["Suma", "Total"]):                                      STD_COLS["suma"],
        find_col(cols, ["Nota"]):                                               STD_COLS["nota"],
    }
    mapping = {k: v for k, v in mapping.items() if k is not None}
    df = df.rename(columns=mapping)
    return df


def _type_df(df: pd.DataFrame) -> pd.DataFrame:
    if STD_COLS["fecha"] in df.columns:
        fecha_series = pd.to_datetime(df[STD_COLS["fecha"]], errors="coerce")
        # Descartar fechas irreales (<2000) típicas de epoch 0 / filas de totales
        fecha_series = fecha_series.where(fecha_series.dt.year >= 2000)
        df[STD_COLS["fecha"]] = fecha_series
    for k in ("cant", "importe", "suma"):
        c = STD_COLS[k]
        if c in df.columns:
            df[c] = smart_to_numeric(df[c])
            if k != "cant":
                df[c] = df[c].round(2)
    if STD_COLS["op"] in df.columns:
        df[STD_COLS["op"]] = pd.to_numeric(df[STD_COLS["op"]], errors="coerce").astype("Int64")
    # Homogeneizar strings (evita mixtos int/str que rompen parquet)
    for key in ("socio", "merc", "grupo", "nota"):
        c = STD_COLS[key]
        if c in df.columns:
            df[c] = df[c].astype("string")
    return df


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    if "GestorDetectado" not in df.columns:
        if STD_COLS["nota"] in df.columns:
            df["GestorDetectado"] = df[STD_COLS["nota"]].apply(detect_gestor)
        else:
            df["GestorDetectado"] = None
    if STD_COLS["nota"] in df.columns:
        df["GestorPunto"] = df[STD_COLS["nota"]].apply(detect_gestor_punto)
    else:
        df["GestorPunto"] = None

    if STD_COLS["merc"] in df.columns:
        df["Size"] = df[STD_COLS["merc"]].apply(detect_size)
        df["IsMalta"] = df[STD_COLS["merc"]].apply(is_malta)
        df["IsParranda"] = df[STD_COLS["merc"]].apply(is_parranda)
    else:
        df["Size"] = None
        df["IsMalta"] = False
        df["IsParranda"] = False

    if STD_COLS["cant"] in df.columns:
        mult = df["Size"].map(SIZE_MULT).fillna(0)
        df["Hectolitros"] = (df[STD_COLS["cant"]].fillna(0) * mult).round(2)
    else:
        df["Hectolitros"] = 0.0

    # Normalizar strings de soporte para parquet
    for c in ("Size", "GestorDetectado", "GestorPunto"):
        if c in df.columns:
            df[c] = df[c].astype("string")
    return df


def _match_gestor_sheet(sheet_name: str) -> str | None:
    """Devuelve el gestor permitido cuyo nombre coincide con el de la hoja."""
    norm = " ".join(str(sheet_name).upper().split())
    for g in GESTORES_PERMITIDOS:
        if norm == g:
            return g
    # Tolerar variaciones (JEANMICHEL, Jean-Michel, etc.)
    flat = norm.replace(" ", "").replace("-", "").replace("_", "")
    for g in GESTORES_PERMITIDOS:
        if flat == g.replace(" ", ""):
            return g
    return None


def load_report(content: bytes, filename: str) -> ReportData:
    """Carga el reporte (multi-hoja o mono-hoja) y devuelve un ReportData."""
    bio = io.BytesIO(content)
    engine = _engine_for(filename)
    xl = pd.ExcelFile(bio, engine=engine)

    # ¿Multi-hoja estilo supervisor (una hoja por gestor)?
    gestor_sheets = {s: _match_gestor_sheet(s) for s in xl.sheet_names}
    gestor_sheets = {s: g for s, g in gestor_sheets.items() if g is not None}

    dfs: list[pd.DataFrame] = []
    if len(gestor_sheets) >= 2:
        for sheet, gestor in gestor_sheets.items():
            bio.seek(0)
            raw = pd.read_excel(bio, sheet_name=sheet, header=None, engine=engine)
            hdr = _find_header_row(raw)
            bio.seek(0)
            dfi = pd.read_excel(bio, sheet_name=sheet, header=hdr, engine=engine)
            dfi = _normalize_df(dfi)
            dfi["GestorDetectado"] = gestor  # viene de la hoja
            dfs.append(dfi)
    else:
        # Formato mono-hoja legacy
        bio.seek(0)
        raw = pd.read_excel(bio, header=None, engine=engine)
        hdr = _find_header_row(raw)
        bio.seek(0)
        dfi = pd.read_excel(bio, header=hdr, engine=engine)
        dfi = _normalize_df(dfi)
        dfs.append(dfi)

    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    df = _type_df(df)
    df = _enrich(df)

    # Rango de fechas
    date_min = date_max = None
    if STD_COLS["fecha"] in df.columns:
        valid = df[STD_COLS["fecha"]].dropna()
        if not valid.empty:
            date_min = valid.min()
            date_max = valid.max()

    return ReportData(df=df, date_min=date_min, date_max=date_max, filename=filename)


def only_valid_gestores(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra al DataFrame a filas con gestor detectado dentro de la lista permitida."""
    if "GestorDetectado" not in df.columns:
        return df.iloc[0:0].copy()
    return df[df["GestorDetectado"].isin(GESTORES_PERMITIDOS)].copy()


def filter_by_period(report: ReportData, mes: str | None) -> ReportData:
    """Devuelve un nuevo ReportData filtrado al mes indicado (formato YYYY-MM).
    Si mes es None devuelve el mismo reporte sin cambios."""
    if mes is None:
        return report
    try:
        year, month = int(mes[:4]), int(mes[5:7])
    except (ValueError, IndexError):
        return report
    fecha_col = STD_COLS["fecha"]
    if fecha_col not in report.df.columns:
        return report
    mask = (
        (report.df[fecha_col].dt.year == year) &
        (report.df[fecha_col].dt.month == month)
    )
    filtered = report.df[mask].copy()
    valid = filtered[fecha_col].dropna()
    return ReportData(
        df=filtered,
        date_min=valid.min() if not valid.empty else None,
        date_max=valid.max() if not valid.empty else None,
        filename=report.filename,
    )


def available_periods(report: ReportData) -> list[str]:
    """Devuelve la lista de meses disponibles en el reporte (YYYY-MM), descendente."""
    fecha_col = STD_COLS["fecha"]
    if fecha_col not in report.df.columns:
        return []
    valid = report.df[fecha_col].dropna()
    if valid.empty:
        return []
    return sorted(
        {f"{d.year}-{d.month:02d}" for d in valid},
        reverse=True,
    )
