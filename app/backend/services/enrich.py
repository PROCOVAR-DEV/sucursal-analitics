"""Enriquecimiento dinámico del reporte según la config efectiva de una sucursal.

Toma el DataFrame crudo (columnas estables de loader) y agrega las columnas que
dependen de la configuración editable: gestor asignado, hectolitros, grupo
comercial, pallets, cliente-punto. Se ejecuta en cada cómputo, de modo que editar
gestores/alias/factores se refleja de inmediato.
"""
from __future__ import annotations

import re

import pandas as pd

from core.utils import build_alias_map, detect_product_group, normalize_text
from services.loader import STD_COLS


def _match_gestor_from_seg(vseg, keys: list[str], alias_map: dict[str, str]) -> str | None:
    if vseg is None or (not isinstance(vseg, str) and pd.isna(vseg)):
        return None
    txt = str(vseg).strip()
    if not txt:
        return None
    for g in keys:
        gn = normalize_text(g)
        if gn and re.search(rf"(^|\b){re.escape(gn)}(\b|$)", txt):
            return g
    ns = txt.replace(" ", "")
    for alias_ns, gestor in alias_map.items():
        if alias_ns and alias_ns in ns:
            return gestor
    parts = set(txt.split())
    for g in keys:
        words = normalize_text(g).split()
        if len(words) > 1 and all(w in parts for w in words):
            return g
    return None


def _match_sheet_to_gestor(sheet, keys: list[str]) -> str | None:
    if sheet is None or (not isinstance(sheet, str) and pd.isna(sheet)):
        return None
    if not str(sheet).strip() or str(sheet) == "<NA>":
        return None
    norm = " ".join(str(sheet).upper().split())
    flat = norm.replace(" ", "")
    for g in keys:
        if norm == g.upper() or flat == g.upper().replace(" ", ""):
            return g
    return None


def enrich_for_sucursal(report, eff: dict):
    """Devuelve un nuevo DataFrame enriquecido con las columnas dinámicas.

    `eff` = config efectiva de la sucursal (config_for_period).
    """
    df = report.df.copy() if report is not None and report.df is not None else pd.DataFrame()
    if df.empty:
        return df

    gestores = eff.get("gestores") or {}
    keys = [k for k, v in gestores.items() if v.get("activo", True)]
    alias_map = build_alias_map({k: gestores[k] for k in keys})
    size_mult = {str(k): float(v) for k, v in (eff.get("size_mult") or {}).items()}
    units_pp = {str(k): float(v) for k, v in (eff.get("units_per_pallet") or {}).items()}
    groups_kw = eff.get("product_groups_keywords") or {}

    # --- Gestor: hoja si viene, si no segmento V- ---
    sheet_col = STD_COLS["sheet"]
    vseg_col = STD_COLS["vseg"]

    def _gestor(row):
        g = _match_sheet_to_gestor(row.get(sheet_col), keys) if sheet_col in df.columns else None
        if g:
            return g
        return _match_gestor_from_seg(row.get(vseg_col, ""), keys, alias_map)

    df["GestorDetectado"] = df.apply(_gestor, axis=1)

    # --- Cliente punto (NOMBRE!!) ---
    nota_col = STD_COLS["nota"]
    if nota_col in df.columns:
        def _punto(v):
            if v is None:
                return None
            t = normalize_text(v)
            raw = str(v).upper()
            for g in keys:
                gn = normalize_text(g)
                if gn and re.search(rf"(?:^|\b){re.escape(gn)}\s*!{{2,}}", raw):
                    return g
            return None
        df["GestorPunto"] = df[nota_col].apply(_punto)
    else:
        df["GestorPunto"] = None

    # --- Venta SIN PEDIDO: la Nota trae vendedor (V-) pero NO pedido (P-) ---
    if nota_col in df.columns:
        s = df[nota_col].astype("string").fillna("")
        has_v = s.str.contains(r"(?:^|;)\s*V-", case=False, regex=True)
        has_p = s.str.contains(r"(?:^|;)\s*P-", case=False, regex=True)
        df["SinPedido"] = (has_v & ~has_p).fillna(False)
    else:
        df["SinPedido"] = False

    # --- Hectolitros (Cantidad × size_mult) ---
    size_col = STD_COLS["size"]
    cant_col = STD_COLS["cant"]
    if cant_col in df.columns and size_col in df.columns:
        mult = df[size_col].map(size_mult).fillna(0.0)
        df["Hectolitros"] = (pd.to_numeric(df[cant_col], errors="coerce").fillna(0) * mult).round(2)
    else:
        df["Hectolitros"] = 0.0

    # --- Pallets (Cantidad / units_per_pallet[size]) ---
    if cant_col in df.columns and size_col in df.columns:
        upp = df[size_col].map(units_pp)
        cant = pd.to_numeric(df[cant_col], errors="coerce").fillna(0)
        df["Pallets"] = (cant / upp).where(upp.notna() & (upp != 0), 0.0).round(4)
    else:
        df["Pallets"] = 0.0

    # --- Grupo comercial ---
    merc_col = STD_COLS["merc"]
    grupo_col = STD_COLS["grupo"]
    if merc_col in df.columns:
        gvals = df[grupo_col] if grupo_col in df.columns else pd.Series([None] * len(df), index=df.index)
        df["GrupoComercial"] = [
            detect_product_group(g, m, groups_kw) for g, m in zip(gvals, df[merc_col])
        ]
    else:
        df["GrupoComercial"] = "OTRO"

    for c in ("GestorDetectado", "GestorPunto", "GrupoComercial"):
        df[c] = df[c].astype("string")
    return df


def gestor_keys(eff: dict) -> list[str]:
    """Claves de gestores activos de la sucursal (orden de inserción)."""
    gestores = eff.get("gestores") or {}
    return [k for k, v in gestores.items() if v.get("activo", True)]


def only_valid(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if "GestorDetectado" not in df.columns:
        return df.iloc[0:0].copy()
    return df[df["GestorDetectado"].isin(keys)].copy()
