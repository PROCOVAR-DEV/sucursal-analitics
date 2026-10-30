"""El multiplicador de HL por blíster de 6 es litros exactos: 6 x tamaño / 100."""
from core.constants import SIZE_MULT


def test_size_mult_es_seis_botellas_en_hectolitros():
    for size, mult in SIZE_MULT.items():
        assert round(6 * int(size) / 1000 / 100, 4) == mult
