"""Valores por defecto del dominio.

IMPORTANTE: estos valores son solo *semillas* para crear una sucursal nueva.
En tiempo de ejecución TODO es dinámico y vive en la configuración de cada
sucursal (ver services/sucursal_store.py). Los servicios de negocio nunca deben
leer estas constantes directamente: reciben la config efectiva de la sucursal.
"""
from __future__ import annotations

# --- Factores de conversión (semilla) ---
# Hectolitros = Cantidad × SIZE_MULT[tamaño]
SIZE_MULT: dict[str, float] = {"330": 0.02, "500": 0.03, "1500": 0.09}

# Unidades (blisters) por Pallet, por tamaño (Malta y Parranda comparten valores)
UNITS_PER_PALLET: dict[str, int] = {"330": 496, "500": 336, "1500": 110}

# Tamaños de envase reconocidos
SIZES: list[str] = ["330", "500", "1500"]

# Comisiones
COMISION_GESTOR_PCT: float = 0.01      # 1% del importe para el gestor
COMISION_SUPERVISOR_PCT: float = 0.10  # 10% de las comisiones para el supervisor

# --- Grupos comerciales (clasificación de productos) ---
PRODUCT_GROUPS_KEYWORDS: dict[str, list[str]] = {
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
GROUPS_ORDER: list[str] = ["PARRANDA", "IMPORTACIONES", "CONSIGNACION", "TECNOLOGIA Y KAPITAL"]

# Colores por grupo (para los export Excel)
GROUP_BG_COLORS: dict[str, str] = {
    "PARRANDA": "#1F4E78",
    "IMPORTACIONES": "#375623",
    "CONSIGNACION": "#7B3900",
    "TECNOLOGIA Y KAPITAL": "#4A1080",
    "OTRO": "#595959",
}
GROUP_CHART_COLORS: dict[str, str] = {
    "PARRANDA": "#4F81BD",
    "IMPORTACIONES": "#70AD47",
    "CONSIGNACION": "#FF9900",
    "TECNOLOGIA Y KAPITAL": "#7030A0",
    "OTRO": "#A0A0A0",
}

# --- Metas de productos CES / Importaciones (semilla) ---
METAS_PRODUCTOS_CES: dict[str, float] = {
    "ACEITE": 1000,
    "ARROZ": 2500,
    "AZUCAR": 5000,
    "REFRESCO": 2418,
    "SANTA ISABEL": 8000,
}

# --- Metas globales (semilla, tomadas del reporte real de Camagüey JULIO 2026) ---
META_HECTOLITROS_TOTAL: float = 1709.0
META_DINERO_TOTAL: float = 400000.0
META_CCC_TOTAL: float = 500.0

# Curva de venta y frecuencia semanal (reporte Market)
CURVA_VENTA: dict[str, int] = {"S1": 3, "S2": 5, "S3": 5, "S4": 5, "S5": 5}
FRECUENCIA: dict[str, int] = {"S1": 1, "S2": 1, "S3": 1, "S4": 1, "S5": 5}

# --- Gestores semilla de la sucursal Camagüey (7 vendedores reales) ---
# aliases = errores/variantes que aparecen en la Nota; el sistema los reconoce.
DEFAULT_GESTORES: dict[str, dict] = {
    "ALEXANDER":   {"nombre": "Alexander Padron",  "agencia": "Camaguey", "sector": "Zona 1", "cuota_hl": 235.0, "cuota_ccc": 100.0,
                    "aliases": ["ALELEXANDER", "ALENXANDER", "ALEXANDR", "ALEJANDER", "ALEX"]},
    "DEYANIRA":    {"nombre": "Deyanira Zaldivar", "agencia": "Camaguey", "sector": "Zona 2", "cuota_hl": 321.0, "cuota_ccc": 100.0,
                    "aliases": ["DEIANIRA", "DEYANNIRA", "DEYANI", "DEY"]},
    "GEORLIS":     {"nombre": "Georlis Cardenas",  "agencia": "Camaguey", "sector": "Zona 3", "cuota_hl": 235.0, "cuota_ccc": 100.0,
                    "aliases": ["GEORLI", "GEIRLIS"]},
    "JEAN MICHEL": {"nombre": "Jean Ramos",        "agencia": "Camaguey", "sector": "Zona 4", "cuota_hl": 235.0, "cuota_ccc": 100.0,
                    "aliases": ["JEANMICHEL", "JEANMIC", "JEANMICHE", "JEAN", "JAEN", "MICHEL"]},
    "ERNESTO":     {"nombre": "Ernesto",           "agencia": "Camaguey", "sector": "Zona 5", "cuota_hl": 224.0, "cuota_ccc": 100.0,
                    "aliases": []},
    "ANDY":        {"nombre": "Andy",              "agencia": "Camaguey", "sector": "Zona 7", "cuota_hl": 224.0, "cuota_ccc": 100.0,
                    "aliases": []},
    "MAYLEN":      {"nombre": "Maylen Remon",      "agencia": "Camaguey", "sector": "Zona 6", "cuota_hl": 235.0, "cuota_ccc": 100.0,
                    "aliases": ["MAYELIN", "MAYELEN", "MAYLIN"]},
}

MESES_ES: dict[int, str] = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO",
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

# --- Paleta de colores de los reportes (export Excel) ---
COLORS = {
    "title": "#203864",
    "header": "#1F4E79",
    "band": "#D9E1F2",
    "block": "#FCE4D6",
    "kpi": "#E2EFDA",
    "green_bg": "#C6EFCE", "green_fg": "#006100",
    "red_bg": "#FFC7CE", "red_fg": "#9C0006",
    "yellow_bg": "#FFEB9C", "yellow_fg": "#9C6500",
    "gold": "#FFD700", "silver": "#C0C0C0", "bronze": "#CD7F32",
    "white": "#FFFFFF",
}
