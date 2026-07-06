import { UserCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { getMetasGestor, getVendedores } from "../api.js";
import { Kpi, formatInt, formatMoney, formatNumber } from "./Kpi.jsx";
import { VendorFormatoTables } from "./MetasGestorReport.jsx";

export default function VendedoresView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [metas, setMetas] = useState(null);
  const [err, setErr] = useState(null);
  const [selGestor, setSelGestor] = useState(null);

  useEffect(() => {
    setData(null); setMetas(null); setErr(null); setSelGestor(null);
    getVendedores(sourceId, period)
      .then(setData)
      .catch((e) => setErr(e?.response?.data?.detail || e.message));
    getMetasGestor(sourceId, period).then(setMetas).catch(() => {});
  }, [sourceId, period]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  const activeGestor = selGestor ?? data.vendedores[0]?.gestor ?? null;
  const vendor = data.vendedores.find((v) => v.gestor === activeGestor);
  const metasBlock = metas?.por_gestor?.find((g) => g.gestor === activeGestor) || null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <UserCheck className="text-brand-600" /> Por Vendedor
          </h2>
          <p className="text-sm text-slate-500">{data.rango}</p>
        </div>
      </div>

      {/* Office summary KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <Kpi label="Total Oficina (importe)" value={formatMoney(data.total_importe)} />
        <Kpi label="Total Hectolitros" value={formatNumber(data.total_hectolitros, 2)} tone="brand" />
        <Kpi label="Total Operaciones" value={formatInt(data.total_operaciones)} tone="slate" />
      </div>

      {/* Vendor tab selector */}
      <div className="flex gap-2 flex-wrap border-b border-slate-200 pb-3">
        {data.vendedores.map((v) => {
          const active = v.gestor === activeGestor;
          const pct = v.cumplimiento_pct;
          const tone = pct >= 100 ? "text-emerald-700" : pct >= 80 ? "text-amber-700" : "text-red-700";
          return (
            <button
              key={v.gestor}
              className={`tab flex flex-col items-start gap-0.5 py-2 px-4 ${active ? "tab-active" : ""}`}
              onClick={() => setSelGestor(v.gestor)}
            >
              <span className="font-semibold">{v.nombre || v.gestor}</span>
              {!active && (
                <span className={`text-[10px] font-bold ${tone}`}>{pct.toFixed(1)}% HL</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Vendor detail */}
      {vendor && <VendorDetail vendor={vendor} metasBlock={metasBlock} formatos={metas?.formatos} reportDate={metas?.report_date} />}
    </div>
  );
}

function VendorDetail({ vendor, metasBlock, formatos, reportDate }) {
  const pct = vendor.cumplimiento_pct;
  const barPct = Math.min(pct, 100);
  const barColor = pct >= 100 ? "bg-emerald-500" : pct >= 80 ? "bg-amber-500" : "bg-red-500";
  const badgeBg  = pct >= 100 ? "bg-emerald-100 text-emerald-800" : pct >= 80 ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800";

  return (
    <div className="space-y-4">
      {/* Vendor header card */}
      <div className="card">
        <div className="flex justify-between items-start flex-wrap gap-3">
          <div>
            <h3 className="text-xl font-bold">{vendor.nombre}</h3>
            <p className="text-sm text-slate-500">{vendor.sector} · {vendor.gestor}</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-bold ${badgeBg}`}>
            {pct.toFixed(1)}% cumplimiento HL
          </span>
        </div>

        {/* HL progress bar */}
        <div className="mt-4">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Hectolitros: {formatNumber(vendor.total_hectolitros, 2)}</span>
            <span>Cuota: {formatNumber(vendor.cuota_hl, 2)} HL</span>
          </div>
          <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
            <div
              className={`h-full ${barColor} rounded-full transition-all`}
              style={{ width: `${barPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Total Ventas" value={formatMoney(vendor.total_importe)} />
        <Kpi label="Hectolitros" value={formatNumber(vendor.total_hectolitros, 2)} tone="brand" />
        <Kpi label="Operaciones" value={formatInt(vendor.num_operaciones)} tone="slate" />
        <Kpi label="Clientes Únicos" value={formatInt(vendor.num_clientes)} tone="slate" />
      </div>

      {/* Estudio diario/mensual por formato (individual) — como el reporte */}
      {metasBlock && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h4 className="font-semibold">Cumplimiento por formato · {vendor.gestor}</h4>
            {reportDate && <span className="text-xs text-slate-400">Último día: {reportDate}</span>}
          </div>
          <VendorFormatoTables block={metasBlock} formatos={formatos} />
        </div>
      )}

      {/* Comisión individual del vendedor */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Comisión" value={formatMoney(vendor.comision)} tone="green" />
        <Kpi label="Ventas sin pedido" value={formatInt(vendor.sin_pedido || 0)} tone="slate" />
        <Kpi label="Descuento sin pedido" value={vendor.descuento ? "-" + formatMoney(vendor.descuento) : formatMoney(0)}
          tone={vendor.descuento > 0 ? "red" : "slate"} />
        <Kpi label="Comisión neta" value={formatMoney(vendor.comision_neta)} tone="brand" />
      </div>

      {/* HL breakdown table */}
      <div className="card">
        <h4 className="font-semibold mb-3">Desglose Hectolitros (Malta / Parranda)</h4>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Producto</th>
                <th className="px-3 py-2 text-right">330 ml</th>
                <th className="px-3 py-2 text-right">500 ml</th>
                <th className="px-3 py-2 text-right">1500 ml</th>
                <th className="px-3 py-2 text-right font-bold">Total HL</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-slate-100">
                <td className="px-3 py-2 font-medium">Malta</td>
                <td className="px-3 py-2 text-right">{formatNumber(vendor.malta_330, 2)}</td>
                <td className="px-3 py-2 text-right">{formatNumber(vendor.malta_500, 2)}</td>
                <td className="px-3 py-2 text-right">{formatNumber(vendor.malta_1500, 2)}</td>
                <td className="px-3 py-2 text-right font-semibold">
                  {formatNumber(vendor.malta_330 + vendor.malta_500 + vendor.malta_1500, 2)}
                </td>
              </tr>
              <tr className="border-t border-slate-100">
                <td className="px-3 py-2 font-medium">Parranda</td>
                <td className="px-3 py-2 text-right">{formatNumber(vendor.parranda_330, 2)}</td>
                <td className="px-3 py-2 text-right">{formatNumber(vendor.parranda_500, 2)}</td>
                <td className="px-3 py-2 text-right">{formatNumber(vendor.parranda_1500, 2)}</td>
                <td className="px-3 py-2 text-right font-semibold">
                  {formatNumber(vendor.parranda_330 + vendor.parranda_500 + vendor.parranda_1500, 2)}
                </td>
              </tr>
              <tr className="border-t-2 border-slate-300 bg-slate-50">
                <td className="px-3 py-2 font-bold">Total</td>
                <td className="px-3 py-2 text-right font-bold">
                  {formatNumber(vendor.malta_330 + vendor.parranda_330, 2)}
                </td>
                <td className="px-3 py-2 text-right font-bold">
                  {formatNumber(vendor.malta_500 + vendor.parranda_500, 2)}
                </td>
                <td className="px-3 py-2 text-right font-bold">
                  {formatNumber(vendor.malta_1500 + vendor.parranda_1500, 2)}
                </td>
                <td className="px-3 py-2 text-right font-bold text-brand-700">
                  {formatNumber(vendor.total_hectolitros, 2)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Top products */}
      {vendor.top_productos?.length > 0 && (
        <div className="card">
          <h4 className="font-semibold mb-3">Top Productos (por importe)</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-100">
                <tr>
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">Producto</th>
                  <th className="px-3 py-2 text-right">Importe</th>
                  <th className="px-3 py-2 text-right">% del total</th>
                </tr>
              </thead>
              <tbody>
                {vendor.top_productos.map((p, i) => {
                  const pctProd = vendor.total_importe > 0
                    ? ((p.total / vendor.total_importe) * 100).toFixed(1)
                    : "0.0";
                  return (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-3 py-2 text-slate-400">{i + 1}</td>
                      <td className="px-3 py-2 font-medium">{p.producto}</td>
                      <td className="px-3 py-2 text-right">{formatMoney(p.total)}</td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-2 bg-slate-200 rounded-full w-16 overflow-hidden">
                            <div
                              className="h-full bg-brand-500 rounded-full"
                              style={{ width: `${pctProd}%` }}
                            />
                          </div>
                          <span className="text-slate-600 w-10 text-right">{pctProd}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
