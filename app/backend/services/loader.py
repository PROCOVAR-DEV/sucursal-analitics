"""Carga y normalización del 'Reporte de Venta' (crudo transaccional).

Soporta:
  A) Mono-hoja con columna 'Nota' (formato PROCOVAR real): el gestor se detecta
     del segmento 'V-' de la nota EN TIEMPO DE CÓMPUTO (dinámico por sucursal).
  B) Multi-hoja, una hoja por gestor: se guarda el nombre de hoja y el enrich lo
     mapea contra los gestores de la sucursal.

El loader NO conoce la sucursal: solo deja columnas estables. La asignación de
gestor, hectolitros, grupo y pallets la hace `enrich_for_sucursal` con la config
efectiva (para que editar gestores/factores/alias se refleje al instante).
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd

from core.utils import (
    detect_size,
    extract_vendor_segment,
    find_col,
    is_malta,
    is_parranda,
    normalize_text,
    smart_to_numeric,
)


@dataclass
class ReportData:
    df: pd.DataFrame
    date_min: pd.Timestamp | None
    date_max: pd.Timestamp | None
    filename: str

    @property
    def rango_str(self) -> str:
        if self.date_min is None or self.date_max is None:
            return "Rango no disponible"
        return f"{self.date_min.strftime('%d/%m/%Y')} - {self.date_max.strftime('%d/%m/%Y')}"


STD_COLS = {
    "op": "Operacion", "fecha": "Fecha", "socio": "Socio", "merc": "Mercancia",
    "grupo": "Grupo", "cant": "Cantidad", "importe": "Importe", "suma": "SumaTotal",
    "nota": "Nota", "sheet": "__sheet__",
    "vseg": "VendorSegNorm", "size": "Size", "malta": "IsMalta", "parr": "IsParranda",
}


def _engine_for(filename: str) -> str | None:
    return "xlrd" if filename.lower().endswith(".xls") else None


def _find_header_row(raw: pd.DataFrame) -> int:
    for i in range(min(30, len(raw))):
        row_vals = [str(v).strip() for v in raw.iloc[i].tolist()]
        if any("Operaci" in v for v in row_vals) and any("Fecha" in v for v in row_vals):
            return i
    return 0


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    cols = df.columns
    mapping = {
        find_col(cols, ["No.", "Operaci"]) or find_col(cols, ["Operaci"]): STD_COLS["op"],
        find_col(cols, ["Fecha"]): STD_COLS["fecha"],
        find_col(cols, ["socio"]) or find_col(cols, ["Nombre"]): STD_COLS["socio"],
        find_col(cols, ["Mercanc"]): STD_COLS["merc"],
        find_col(cols, ["Grupo"]): STD_COLS["grupo"],
        find_col(cols, ["Cant"]): STD_COLS["cant"],
        find_col(cols, ["Importe"]): STD_COLS["importe"],
        find_col(cols, ["Suma", "Total"]): STD_COLS["suma"],
        find_col(cols, ["Nota"]): STD_COLS["nota"],
    }
    mapping = {k: v for k, v in mapping.items() if k is not None}
    return df.rename(columns=mapping)


def _type_df(df: pd.DataFrame) -> pd.DataFrame:
    if STD_COLS["fecha"] in df.columns:
        fecha = pd.to_datetime(df[STD_COLS["fecha"]], errors="coerce")
        fecha = fecha.where(fecha.dt.year >= 2000)
        df[STD_COLS["fecha"]] = fecha
    for k in ("cant", "importe", "suma"):
        c = STD_COLS[k]
        if c in df.columns:
            df[c] = smart_to_numeric(df[c])
            if k != "cant":
                df[c] = df[c].round(2)
    if STD_COLS["op"] in df.columns:
        df[STD_COLS["op"]] = pd.to_numeric(df[STD_COLS["op"]], errors="coerce").astype("Int64")
    for key in ("socio", "merc", "grupo", "nota", "sheet"):
        c = STD_COLS[key]
        if c in df.columns:
            df[c] = df[c].astype("string")
    return df


def _add_stable_helpers(df: pd.DataFrame) -> pd.DataFrame:
    """Columnas estables (no dependen de la config de la sucursal)."""
    nota = STD_COLS["nota"]
    if nota in df.columns:
        df[STD_COLS["vseg"]] = df[nota].apply(lambda v: normalize_text(extract_vendor_segment(v)))
    else:
        df[STD_COLS["vseg"]] = ""
    merc = STD_COLS["merc"]
    if merc in df.columns:
        df[STD_COLS["size"]] = df[merc].apply(detect_size)
        df[STD_COLS["malta"]] = df[merc].apply(is_malta)
        df[STD_COLS["parr"]] = df[merc].apply(is_parranda)
    else:
        df[STD_COLS["size"]] = None
        df[STD_COLS["malta"]] = False
        df[STD_COLS["parr"]] = False
    df[STD_COLS["vseg"]] = df[STD_COLS["vseg"]].astype("string")
    df[STD_COLS["size"]] = df[STD_COLS["size"]].astype("string")
    return df


def load_report(content: bytes, filename: str) -> ReportData:
    bio = io.BytesIO(content)
    engine = _engine_for(filename)
    xl = pd.ExcelFile(bio, engine=engine)

    # Hojas que NO son de datos transaccionales (resúmenes generados)
    skip = {"supervisor", "resumen general", "resumen", "cumplimiento",
            "ranking general", "ranking semanal", "progreso diario", "evolución",
            "evolucion", "reporte de ventas", "_datos_grafico"}
    data_sheets = [s for s in xl.sheet_names if str(s).strip().lower() not in skip]
    if not data_sheets:
        data_sheets = list(xl.sheet_names)

    dfs: list[pd.DataFrame] = []
    multi = len(data_sheets) >= 2
    for sheet in data_sheets:
        bio.seek(0)
        raw = pd.read_excel(bio, sheet_name=sheet, header=None, engine=engine)
        hdr = _find_header_row(raw)
        bio.seek(0)
        dfi = pd.read_excel(bio, sheet_name=sheet, header=hdr, engine=engine)
        dfi = _normalize_df(dfi)
        # Solo aceptar hojas que parezcan transaccionales (tienen Operacion/Fecha)
        if STD_COLS["fecha"] not in dfi.columns:
            continue
        dfi[STD_COLS["sheet"]] = str(sheet) if multi else None
        dfs.append(dfi)

    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    if not df.empty:
        df = _type_df(df)
        df = _add_stable_helpers(df)

    date_min = date_max = None
    if STD_COLS["fecha"] in df.columns:
        valid = df[STD_COLS["fecha"]].dropna()
        if not valid.empty:
            date_min, date_max = valid.min(), valid.max()

    return ReportData(df=df, date_min=date_min, date_max=date_max, filename=filename)


def filter_by_period(report: ReportData, mes: str | None) -> ReportData:
    if mes is None:
        return report
    try:
        year, month = int(mes[:4]), int(mes[5:7])
    except (ValueError, IndexError):
        return report
    fecha = STD_COLS["fecha"]
    if fecha not in report.df.columns:
        return report
    mask = (report.df[fecha].dt.year == year) & (report.df[fecha].dt.month == month)
    filtered = report.df[mask].copy()
    valid = filtered[fecha].dropna()
    return ReportData(
        df=filtered,
        date_min=valid.min() if not valid.empty else None,
        date_max=valid.max() if not valid.empty else None,
        filename=report.filename,
    )


def available_periods(report: ReportData) -> list[str]:
    fecha = STD_COLS["fecha"]
    if fecha not in report.df.columns:
        return []
    valid = report.df[fecha].dropna()
    if valid.empty:
        return []
    return sorted({f"{d.year}-{d.month:02d}" for d in valid}, reverse=True)
