"""Configuración compartida por todos los módulos de negocio.

Centraliza gestores, alias, metas, factores de conversión y meses,
para que los servicios reutilicen la misma fuente de verdad.
"""
from __future__ import annotations

GESTORES_PERMITIDOS: list[str] = [
    "ALEXANDER",
    "DEYANIRA",
    "GEORLIS",
    "JEAN MICHEL",
    "JELEN",
    "MAYLEN",
]

# Aliases/errores ortográficos comunes en la columna Nota
ALIAS_MAP: dict[str, str] = {
    "ALELEXANDER": "ALEXANDER", "ALENXANDER": "ALEXANDER", "ALEXANDR": "ALEXANDER",
    "ALEJANDER": "ALEXANDER", "ALEX": "ALEXANDER", "ALEXANDER": "ALEXANDER",
    "DEYANIRA": "DEYANIRA", "DEIANIRA": "DEYANIRA", "DEYANNIRA": "DEYANIRA",
    "DEYANI": "DEYANIRA", "DEY": "DEYANIRA",
    "GEORLIS": "GEORLIS", "GEORLI": "GEORLIS", "GEIRLIS": "GEORLIS",
    "GEORLIS_": "GEORLIS", "GEORLIS.": "GEORLIS", "GEORLIS!!": "GEORLIS",
    "JEANMICHEL": "JEAN MICHEL", "JEANMIC": "JEAN MICHEL", "JEANMICHE": "JEAN MICHEL",
    "JEAN": "JEAN MICHEL", "JAEN": "JEAN MICHEL", "MICHEL": "JEAN MICHEL",
    "JELEN": "JELEN", "JELEN.": "JELEN", "JELEN_": "JELEN",
    "MAYLEN": "MAYLEN", "MAYELIN": "MAYLEN", "MAYELEN": "MAYLEN",
    "MAYLIN": "MAYLEN", "MAYLEN.": "MAYLEN", "MAYLEN_": "MAYLEN",
}

# Configuración detallada por gestor (agencias, sectores, cuotas)
GESTORES_CONFIG: dict[str, dict] = {
    "ALEXANDER":   {"nombre": "Alexander Padron",  "sector": "Zona 1", "cuota_hl": 178.5, "cuota_ccc": 100},
    "DEYANIRA":    {"nombre": "Deyanira Zaldivar", "sector": "Zona 2", "cuota_hl": 178.5, "cuota_ccc": 100},
    "GEORLIS":     {"nombre": "Georlis Cardenas",  "sector": "Zona 3", "cuota_hl": 178.5, "cuota_ccc": 100},
    "JEAN MICHEL": {"nombre": "Jean Ramos",        "sector": "Zona 4", "cuota_hl": 178.5, "cuota_ccc": 100},
    "JELEN":       {"nombre": "Jelen",             "sector": "Zona 5", "cuota_hl":  15.0, "cuota_ccc":  50},
    "MAYLEN":      {"nombre": "Maylen Remon",      "sector": "Zona 6", "cuota_hl": 178.5, "cuota_ccc": 100},
}

# Hectolitros = Cantidad × multiplicador (por tamaño de envase)
SIZE_MULT: dict[str, float] = {"330": 0.02, "500": 0.03, "1500": 0.09}

# Unidades por Pallet (blisters → pallets)
UNITS_PER_PALLET: dict[tuple[str, str], int] = {
    ("MALTA", "330"): 496, ("PARRANDA", "330"): 496,
    ("MALTA", "500"): 336, ("PARRANDA", "500"): 336,
    ("MALTA", "1500"): 110, ("PARRANDA", "1500"): 110,
}

META_HECTOLITROS_TOTAL: float = 920.0
META_DINERO_TOTAL: float = 350000.0

# Productos CES con meta mensual (unidades)
METAS_PRODUCTOS_CES: dict[str, float] = {
    "ACEITE": 1000,
    "ARROZ": 2500,
    "AZUCAR": 5000,
    "REFRESCO": 2418,
    "SANTA ISABEL": 8000,
}

MESES_ES: dict[int, str] = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}
