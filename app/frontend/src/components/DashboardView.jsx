import { useEffect, useState } from "react";
import { getDashboard } from "../api.js";
import { Kpi, formatInt, formatMoney, formatNumber } from "./Kpi.jsx";
import { BarCard, PieCard } from "./Charts.jsx";

export default function DashboardView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    getDashboard(sourceId, period).then(setData).catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sourceId, period]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  const { kpis } = data;
  const gestoresBar = data.gestores_ventas.map((g) => ({
    gestor: g.gestor,
    hectolitros: g.total_hectolitros,
  }));
  const rankingPie = data.ranking_general.map((r) => ({ name: r.vendedor, value: r.ventas }));

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold">Resumen General</h2>
          <p className="text-sm text-slate-500">
            {sourceId === "accumulated" ? "Acumulado global · " : ""}
            Periodo: {data.rango} · {data.filas.toLocaleString("es-CO")} filas
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Hectolitros" value={formatNumber(kpis.total_hectolitros, 2)} hint={`Meta: ${formatNumber(kpis.meta_hectolitros, 0)}`} />
        <Kpi label="% Cumplimiento" value={`${formatNumber(kpis.cumplimiento_pct, 1)} %`}
          tone={kpis.cumplimiento_pct >= 100 ? "green" : kpis.cumplimiento_pct >= 80 ? "amber" : "red"} />
        <Kpi label="Venta Total" value={formatMoney(kpis.total_importe)} tone="slate" />
        <Kpi label="Clientes Punto" value={formatInt(kpis.total_clientes_punto)}
          hint={`${formatInt(kpis.operaciones_punto)} ops.`} tone="brand" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BarCard title="Hectolitros por gestor" subtitle="MALTA + PARRANDA" data={gestoresBar} xKey="gestor" yKey="hectolitros" />
        <PieCard title="Ranking general de ventas" subtitle="Participación por vendedor" data={rankingPie} nameKey="name" valueKey="value" />
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3">Cumplimiento de productos CES</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-slate-700">
              <tr>
                <th className="px-3 py-2 text-left">Producto</th>
                <th className="px-3 py-2 text-right">Meta</th>
                <th className="px-3 py-2 text-right">Real</th>
                <th className="px-3 py-2 text-right">% Cumpl.</th>
                <th className="px-3 py-2 text-right">Debería</th>
                <th className="px-3 py-2 text-right">Delta</th>
                <th className="px-3 py-2 text-right">Nec/día</th>
                <th className="px-3 py-2 text-center">Estado</th>
              </tr>
            </thead>
            <tbody>
              {data.cumplimiento_productos.map((p) => (
                <tr key={p.producto} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">{p.producto}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.meta, 0)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.real, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.cumplimiento_pct, 1)}%</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.deberia, 2)}</td>
                  <td className={`px-3 py-2 text-right font-semibold ${p.delta >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {formatNumber(p.delta, 2)}
                  </td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.necesario_por_dia, 2)}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`inline-block w-2.5 h-2.5 rounded-full ${
                      p.estado === "ok" ? "bg-emerald-500" : p.estado === "alerta" ? "bg-amber-500" : "bg-red-500"
                    }`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
