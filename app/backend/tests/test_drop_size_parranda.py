import pandas as pd

from services.loader import STD_COLS
from services.vendedores import drop_size_parranda


def _df(filas):
    return pd.DataFrame(filas, columns=[STD_COLS["op"], "GrupoComercial", "Hectolitros"])


def test_hl_entre_operaciones_solo_de_parranda():
    df = _df([
        ("F1", "PARRANDA", 1.0), ("F1", "PARRANDA", 0.5),  # una operacion, 1,5 HL
        ("F2", "PARRANDA", 0.5),
        ("F3", "IMPORTACIONES", 9.0),  # no cuenta
    ])
    r = drop_size_parranda(df)
    assert r == {"operaciones": 2, "hectolitros": 2.0, "drop_size": 1.0}


def test_sin_parranda_da_cero_sin_dividir():
    assert drop_size_parranda(_df([("F1", "IMPORTACIONES", 3.0)]))["drop_size"] == 0.0
    assert drop_size_parranda(_df([]))["operaciones"] == 0
