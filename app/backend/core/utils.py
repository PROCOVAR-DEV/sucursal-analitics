"""Utilidades puras compartidas por los servicios (sin efectos secundarios)."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import pandas as pd

from .constants import ALIAS_MAP, GESTORES_PERMITIDOS


def find_col(cols: Iterable[str], subs: list[str]) -> str | None:
    """Encuentra la primera columna cuyo nombre contenga todos los substrings (case-insensitive)."""
    for c in cols:
        if isinstance(c, str) and all(s.lower() in c.lower() for s in subs):
            return c
    return None


def normalize_text(s: str | None) -> str:
    """Mayúsculas sin tildes ni caracteres especiales (deja letras y espacios)."""
    if s is None:
        return ""
    t = unicodedata.normalize("NFKD", str(s))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.upper()
    t = re.sub(r"\bTRANSFERENCIA\b", " ", t)
    t = re.sub(r"[^A-Z ]+", " ", t)
    return " ".join(t.split())


def detect_gestor(obs_val: str | None) -> str | None:
    """Devuelve el gestor permitido que aparece en la Nota, o None."""
    txt = normalize_text(obs_val)
    if not txt:
        return None
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


def detect_gestor_punto(obs_val: str | None) -> str | None:
    """Detecta NOMBRE!! o NOMBRE!!! (2+ exclamaciones) = cliente que vino por su cuenta."""
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


def detect_size(text: str | None) -> str | None:
    t = str(text).upper() if text is not None else ""
    if "1,5" in t or "1.5" in t or "1500" in t:
        return "1500"
    if "500" in t:
        return "500"
    if "330" in t:
        return "330"
    return None


def is_malta(text: str | None) -> bool:
    t = str(text).upper() if text is not None else ""
    return "MALTA" in t and "GUAJIRA" in t


def is_parranda(text: str | None) -> bool:
    t = str(text).upper() if text is not None else ""
    return "PARRANDA" in t


def smart_to_numeric(series: pd.Series) -> pd.Series:
    """Convierte string con separadores de miles '.' y decimal ',' a número."""
    if pd.api.types.is_numeric_dtype(series):
        return series
    s = series.astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")
