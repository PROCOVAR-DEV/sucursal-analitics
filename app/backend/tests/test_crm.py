"""Cuotas y KPI leídos del CRM (services/crm.py). Sin red: se sustituye `_leer`."""
import pytest

from services import crm
from services.sucursal_store import config_for_period, default_sucursal_config

GESTORES = {
    "ALEXANDER": {"nombre": "Alexander Pérez", "aliases": ["V102"], "cuota_hl": 50.0,
                  "metas_cantidad": {"ARROZ": 9}},
    "JEAN MICHEL": {"nombre": "Jean Michel", "aliases": [], "cuota_hl": 40.0},
}

CUOTAS = [
    {"gestor": "sub-alex", "codigo_vendedor": "V102", "sku": "P15", "producto": "CERVEZA PARRANDA 1,5 L",
     "cuota": 100, "cuota_hectolitros": 1.5},
    {"gestor": "sub-alex", "codigo_vendedor": "V102", "sku": "M33", "producto": "MALTA GUAJIRA 330",
     "cuota": 100, "cuota_hectolitros": 0.33},
    {"gestor": "sub-alex", "codigo_vendedor": "V102", "sku": "AR", "producto": "ARROZ",
     "cuota": 20, "cuota_hectolitros": 0},
    {"gestor": "sub-jean", "codigo_vendedor": "", "sku": "P15", "producto": "CERVEZA PARRANDA 1,5 L",
     "cuota": 200, "cuota_hectolitros": 3.0},
    {"gestor": "sub-otro", "codigo_vendedor": "V999", "sku": "P15", "producto": "CERVEZA PARRANDA 1,5 L",
     "cuota": 10, "cuota_hectolitros": 0.15},
]
KPIS = [
    {"usuario_id": "sub-alex", "codigo_vendedor": "V102", "nombre": "Otro Nombre", "kpis": {"visitas_mes": 7}},
    {"usuario_id": "sub-jean", "codigo_vendedor": "", "nombre": "Jean  Michel", "kpis": {"visitas_mes": 3}},
]


@pytest.fixture
def con_crm(monkeypatch):
    monkeypatch.setenv("CRM_API_URL", "http://crm.invalid/api/v1")
    monkeypatch.setenv("CRM_API_TOKEN", "x")
    crm._CACHE.clear()
    llamadas = []

    def leer(ruta, params):
        llamadas.append((ruta, params))
        return {"/integracion/cuotas": CUOTAS, "/integracion/kpis/gestores": KPIS}[ruta]

    monkeypatch.setattr(crm, "_leer", leer)
    yield llamadas
    crm._CACHE.clear()


def test_sin_configurar_no_cambia_nada(monkeypatch):
    monkeypatch.delenv("CRM_API_URL", raising=False)
    monkeypatch.delenv("CRM_API_TOKEN", raising=False)
    eff = {"gestores": GESTORES, "meta_hectolitros_total": 90.0}
    assert crm.aplicar_cuotas(eff, "camaguey", 2026, 10) is eff
    assert crm.kpis_por_clave({**eff, "_period": "2026-10"}, "camaguey") == {}
    assert crm.huella() == ""


def test_crm_caido_no_cambia_nada(monkeypatch):
    monkeypatch.setenv("CRM_API_URL", "http://127.0.0.1:9/api/v1")  # nadie escucha
    monkeypatch.setenv("CRM_API_TOKEN", "x")
    crm._CACHE.clear()
    eff = {"gestores": GESTORES, "meta_hectolitros_total": 90.0}
    assert crm.aplicar_cuotas(eff, "camaguey", 2026, 10) is eff
    crm._CACHE.clear()


def test_sucursal_sin_codigo_no_llama(con_crm):
    eff = {"gestores": GESTORES}
    assert crm.aplicar_cuotas(eff, "sucursal-de-prueba", 2026, 10) is eff
    assert con_crm == []


def test_las_cuotas_del_crm_mandan(con_crm):
    eff = crm.aplicar_cuotas({"gestores": GESTORES, "meta_hectolitros_total": 90.0}, "camaguey", 2026, 10)
    alex, jean = eff["gestores"]["ALEXANDER"], eff["gestores"]["JEAN MICHEL"]
    assert alex["cuota_hl"] == 1.83
    assert alex["metas_formato"] == {"PARRANDA-1500": 1.5, "MALTA-330": 0.33}
    assert alex["metas_cantidad"] == {"ARROZ": 20.0}  # la de Analytics (9) ya no cuenta
    assert jean["cuota_hl"] == 3.0  # casado por nombre, sin código
    # La sucursal es la suma de TODO lo del CRM, también lo que no casa.
    assert eff["meta_hectolitros_total"] == 4.98
    assert eff["metas_productos_ces"] == {"ARROZ": 20.0}
    assert eff["_fuente_metas"] == "crm"
    assert eff["_crm_sin_casar"] == ["V999"]
    assert ("/integracion/cuotas", {"anio": 2026, "mes": 10, "sucursal": "CAM"}) in con_crm
    # No toca el dict de entrada.
    assert GESTORES["ALEXANDER"]["cuota_hl"] == 50.0


def test_sin_cuotas_ese_mes_se_queda_lo_de_aqui(monkeypatch, con_crm):
    monkeypatch.setattr(crm, "_leer", lambda ruta, params: [])
    eff = {"gestores": GESTORES}
    assert crm.aplicar_cuotas(eff, "camaguey", 2026, 11) is eff


def test_cache_evita_volver_a_preguntar(con_crm):
    crm.aplicar_cuotas({"gestores": GESTORES}, "camaguey", 2026, 10)
    n = len(con_crm)
    crm.aplicar_cuotas({"gestores": GESTORES}, "camaguey", 2026, 10)
    assert len(con_crm) == n


def test_kpis_por_clave(con_crm):
    kpis = crm.kpis_por_clave({"gestores": GESTORES, "_period": "2026-10"}, "camaguey")
    assert kpis == {"ALEXANDER": {"visitas_mes": 7}, "JEAN MICHEL": {"visitas_mes": 3}}
    # Acumulado de varios meses: no hay un mes al que pedirle KPI.
    assert crm.kpis_por_clave({"gestores": GESTORES, "_period": None}, "camaguey") == {}


def test_config_for_period_pasa_por_el_crm(con_crm):
    suc = default_sucursal_config("Camagüey", sid="camaguey", seed_gestores=False)
    suc["gestores"] = GESTORES
    eff = config_for_period(suc, 2026, 10)
    assert eff["_fuente_metas"] == "crm"
    assert eff["gestores"]["ALEXANDER"]["cuota_hl"] == 1.83
    assert eff["_period"] == "2026-10"


def test_formato():
    assert crm._formato("CERVEZA PARRANDA 1,5 L") == "PARRANDA-1500"
    assert crm._formato("MALTA GUAJIRA 330") == "MALTA-330"
    assert crm._formato("ARROZ") is None
