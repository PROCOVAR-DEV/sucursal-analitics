import { Fragment, useEffect, useState } from "react";
import { getMarket } from "../api.js";
import { Kpi, formatNumber } from "./Kpi.jsx";

const DOT = { verde: "text-emerald-500", amarillo: "text-amber-500", rojo: "text-red-500" };

function Tabla({ titulo, weeks, filas, cuotaKey }) {
  return (
    <div className="card">
      <h3 className="font-semibold mb-3">{titulo}</h3>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-2 py-2 text-left">Vendedor</th>
              <th className="px-2 py-2 text-right">Cuota Mes</th>
              {weeks.map((w) => (
                <th key={w} className="px-2 py-2 text-right" colSpan={2}>{w}</th>
              ))}
              <th className="px-2 py-2 text-right">Real Mes</th>
              <th className="px-2 py-2 text-right">% Cumpl.</th>
              <th className="px-2 py-2 text-center">●</th>
            </tr>
            <tr className="text-[10px] text-slate-400">
              <th></th><th></th>
              {weeks.map((w) => (
                <Fragment key={w}>
                  <th className="text-right px-1">cuota</th><th className="text-right px-1">real</th>
                </Fragment>
              ))}
              <th></th><th></th><th></th>
            </tr>
          </thead>
          <tbody>
            {filas.map((r) => (
              <tr key={r.gestor} className="border-t border-slate-100">
                <td className="px-2 py-1.5 font-medium">{r.nombre}</td>
                <td className="px-2 py-1.5 text-right">{formatNumber(r[cuotaKey], 0)}</td>
                {weeks.map((w) => (
                  <Fragment key={w}>
                    <td className="px-1 py-1.5 text-right text-slate-400">{formatNumber(r.cuota_semanal[w], 0)}</td>
                    <td className="px-1 py-1.5 text-right">{formatNumber(r.real_semanal[w], cuotaKey === "cuota_ccc" ? 0 : 2)}</td>
                  </Fragment>
                ))}
                <td className="px-2 py-1.5 text-right font-semibold">{formatNumber(r.real_mes, cuotaKey === "cuota_ccc" ? 0 : 2)}</td>
                <td className="px-2 py-1.5 text-right">{formatNumber(r.cumplimiento_pct, 1)}%</td>
                <td className={`px-2 py-1.5 text-center text-lg ${DOT[r.semaforo]}`}>●</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function MarketView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setData(null); setErr(null);
    getMarket(sourceId, period).then(setData).catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sourceId, period]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;
  const t = data.totales;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Market — HL y CCC semanal</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Real HL" value={formatNumber(t.real_hl, 2)} />
        <Kpi label="Meta HL" value={formatNumber(data.meta_hl, 0)} tone="slate" />
        <Kpi label="Real CCC (clientes)" value={formatNumber(t.real_ccc, 0)} />
        <Kpi label="Meta CCC" value={formatNumber(data.meta_ccc, 0)} tone="slate" />
      </div>
      <Tabla titulo="Hectolitros (HL)" weeks={data.weeks} filas={data.hl} cuotaKey="cuota_hl" />
      <Tabla titulo="Cajas Comerciales (CCC / clientes únicos)" weeks={data.weeks} filas={data.ccc} cuotaKey="cuota_ccc" />
    </div>
  );
}
