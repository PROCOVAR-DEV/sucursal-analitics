import { Package } from "lucide-react";
import { useEffect, useState } from "react";
import { getProductos } from "../api.js";
import { BarCard } from "./Charts.jsx";
import { formatNumber } from "./Kpi.jsx";
import { Badge, Panel, PanelHeader, StatTile, cn } from "./ui.jsx";

const GROUP_COLORS = {
  PARRANDA: "#2563eb", IMPORTACIONES: "#16a34a", CONSIGNACION: "#f59e0b", "TECNOLOGIA Y KAPITAL": "#7c3aed",
};

export default function ProductosView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setData(null); setErr(null);
    getProductos(sourceId, period).then(setData).catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sourceId, period]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;

  const order = (data.groups_order || []).filter((g) => (data.resumen_por_grupo?.[g] || []).length);
  const totalDe = (g) => (data.resumen_por_grupo[g] || []).reduce((s, x) => s + (x.total || 0), 0);

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="section-title flex items-center gap-2"><Package className="text-brand-600" size={22} /> Productos por grupo</h2>
          <p className="text-sm text-slate-500">
            Días laborales: {data.dias_laborales_transcurridos}/{data.dias_laborales_totales} (restan {data.dias_laborales_restantes})
          </p>
        </div>
      </div>

      {/* Totales por grupo */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {order.map((g) => (
          <div key={g} className="kpi-card">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: GROUP_COLORS[g] || "#64748b" }} />
              <span className="kpi-label truncate">{g}</span>
            </div>
            <span className="kpi-value">$ {formatNumber(totalDe(g), 2)}</span>
            <span className="text-xs text-slate-400">{(data.resumen_por_grupo[g] || []).length} productos</span>
          </div>
        ))}
      </div>

      {/* Top productos por grupo */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {order.map((g) => (
          <BarCard key={g} title={g} subtitle="Top productos por venta ($)"
            data={(data.resumen_por_grupo[g] || []).slice(0, 8).map((x) => ({ name: x.producto, value: x.total }))}
            xKey="name" yKey="value" tone={GROUP_COLORS[g] || "#2563eb"} />
        ))}
      </div>

      {/* Cumplimiento de metas por producto */}
      <Panel>
        <PanelHeader icon={Package} title="Cumplimiento de metas por producto"
          sub={data.periodo ? `Metas del periodo ${data.periodo}` : "Metas del mes"} />
        <div className="overflow-x-auto scroll-thin">
          <table className="tbl">
            <thead>
              <tr>
                <th>Producto</th><th>Grupo</th>
                <th className="!text-right">Meta</th><th className="!text-right">Real</th>
                <th className="!text-right">% Cumpl.</th><th className="!text-right">Debería</th>
                <th className="!text-right">Delta</th><th className="!text-right">Prom. día</th><th className="!text-right">Nec./día</th>
              </tr>
            </thead>
            <tbody>
              {data.cumplimiento.map((p) => (
                <tr key={p.producto} className="hover:bg-slate-50">
                  <td className="font-medium">{p.producto}</td>
                  <td>{p.grupo ? <Badge tone="slate">{p.grupo}</Badge> : <span className="text-slate-300">—</span>}</td>
                  <td className="text-right tabular-nums">{formatNumber(p.meta, 0)}</td>
                  <td className="text-right tabular-nums">{formatNumber(p.real, 2)}</td>
                  <td className="text-right tabular-nums">{formatNumber(p.cumplimiento_pct, 1)}%</td>
                  <td className="text-right tabular-nums">{formatNumber(p.deberia, 2)}</td>
                  <td className={cn("text-right font-semibold tabular-nums", p.delta >= 0 ? "text-emerald-600" : "text-red-600")}>{formatNumber(p.delta, 2)}</td>
                  <td className="text-right tabular-nums">{formatNumber(p.prom_diario, 2)}</td>
                  <td className="text-right tabular-nums">{formatNumber(p.necesario_por_dia, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
