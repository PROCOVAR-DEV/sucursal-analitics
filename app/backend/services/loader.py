"""Carga y normalización del archivo 'Reporte de Venta'.

Detecta la fila de encabezados (variable entre archivos) y devuelve un
DataFrame canónico con columnas renombradas a nombres estándar.
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


def _read_excel_auto(content: bytes, filename: str) -> pd.DataFrame:
    """Lee .xls o .xlsx desde bytes usando el engine adecuado."""
    lower = filename.lower()
    bio = io.BytesIO(content)
    if lower.endswith(".xls"):
        return pd.read_excel(bio, header=None, engine="xlrd")
    return pd.read_excel(bio, header=None)


def _read_excel_auto_header(content: bytes, filename: str, header_row: int) -> pd.DataFrame:
    lower = filename.lower()
    bio = io.BytesIO(content)
    if lower.endswith(".xls"):
        return pd.read_excel(bio, header=header_row, engine="xlrd")
    return pd.read_excel(bio, header=header_row)


def load_report(content: bytes, filename: str) -> ReportData:
    """Carga un Reporte de Venta desde bytes y devuelve un ReportData."""
    raw = _read_excel_auto(content, filename)

    # Detectar fila con "No. de Operación" y "Fecha"
    header_row = None
    for i in range(min(30, len(raw))):
        row_vals = [str(v).strip() for v in raw.iloc[i].tolist()]
        if any("Operaci" in v for v in row_vals) and any("Fecha" in v for v in row_vals):
            header_row = i
            break
    if header_row is None:
        header_row = 2

    df = _read_excel_auto_header(content, filename, header_row)
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    df.columns = [str(c).strip() for c in df.columns]

    cols = df.columns
    mapping = {
        find_col(cols, ["No.", "Operación"]) or find_col(cols, ["Operación"]): STD_COLS["op"],
        find_col(cols, ["Fecha"]):                                              STD_COLS["fecha"],
        find_col(cols, ["socio"]):                                              STD_COLS["socio"],
        find_col(cols, ["Mercancía"]) or find_col(cols, ["Mercancia"]):         STD_COLS["merc"],
        find_col(cols, ["Grupo"]):                                              STD_COLS["grupo"],
        find_col(cols, ["Cant"]):                                               STD_COLS["cant"],
        find_col(cols, ["Importe"]):                                            STD_COLS["importe"],
        find_col(cols, ["Suma", "Total"]):                                      STD_COLS["suma"],
        find_col(cols, ["Nota"]):                                               STD_COLS["nota"],
    }
    mapping = {k: v for k, v in mapping.items() if k is not None}
    df = df.rename(columns=mapping)

    # Tipado
    if STD_COLS["fecha"] in df.columns:
        df[STD_COLS["fecha"]] = pd.to_datetime(df[STD_COLS["fecha"]], errors="coerce")
    for k in ("cant", "importe", "suma"):
        c = STD_COLS[k]
        if c in df.columns:
            df[c] = smart_to_numeric(df[c])
            if k != "cant":
                df[c] = df[c].round(2)
    if STD_COLS["op"] in df.columns:
        df[STD_COLS["op"]] = pd.to_numeric(df[STD_COLS["op"]], errors="coerce").astype("Int64")

    # Enriquecimiento
    if STD_COLS["nota"] in df.columns:
        df["GestorDetectado"] = df[STD_COLS["nota"]].apply(detect_gestor)
        df["GestorPunto"] = df[STD_COLS["nota"]].apply(detect_gestor_punto)
    else:
        df["GestorDetectado"] = None
        df["GestorPunto"] = None

    if STD_COLS["merc"] in df.columns:
        df["Size"] = df[STD_COLS["merc"]].apply(detect_size)
        df["IsMalta"] = df[STD_COLS["merc"]].apply(is_malta)
        df["IsParranda"] = df[STD_COLS["merc"]].apply(is_parranda)
    else:
        df["Size"] = None
        df["IsMalta"] = False
        df["IsParranda"] = False

    # Hectolitros = Cantidad * multiplicador por tamaño
    if STD_COLS["cant"] in df.columns:
        mult = df["Size"].map(SIZE_MULT).fillna(0)
        df["Hectolitros"] = (df[STD_COLS["cant"]].fillna(0) * mult).round(2)
    else:
        df["Hectolitros"] = 0.0

    # Rango de fechas
    date_min = date_max = None
    if STD_COLS["fecha"] in df.columns and not df[STD_COLS["fecha"]].isna().all():
        date_min = df[STD_COLS["fecha"]].min()
        date_max = df[STD_COLS["fecha"]].max()

    return ReportData(df=df, date_min=date_min, date_max=date_max, filename=filename)


def only_valid_gestores(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra al DataFrame a filas con gestor detectado dentro de la lista permitida."""
    return df[df["GestorDetectado"].isin(GESTORES_PERMITIDOS)].copy()
