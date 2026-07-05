"""Utilidades puras compartidas por los servicios (sin efectos secundarios).

La detección de gestor es *dinámica*: recibe la lista de gestores y su mapa de
alias de la sucursal en curso (no hay lista global hardcodeada).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import pandas as pd


def find_col(cols: Iterable[str], subs: list[str]) -> str | None:
    """Primera columna cuyo nombre contiene todos los substrings (case-insensitive)."""
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


def extract_vendor_segment(obs_val: str | None) -> str:
    """Devuelve el segmento del VENDEDOR ('V-…' o 'V:…') de la Nota.

    La Nota tiene forma  'P-…; V-NOMBRE VENDEDOR; C-CLIENTE;'  y el cliente puede
    contener otro nombre de gestor, por eso hay que quedarse solo con el segmento V.
    Si no hay marca V-, se usa la nota completa.
    """
    txt = str(obs_val) if obs_val is not None else ""
    m = re.search(r"\bV[-:]\s*([^;]+)", txt, re.IGNORECASE)
    return m.group(1).strip() if m else txt


def build_alias_map(gestores: dict) -> dict[str, str]:
    """Construye el mapa alias→clave a partir de la config de gestores de la sucursal."""
    alias_map: dict[str, str] = {}
    for key, cfg in (gestores or {}).items():
        k = str(key).upper().strip()
        alias_map[k.replace(" ", "")] = key
        for al in (cfg.get("aliases") or []):
            an = normalize_text(al).replace(" ", "")
            if an:
                alias_map[an] = key
    return alias_map


def detect_gestor(obs_val: str | None, gestores: dict, alias_map: dict[str, str] | None = None) -> str | None:
    """Detecta la clave de gestor presente en la Nota, usando la config de la sucursal.

    `gestores` = dict {clave: {...}} de la sucursal.
    `alias_map` = mapa alias_normalizado_sin_espacios → clave (opcional; se calcula si falta).
    """
    if not gestores:
        return None
    keys = list(gestores.keys())
    alias_map = alias_map if alias_map is not None else build_alias_map(gestores)

    txt = normalize_text(extract_vendor_segment(obs_val))
    if not txt:
        return None
    # 1) coincidencia exacta de clave como palabra
    for g in keys:
        gn = normalize_text(g)
        if gn and re.search(rf"(^|\b){re.escape(gn)}(\b|$)", txt):
            return g
    # 2) alias (comparación sin espacios, substring)
    txt_nospace = txt.replace(" ", "")
    for alias_ns, gestor in alias_map.items():
        if alias_ns and alias_ns in txt_nospace:
            return gestor
    # 3) claves multi-palabra (todas las palabras presentes)
    parts = set(txt.split())
    for g in keys:
        words = normalize_text(g).split()
        if len(words) > 1 and all(w in parts for w in words):
            return g
    return None


def detect_gestor_punto(obs_val: str | None, gestores: dict, alias_map: dict[str, str] | None = None) -> str | None:
    """Detecta NOMBRE!! (2+ signos de admiración) = cliente que vino por su cuenta."""
    if obs_val is None or not gestores:
        return None
    raw = str(obs_val).strip()
    if not raw or raw.upper() == "NAN":
        return None
    t = unicodedata.normalize("NFKD", raw.upper())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    for g in gestores.keys():
        gn = unicodedata.normalize("NFKD", str(g).upper())
        gn = "".join(ch for ch in gn if not unicodedata.combining(ch))
        if re.search(rf"(?:^|\b){re.escape(gn)}\s*!{{2,}}", t):
            return g
    for cfg_key, cfg in gestores.items():
        for al in (cfg.get("aliases") or []):
            an = unicodedata.normalize("NFKD", str(al).upper())
            an = "".join(ch for ch in an if not unicodedata.combining(ch))
            if an and re.search(rf"(?:^|\b){re.escape(an)}\s*!{{2,}}", t):
                return cfg_key
    return None


def detect_size(text: str | None, sizes: Iterable[str] | None = None) -> str | None:
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


def detect_product_group(grupo_val, merc_val, groups_keywords: dict) -> str:
    """Clasifica una fila en un grupo comercial (dinámico por sucursal)."""
    grupo = str(grupo_val).upper().strip() if grupo_val is not None else ""
    merc = str(merc_val).upper().strip() if merc_val is not None else ""
    if "PROCOVAR" in grupo or "PARRANDA" in grupo:
        return "PARRANDA"
    if "IMPORT" in grupo:
        return "IMPORTACIONES"
    if "CONSIGN" in grupo:
        return "CONSIGNACION"
    if "TECNOLOG" in grupo or "KAPITAL" in grupo:
        return "TECNOLOGIA Y KAPITAL"
    for group_name, keywords in (groups_keywords or {}).items():
        for kw in keywords:
            if kw.upper() in merc:
                return group_name
    return "OTRO"


def smart_to_numeric(series: pd.Series) -> pd.Series:
    """Convierte string con separadores de miles '.' y decimal ',' a número."""
    if pd.api.types.is_numeric_dtype(series):
        return series
    s = series.astype(str).str.replace(" ", " ", regex=False).str.strip()
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")
