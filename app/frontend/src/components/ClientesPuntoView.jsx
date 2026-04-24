import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { exportUrl, getPunto } from "../api.js";
import { Kpi, formatInt, formatMoney } from "./Kpi.jsx";
import { BarCard } from "./Charts.jsx";

export default function ClientesPuntoView({ sourceId }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    getPunto(sourceId).then(setData).catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sourceId]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  const byGestor = data.por_gestor.map((g) => ({ gestor: g.gestor, importe: g.total_importe }));

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Clientes Punto</h2>
        <a className="btn-primary" href={exportUrl(sourceId, "clientes-punto")}>
          <Download size={16} /> Exportar Excel
        </a>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <Kpi label="Operaciones" value={formatInt(data.total_operaciones)} />
        <Kpi label="Clientes únicos" value={formatInt(data.total_clientes_unicos)} tone="brand" />
        <Kpi label="Importe total" value={formatMoney(data.total_importe)} tone="green" />
      </div>

      <BarCard title="Clientes punto — importe por gestor" data={byGestor} xKey="gestor" yKey="importe" />

      <div className="card">
        <h3 className="font-semibold mb-3">Resumen por gestor</h3>
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2 text-left">Gestor</th>
              <th className="px-3 py-2 text-right">Operaciones</th>
              <th className="px-3 py-2 text-right">Clientes únicos</th>
              <th className="px-3 py-2 text-right">Importe</th>
            </tr>
          </thead>
          <tbody>
            {data.por_gestor.map((g) => (
              <tr key={g.gestor} className="border-t border-slate-100">
                <td className="px-3 py-2 font-medium">{g.gestor}</td>
                <td className="px-3 py-2 text-right">{formatInt(g.operaciones)}</td>
                <td className="px-3 py-2 text-right">{formatInt(g.clientes_unicos)}</td>
                <td className="px-3 py-2 text-right">{formatMoney(g.total_importe)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3">Detalle de operaciones</h3>
        <div className="overflow-x-auto max-h-[520px]">
          <table className="min-w-full text-xs">
            <thead className="bg-slate-100 sticky top-0">
              <tr>
                {data.filas[0] && Object.keys(data.filas[0]).map((k) => (
                  <th key={k} className="px-2 py-2 text-left whitespace-nowrap">{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.filas.map((row, i) => (
                <tr key={i} className="border-t border-slate-100">
                  {Object.values(row).map((v, j) => (
                    <td key={j} className="px-2 py-1.5 whitespace-nowrap">{String(v)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
