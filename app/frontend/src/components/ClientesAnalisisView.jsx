import { Download, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { downloadExport, getClientesAnalisis } from "../api.js";
import { formatInt, formatMoney } from "./Kpi.jsx";
import { Button, Empty, Panel, PanelHeader, StatTile, cn } from "./ui.jsx";

export default function ClientesAnalisisView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [sel, setSel] = useState("__oficina__");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Descarta respuestas viejas (ver DashboardView): si no, la del acumulado pisa la del mes.
    let cancelled = false;
    setData(null); setErr(null); setSel("__oficina__");
    getClientesAnalisis(sourceId, period)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });
    return () => { cancelled = true; };
  }, [sourceId, period]);

  const block = useMemo(() => {
    if (!data) return null;
    if (sel === "__oficina__") return data.oficina;
    return data.por_gestor.find((g) => g.gestor === sel) || data.oficina;
  }, [data, sel]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;

  const skus = block.skus || [];
  const clientes = block.clientes || [];
  const isOficina = sel === "__oficina__";

  async function handleExport() {
    setBusy(true);
    try { await downloadExport(sourceId, "clientes-analisis", period); }
    catch (e) { alert(e?.response?.data?.detail || "No se pudo descargar"); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex justify-between items-start gap-4 flex-wrap">
        <div>
          <h2 className="section-title">Análisis de Clientes por Vendedor</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Clientes rankeados por ventas ($). Cada columna es un SKU comprado. · {data.rango}
          </p>
        </div>
        <Button variant="outline" icon={Download} onClick={handleExport} disabled={busy}>
          {busy ? "Generando…" : "Exportar Excel"}
        </Button>
      </div>

      {/* Selector Oficina / vendedor */}
      <div className="flex items-center gap-1.5 overflow-x-auto scroll-thin pb-1">
        <button className={cn("tab shrink-0", isOficina && "tab-active")} onClick={() => setSel("__oficina__")}>
          <Users size={15} /> Oficina (total)
        </button>
        {data.por_gestor.map((g) => (
          <button key={g.gestor} className={cn("tab shrink-0", sel === g.gestor && "tab-active")} onClick={() => setSel(g.gestor)}>
            {g.gestor}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile label="Clientes" value={formatInt(block.num_clientes)} accent="brand" />
        <StatTile label="SKUs distintos" value={formatInt(block.num_skus)} accent="slate" />
        <StatTile label="Total ventas" value={formatMoney(block.total)} accent="green" />
        <StatTile label="Ticket promedio" value={formatMoney(block.num_clientes ? block.total / block.num_clientes : 0)} accent="amber" />
      </div>

      {clientes.length === 0 ? (
        <Empty>Sin datos para {isOficina ? "la oficina" : sel} en este periodo.</Empty>
      ) : (
        <Panel>
          <PanelHeader
            icon={Users}
            title={isOficina ? "Oficina — todos los clientes" : `Cartera de ${sel}`}
            sub={`${clientes.length} clientes · ${skus.length} SKUs · valores por SKU en dólares`}
          />
          <div className="overflow-auto scroll-thin max-h-[640px]">
            <table className="text-sm border-collapse">
              <thead>
                <tr className="sticky top-0 z-20">
                  <th className="sticky left-0 z-30 bg-slate-100 text-slate-500 text-[11px] font-semibold uppercase px-3 py-2 text-left border-b border-r border-slate-200 w-10">#</th>
                  <th className="sticky left-10 z-30 bg-slate-100 text-slate-500 text-[11px] font-semibold uppercase px-3 py-2 text-left border-b border-r border-slate-200 min-w-[210px]">Cliente</th>
                  {isOficina && <th className="bg-slate-100 text-slate-500 text-[11px] font-semibold uppercase px-3 py-2 text-left border-b border-slate-200 min-w-[100px]">Gestor</th>}
                  <th className="bg-slate-200/70 text-slate-600 text-[11px] font-semibold uppercase px-3 py-2 text-right border-b border-slate-200 min-w-[110px]">Total $</th>
                  <th className="bg-slate-100 text-slate-500 text-[11px] font-semibold uppercase px-2 py-2 text-center border-b border-slate-200 w-14">#SKUs</th>
                  <th className="bg-slate-100 text-slate-500 text-[11px] font-semibold uppercase px-2 py-2 text-center border-b border-slate-200 w-16" title="Cantidad de pedidos en la app PEDIDO">Pedidos</th>
                  {skus.map((s) => (
                    <th key={s.sku} title={s.sku}
                      className="bg-slate-100 text-slate-500 text-[10px] font-semibold px-2 py-2 text-right border-b border-l border-slate-200 align-bottom w-[120px] min-w-[120px] max-w-[120px]">
                      <span className="line-clamp-3 leading-tight normal-case">{s.sku}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {clientes.map((c, i) => (
                  <tr key={i} className="group">
                    <td className="sticky left-0 z-10 bg-white group-hover:bg-brand-50/60 px-3 py-2 text-slate-400 border-b border-r border-slate-100 tabular-nums">{i + 1}</td>
                    <td className="sticky left-10 z-10 bg-white group-hover:bg-brand-50/60 px-3 py-2 font-medium text-slate-800 border-b border-r border-slate-100 whitespace-nowrap">{c.cliente}</td>
                    {isOficina && <td className="px-3 py-2 border-b border-slate-100"><span className="badge-slate">{c.gestor}</span></td>}
                    <td className="px-3 py-2 text-right font-semibold text-slate-900 bg-slate-50/60 border-b border-slate-100 tabular-nums">{formatMoney(c.total)}</td>
                    <td className="px-2 py-2 text-center text-slate-500 border-b border-slate-100 tabular-nums">{c.num_skus}</td>
                    <td className="px-2 py-2 text-center text-slate-600 font-medium border-b border-slate-100 tabular-nums">{c.pedidos ? formatInt(c.pedidos) : "·"}</td>
                    {skus.map((s) => {
                      const v = c.sku_montos[s.sku];
                      return (
                        <td key={s.sku} className={cn("px-2 py-2 text-right border-b border-l border-slate-100 tabular-nums", v ? "text-slate-700" : "text-slate-200")}>
                          {v ? formatInt(Math.round(v)) : "·"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="sticky bottom-0 z-20">
                  <td className="sticky left-0 z-30 bg-slate-800 border-r border-slate-700 px-3 py-2.5" />
                  <td className="sticky left-10 z-30 bg-slate-800 text-white font-semibold px-3 py-2.5 border-r border-slate-700 whitespace-nowrap">TOTAL POR SKU</td>
                  {isOficina && <td className="bg-slate-800" />}
                  <td className="bg-slate-900 text-white font-bold px-3 py-2.5 text-right tabular-nums">{formatMoney(block.total)}</td>
                  <td className="bg-slate-800" />
                  <td className="bg-slate-800" />
                  {skus.map((s) => (
                    <td key={s.sku} className="bg-slate-800 text-white font-semibold px-2 py-2.5 text-right border-l border-slate-700 tabular-nums">{formatInt(Math.round(s.total))}</td>
                  ))}
                </tr>
              </tfoot>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
