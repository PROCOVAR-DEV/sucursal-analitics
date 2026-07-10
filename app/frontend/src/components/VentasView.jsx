import { useEffect, useState } from "react";
import { getVentas } from "../api.js";
import { BarCard } from "./Charts.jsx";
import { Kpi, formatMoney, formatNumber } from "./Kpi.jsx";

export default function VentasView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    getVentas(sourceId, period).then(setData).catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sourceId, period]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  const gestoresBar = data.gestores.map((g) => ({ gestor: g.gestor, hectolitros: g.total_hectolitros }));

  // Totales por SKU (hectolitros) sumando todos los gestores — para ver el HL total de cada SKU.
  const tot = data.gestores.reduce((a, g) => ({
    malta_330: a.malta_330 + (g.malta_330 || 0),
    malta_500: a.malta_500 + (g.malta_500 || 0),
    malta_1500: a.malta_1500 + (g.malta_1500 || 0),
    parranda_330: a.parranda_330 + (g.parranda_330 || 0),
    parranda_500: a.parranda_500 + (g.parranda_500 || 0),
    parranda_1500: a.parranda_1500 + (g.parranda_1500 || 0),
    total_hectolitros: a.total_hectolitros + (g.total_hectolitros || 0),
    total_importe: a.total_importe + (g.total_importe || 0),
  }), { malta_330: 0, malta_500: 0, malta_1500: 0, parranda_330: 0, parranda_500: 0, parranda_1500: 0, total_hectolitros: 0, total_importe: 0 });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Ventas / Supervisor (Hectolitros)</h2>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Total Hectolitros" value={formatNumber(data.total_hectolitros, 2)} hint={`Meta: ${formatNumber(data.meta_hectolitros, 0)}`} />
        <Kpi label="% Cumplimiento" value={`${formatNumber(data.cumplimiento_pct, 1)} %`}
          tone={data.cumplimiento_pct >= 100 ? "green" : data.cumplimiento_pct >= 80 ? "amber" : "red"} />
        <Kpi label="Total Importe" value={formatMoney(data.total_importe)} />
        <Kpi label="Comisión supervisor" value={formatMoney(data.comision_supervisor)} tone="green"
          hint={data.supervisor_nombre || ""} />
      </div>

      <BarCard title="Hectolitros por gestor" data={gestoresBar} xKey="gestor" yKey="hectolitros" />

      <div className="panel">
        <div className="card-header"><h3 className="card-title">Detalle por gestor (Hectolitros)</h3></div>
        <div className="overflow-x-auto scroll-thin">
          <table className="text-sm border-collapse">
            <thead>
              <tr>
                <th className="sticky left-0 z-20 bg-slate-100 text-slate-500 text-[11px] font-semibold uppercase px-3 py-2.5 text-left border-b border-r border-slate-200 min-w-[130px]">Gestor</th>
                {["M330", "M500", "M1500", "P330", "P500", "P1500", "Total HL", "Cuota", "% Cumpl.", "Importe"].map((h) => (
                  <th key={h} className="bg-slate-50 text-slate-500 text-[11px] font-semibold uppercase px-3 py-2.5 text-right border-b border-slate-200 whitespace-nowrap min-w-[92px]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.gestores.map((g) => (
                <tr key={g.gestor} className="group">
                  <td className="sticky left-0 z-10 bg-white group-hover:bg-brand-50/60 px-3 py-2 font-medium text-slate-800 border-b border-r border-slate-100 whitespace-nowrap">{g.gestor}</td>
                  <td className="px-3 py-2 text-right border-b border-slate-100 tabular-nums">{formatNumber(g.malta_330, 2)}</td>
                  <td className="px-3 py-2 text-right border-b border-slate-100 tabular-nums">{formatNumber(g.malta_500, 2)}</td>
                  <td className="px-3 py-2 text-right border-b border-slate-100 tabular-nums">{formatNumber(g.malta_1500, 2)}</td>
                  <td className="px-3 py-2 text-right border-b border-slate-100 tabular-nums">{formatNumber(g.parranda_330, 2)}</td>
                  <td className="px-3 py-2 text-right border-b border-slate-100 tabular-nums">{formatNumber(g.parranda_500, 2)}</td>
                  <td className="px-3 py-2 text-right border-b border-slate-100 tabular-nums">{formatNumber(g.parranda_1500, 2)}</td>
                  <td className="px-3 py-2 text-right font-semibold border-b border-slate-100 tabular-nums">{formatNumber(g.total_hectolitros, 2)}</td>
                  <td className="px-3 py-2 text-right border-b border-slate-100 tabular-nums">{formatNumber(g.cuota_hl, 2)}</td>
                  <td className={`px-3 py-2 text-right font-semibold border-b border-slate-100 tabular-nums ${g.cumplimiento_pct >= 100 ? "text-emerald-600" : g.cumplimiento_pct >= 80 ? "text-amber-600" : "text-red-600"}`}>{formatNumber(g.cumplimiento_pct, 1)}%</td>
                  <td className="px-3 py-2 text-right border-b border-slate-100 tabular-nums">{formatMoney(g.total_importe)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-bold bg-slate-100">
                <td className="sticky left-0 z-10 bg-slate-100 px-3 py-2.5 text-slate-800 border-t-2 border-slate-300 whitespace-nowrap">TOTAL HL por SKU</td>
                <td className="px-3 py-2.5 text-right border-t-2 border-slate-300 tabular-nums">{formatNumber(tot.malta_330, 2)}</td>
                <td className="px-3 py-2.5 text-right border-t-2 border-slate-300 tabular-nums">{formatNumber(tot.malta_500, 2)}</td>
                <td className="px-3 py-2.5 text-right border-t-2 border-slate-300 tabular-nums">{formatNumber(tot.malta_1500, 2)}</td>
                <td className="px-3 py-2.5 text-right border-t-2 border-slate-300 tabular-nums">{formatNumber(tot.parranda_330, 2)}</td>
                <td className="px-3 py-2.5 text-right border-t-2 border-slate-300 tabular-nums">{formatNumber(tot.parranda_500, 2)}</td>
                <td className="px-3 py-2.5 text-right border-t-2 border-slate-300 tabular-nums">{formatNumber(tot.parranda_1500, 2)}</td>
                <td className="px-3 py-2.5 text-right border-t-2 border-slate-300 tabular-nums text-brand-700">{formatNumber(tot.total_hectolitros, 2)}</td>
                <td className="px-3 py-2.5 border-t-2 border-slate-300"></td>
                <td className="px-3 py-2.5 border-t-2 border-slate-300"></td>
                <td className="px-3 py-2.5 text-right border-t-2 border-slate-300 tabular-nums">{formatMoney(tot.total_importe)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
}
