import { Download, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { exportUrl, getRanking } from "../api.js";
import { LineCard } from "./Charts.jsx";
import { formatMoney } from "./Kpi.jsx";

const MEDAL = { 1: "🥇", 2: "🥈", 3: "🥉" };

export default function RankingView({ sid }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    getRanking(sid).then(setData);
  }, [sid]);

  const diarioChart = useMemo(() => {
    if (!data) return { series: [], data: [] };
    const vendedores = [...new Set(data.diario.map((r) => r.vendedor))];
    const fechas = [...new Set(data.diario.map((r) => r.fecha))].sort();
    const byFecha = {};
    for (const f of fechas) byFecha[f] = { fecha: f };
    for (const r of data.diario) byFecha[r.fecha][r.vendedor] = r.acumulado;
    return {
      series: vendedores.map((v) => ({ key: v, label: v })),
      data: fechas.map((f) => byFecha[f]),
    };
  }, [data]);

  if (!data) return <div className="p-6">Cargando…</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Trophy className="text-amber-500" /> Ranking de ventas
        </h2>
        <a className="btn-primary" href={exportUrl(sid, "ranking")}>
          <Download size={16} /> Exportar Excel
        </a>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3">General</h3>
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">Vendedor</th>
              <th className="px-3 py-2 text-right">Ventas</th>
            </tr>
          </thead>
          <tbody>
            {data.general.map((r) => (
              <tr key={r.vendedor} className="border-t border-slate-100">
                <td className="px-3 py-2 font-bold">{MEDAL[r.posicion] || r.posicion}</td>
                <td className="px-3 py-2">{r.vendedor}</td>
                <td className="px-3 py-2 text-right font-semibold">{formatMoney(r.ventas)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <LineCard
        title="Acumulado diario por vendedor"
        subtitle="Muestra la evolución del monto acumulado por día"
        data={diarioChart.data}
        xKey="fecha"
        series={diarioChart.series}
      />

      <div className="card">
        <h3 className="font-semibold mb-3">Por semana</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Semana</th>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Vendedor</th>
                <th className="px-3 py-2 text-right">Ventas</th>
              </tr>
            </thead>
            <tbody>
              {data.semanal.map((r, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="px-3 py-2">{r.semana}</td>
                  <td className="px-3 py-2 font-bold">{MEDAL[r.posicion] || r.posicion}</td>
                  <td className="px-3 py-2">{r.vendedor}</td>
                  <td className="px-3 py-2 text-right">{formatMoney(r.ventas)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
