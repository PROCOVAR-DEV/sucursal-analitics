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

// Ventas por formato (SKU) de Parranda y Malta, en HL, por SEMANA. Se elige la semana:
// "Todas" muestra la matriz formato × semanas + total; una semana muestra solo esa.
function TablaSkuSemanal({ sku, weeksDisp }) {
  const [semana, setSemana] = useState("");
  if (!Array.isArray(sku) || sku.length === 0) return null;
  const weeks = weeksDisp && weeksDisp.length ? weeksDisp : ["S1", "S2", "S3", "S4", "S5"];
  const single = semana && weeks.includes(semana);
  const weekTotal = single ? sku.reduce((s, r) => s + (r.semanal[semana] || 0), 0) : 0;

  return (
    <div className="card">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div>
          <h3 className="font-semibold">Ventas por formato (semanal)</h3>
          <p className="text-sm text-slate-500">
            Hectolitros por SKU de Cerveza Parranda y Malta Guajira — general
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Semana:</label>
          <select
            className="input text-xs py-1 px-2 w-auto"
            value={semana}
            onChange={(e) => setSemana(e.target.value)}
          >
            <option value="">Todas</option>
            {weeks.map((w) => (
              <option key={w} value={w}>{w}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2 text-left">Formato</th>
              {single ? (
                <>
                  <th className="px-3 py-2 text-right">HL {semana}</th>
                  <th className="px-3 py-2 text-right">% de la semana</th>
                </>
              ) : (
                <>
                  {weeks.map((w) => (
                    <th key={w} className="px-3 py-2 text-right">{w}</th>
                  ))}
                  <th className="px-3 py-2 text-right">Total</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {sku.map((r) => {
              const val = single ? (r.semanal[semana] || 0) : 0;
              const pct = single && weekTotal > 0 ? Math.round((val / weekTotal) * 100) : 0;
              return (
                <tr key={r.formato} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">{r.formato}</td>
                  {single ? (
                    <>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(val)} HL</td>
                      <td className="px-3 py-2 text-right text-slate-500">{pct}%</td>
                    </>
                  ) : (
                    <>
                      {weeks.map((w) => (
                        <td key={w} className="px-3 py-2 text-right tabular-nums">{formatNumber(r.semanal[w] || 0)}</td>
                      ))}
                      <td className="px-3 py-2 text-right font-semibold tabular-nums">{formatNumber(r.total)}</td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="bg-slate-100 font-semibold">
              <td className="px-3 py-2">TOTAL</td>
              {single ? (
                <>
                  <td className="px-3 py-2 text-right tabular-nums">{formatNumber(weekTotal)} HL</td>
                  <td className="px-3 py-2 text-right">100%</td>
                </>
              ) : (
                <>
                  {weeks.map((w) => (
                    <td key={w} className="px-3 py-2 text-right tabular-nums">
                      {formatNumber(sku.reduce((s, r) => s + (r.semanal[w] || 0), 0))}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-right tabular-nums text-brand-700">
                    {formatNumber(sku.reduce((s, r) => s + (r.total || 0), 0))}
                  </td>
                </>
              )}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

export default function MarketView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    // Descarta respuestas viejas (ver DashboardView): si no, la del acumulado pisa la del mes.
    let cancelled = false;
    setData(null); setErr(null);
    getMarket(sourceId, period)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });
    return () => { cancelled = true; };
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
      <TablaSkuSemanal sku={data.sku_semanal} weeksDisp={data.weeks_disponibles} />
      <Tabla titulo="Hectolitros (HL)" weeks={data.weeks} filas={data.hl} cuotaKey="cuota_hl" />
      <Tabla titulo="Cajas Comerciales (CCC / clientes únicos)" weeks={data.weeks} filas={data.ccc} cuotaKey="cuota_ccc" />
    </div>
  );
}
