import pandas as pd

from services.repository import UploadRepository
from services.loader import ReportData, STD_COLS
from services.sucursal_store import SucursalStore, slugify


def _report():
    df = pd.DataFrame([
        {STD_COLS["op"]: "1", STD_COLS["fecha"]: pd.Timestamp("2026-01-05"),
         STD_COLS["socio"]: "JUAN", STD_COLS["merc"]: "CERVEZA", STD_COLS["grupo"]: "BEB",
         STD_COLS["cant"]: 2, STD_COLS["importe"]: 100.0},
    ])
    return ReportData(df=df, date_min=df[STD_COLS["fecha"]].min(),
                      date_max=df[STD_COLS["fecha"]].max(), filename="ventas.xlsx")


def test_add_get_accumulated_delete():
    sid = slugify("QA Repo Temp")
    st = SucursalStore(base_dir=None)
    st.delete(sid)
    st.create("QA Repo Temp")  # Upload tiene FK a la sucursal
    repo = UploadRepository(base_dir=None)
    repo.reset(sid)

    stored = repo.add(sid, _report())
    assert stored.filas == 1

    got = repo.get(sid, stored.id)
    assert list(got.df.columns)[:1] == [STD_COLS["op"]] and len(got.df) == 1

    acc = repo.accumulated(sid)
    assert len(acc.df) == 1

    assert repo.delete(sid, stored.id) is True
    assert repo.get(sid, stored.id) is None

    # limpieza
    repo.reset(sid)
    st.delete(sid)
