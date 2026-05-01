import { useEffect, useState } from "react";
import { getProductos } from "../api.js";
import { BarCard, PieCard } from "./Charts.jsx";
import { formatNumber } from "./Kpi.jsx";

export default function ProductosView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    getProductos(sourceId, period).then(setData).catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sourceId, period]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  const cesTop = data.resumen_ces.slice(0, 10).map((x) => ({ name: x.producto, value: x.total }));
  const procTop = data.resumen_procovar.slice(0, 8).map((x) => ({ name: x.producto, value: x.total }));

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold">Productos (CES / PROCOVAR)</h2>
          <p className="text-sm text-slate-500">
            Días laborales: {data.dias_laborales_transcurridos}/{data.dias_laborales_totales} (restan {data.dias_laborales_restantes})
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BarCard title="Top CES (por venta)" data={cesTop} xKey="name" yKey="value" />
        <PieCard title="PROCOVAR (participación)" data={procTop} nameKey="name" valueKey="value" />
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3">Cumplimiento de metas mensuales</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Producto</th>
                <th className="px-3 py-2 text-right">Meta</th>
                <th className="px-3 py-2 text-right">Real</th>
                <th className="px-3 py-2 text-right">% Cumpl.</th>
                <th className="px-3 py-2 text-right">Debería</th>
                <th className="px-3 py-2 text-right">Delta</th>
                <th className="px-3 py-2 text-right">Prom. día</th>
                <th className="px-3 py-2 text-right">Nec. / día</th>
              </tr>
            </thead>
            <tbody>
              {data.cumplimiento.map((p) => (
                <tr key={p.producto} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium">{p.producto}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.meta, 0)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.real, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.cumplimiento_pct, 1)}%</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.deberia, 2)}</td>
                  <td className={`px-3 py-2 text-right ${p.delta >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {formatNumber(p.delta, 2)}
                  </td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.prom_diario, 2)}</td>
                  <td className="px-3 py-2 text-right">{formatNumber(p.necesario_por_dia, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
