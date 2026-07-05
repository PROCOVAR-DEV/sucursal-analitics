"""Servicio Market: HL y CCC semanal (S1-S5) por gestor con cuotas y semáforos."""
from __future__ import annotations

import pandas as pd

from services.enrich import enrich_for_sucursal, gestor_keys, only_valid
from services.loader import STD_COLS

WEEKS = ["S1", "S2", "S3", "S4", "S5"]


def _semaforo(pct: float) -> str:
    if pct >= 100:
        return "verde"
    if pct >= 80:
        return "amarillo"
    return "rojo"


def _week_of(ts: pd.Timestamp) -> str:
    return WEEKS[min(((ts.day - 1) // 7), 4)]


def compute_market(report, eff: dict) -> dict:
    keys = gestor_keys(eff)
    gestores_cfg = eff.get("gestores") or {}
    curva = {k: float(v) for k, v in (eff.get("curva_venta") or {}).items()}
    frec = {k: float(v) for k, v in (eff.get("frecuencia") or {}).items()}
    sum_curva = sum(curva.get(w, 0) for w in WEEKS) or 1
    sum_frec = sum(frec.get(w, 0) for w in WEEKS) or 1

    df = enrich_for_sucursal(report, eff)
    df = only_valid(df, keys)
    fec, socio = STD_COLS["fecha"], STD_COLS["socio"]

    filas_hl, filas_ccc = [], []
    tot_hl = {w: 0.0 for w in WEEKS}
    tot_ccc = {w: 0 for w in WEEKS}
    tot_cuota_hl = tot_cuota_ccc = tot_real_hl = tot_real_ccc = 0.0

    for g in keys:
        g_cfg = gestores_cfg.get(g, {})
        cuota_hl = float(g_cfg.get("cuota_hl", 0.0))
        cuota_ccc = float(g_cfg.get("cuota_ccc", 0.0))
        sub = df[df["GestorDetectado"] == g] if not df.empty else df

        w_hl = {w: 0.0 for w in WEEKS}
        w_cli = {w: set() for w in WEEKS}
        if not sub.empty and fec in sub.columns:
            valid = sub.dropna(subset=[fec])
            for _, row in valid.iterrows():
                w = _week_of(row[fec])
                # HL solo cerveza (Malta/Parranda), igual que el reporte Supervisor
                if bool(row.get("IsMalta")) or bool(row.get("IsParranda")):
                    w_hl[w] += float(row.get("Hectolitros", 0) or 0)
                if socio in valid.columns and pd.notna(row.get(socio)):
                    w_cli[w].add(str(row[socio]))

        real_hl_mes = round(sum(w_hl.values()), 2)
        real_ccc_mes = int(len(set().union(*w_cli.values()))) if w_cli else 0
        cuota_sem_hl = {w: round(cuota_hl * curva.get(w, 0) / sum_curva, 0) for w in WEEKS}
        cuota_sem_ccc = {w: round(cuota_ccc * frec.get(w, 0) / sum_frec, 0) for w in WEEKS}
        pct_hl = round((real_hl_mes / cuota_hl * 100) if cuota_hl else 0.0, 1)
        pct_ccc = round((real_ccc_mes / cuota_ccc * 100) if cuota_ccc else 0.0, 1)

        filas_hl.append({
            "gestor": g, "nombre": g_cfg.get("nombre", g), "agencia": g_cfg.get("agencia", ""),
            "sector": g_cfg.get("sector", ""), "cuota_hl": cuota_hl,
            "cuota_semanal": cuota_sem_hl, "real_semanal": {w: round(w_hl[w], 2) for w in WEEKS},
            "real_mes": real_hl_mes, "cumplimiento_pct": pct_hl, "semaforo": _semaforo(pct_hl),
        })
        filas_ccc.append({
            "gestor": g, "nombre": g_cfg.get("nombre", g), "cuota_ccc": cuota_ccc,
            "cuota_semanal": cuota_sem_ccc, "real_semanal": {w: len(w_cli[w]) for w in WEEKS},
            "real_mes": real_ccc_mes, "cumplimiento_pct": pct_ccc, "semaforo": _semaforo(pct_ccc),
        })
        for w in WEEKS:
            tot_hl[w] += w_hl[w]
            tot_ccc[w] += len(w_cli[w])
        tot_cuota_hl += cuota_hl
        tot_cuota_ccc += cuota_ccc
        tot_real_hl += real_hl_mes
        tot_real_ccc += real_ccc_mes

    return {
        "rango": report.rango_str, "periodo": eff.get("_period"),
        "supervisor_nombre": eff.get("supervisor_nombre"),
        "meta_hl": float(eff["meta_hectolitros_total"]), "meta_ccc": float(eff["meta_ccc_total"]),
        "weeks": WEEKS, "hl": filas_hl, "ccc": filas_ccc,
        "totales": {
            "hl_semanal": {w: round(tot_hl[w], 2) for w in WEEKS},
            "ccc_semanal": {w: int(tot_ccc[w]) for w in WEEKS},
            "cuota_hl": round(tot_cuota_hl, 2), "real_hl": round(tot_real_hl, 2),
            "cuota_ccc": round(tot_cuota_ccc, 2), "real_ccc": int(tot_real_ccc),
        },
    }
