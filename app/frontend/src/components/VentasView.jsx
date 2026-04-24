import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { exportUrl, getVentas } from "../api.js";
import { BarCard } from "./Charts.jsx";
import { Kpi, formatMoney, formatNumber } from "./Kpi.jsx";

export default function VentasView({ sourceId }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    getVentas(sourceId).then(setData).catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sourceId]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  const gestoresBar = data.gestores.map((g) => ({ gestor: g.gestor, hectolitros: g.total_hectolitros }));

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Ventas / Supervisor (Hectolitros)</h2>
        <a className="btn-primary" href={exportUrl(sourceId, "ventas")}>
          <Download size={16} /> Exportar Excel
        </a>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Total Hectolitros" value={formatNumber(data.total_hectolitros, 2)} />
        <Kpi label="Meta" value={formatNumber(data.meta_hectolitros, 0)} tone="slate" />
        <Kpi label="% Cumplimiento" value={`${formatNumber(data.cumplimiento_pct, 1)} %`}
          tone={data.cumplimiento_pct >= 100 ? "green" : data.cumplimiento_pct >= 80 ? "amber" : "red"} />
        <Kpi label="Total Importe" value={formatMoney(data.total_importe)} />
      </div>

      <BarCard title="Hectolitros por gestor" data={gestoresBar} xKey="gestor" yKey="hectolitros" />

      <div className="card">
        <h3 className="font-semibold mb-3">Detalle por gestor</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Gestor</th>
                <th className="px-3 py-2 text-right">M330</th>
                <th className="px-3 py-2 text-right">M500</th>
                <th className="px-3 py-2 text-right">M1500</th>
                <th className="px-3 py-2 text-right">P330</th>
                <th className="px-3 py-2 text-right">P500</th>
                <th className="px-3 py-2 text-right">P1500</th>
                <th className="px-3 py-2 text-right">Total HL</th>
                <th className="px-3 py-2 text-right">Cuota</th>
                <th className="px-3 py-2 text-right">% Cumpl.</th>
                <th className="px-3 py-2 text-right">Importe</th>
              </tr>
            </thead>
            <tbody>
              {data.gestores.map((g) => (
                <tr key={g.gestor} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">{g.gestor}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(g.malta_330, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(g.malta_500, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(g.malta_1500, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(g.parranda_330, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(g.parranda_500, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(g.parranda_1500, 2)}</td>
                  <td className="px-3 py-2 text-right font-semibold">{formatNumber(g.total_hectolitros, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(g.cuota_hl, 2)}</td>
                  <td className={`px-3 py-2 text-right font-semibold ${
                    g.cumplimiento_pct >= 100 ? "text-emerald-600" : g.cumplimiento_pct >= 80 ? "text-amber-600" : "text-red-600"
                  }`}>
                    {formatNumber(g.cumplimiento_pct, 1)}%
                  </td>
                  <td className="px-3 py-2 text-right">{formatMoney(g.total_importe)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
