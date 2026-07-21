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
  // Día de corte elegido (null = el último con datos). Permite mirar días anteriores.
  const [selDia, setSelDia] = useState(null);

  useEffect(() => {
    // Descarta respuestas viejas (ver DashboardView): si no, la del acumulado pisa la del mes.
    let cancelled = false;
    setData(null); setErr(null); setSelGestor(null); setSelDia(null);
    getVendedores(sourceId, period)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });
    return () => { cancelled = true; };
  }, [sourceId, period]);

  // Las tablas de cumplimiento se recargan solas al cambiar el día de corte.
  useEffect(() => {
    let cancelled = false;
    setMetas(null);
    getMetasGestor(sourceId, period, selDia)
      .then((d) => { if (!cancelled) setMetas(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [sourceId, period, selDia]);

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

      {/* Vendor tab selector — fijo (sticky) al hacer scroll para cambiar de vendedor
          sin perderlo de vista mientras miras las tablas de abajo. */}
      <div className="sticky top-0 z-20 -mx-3 sm:-mx-6 px-3 sm:px-6 py-3 bg-slate-50/95 backdrop-blur border-b border-slate-200 shadow-sm flex gap-2 flex-wrap">
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
                <span className={`text-[10px] font-bold ${tone}`}>{Math.round(pct)}% HL</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Vendor detail */}
      {vendor && (
        <VendorDetail
          vendor={vendor}
          metasBlock={metasBlock}
          formatos={metas?.formatos}
          reportDate={metas?.report_date}
          diasDisponibles={metas?.dias_disponibles || []}
          diaAnterior={metas?.dia_anterior}
          selDia={selDia}
          onSelDia={setSelDia}
        />
      )}
    </div>
  );
}

function VendorDetail({ vendor, metasBlock, formatos, reportDate, diasDisponibles, diaAnterior, selDia, onSelDia }) {
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
            {Math.round(pct)}% cumplimiento HL
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
            {/* Día de corte: el acumulado se recalcula HASTA ese día y el diario lo compara
                contra el día anterior con datos. Sirve para mirar atrás y ver cómo iban. */}
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-500">Día:</label>
              <select
                className="input text-xs py-1 px-2 w-auto"
                value={selDia ?? ""}
                onChange={(e) => onSelDia(e.target.value || null)}
              >
                <option value="">Último ({reportDate || "—"})</option>
                {[...(diasDisponibles || [])].reverse().map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              {diaAnterior && (
                <span className="text-xs text-slate-400">vs {diaAnterior}</span>
              )}
            </div>
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

      {/* HL breakdown table — con selector de SEMANA (mismo desglose, filtrado por semana) */}
      <HLBreakdown vendor={vendor} />

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
                  <th className="px-3 py-2 text-right">Empaques</th>
                  <th className="px-3 py-2 text-right">Importe</th>
                  <th className="px-3 py-2 text-right">% del total</th>
                </tr>
              </thead>
              <tbody>
                {vendor.top_productos.map((p, i) => {
                  const pctProd = vendor.total_importe > 0
                    ? Math.round((p.total / vendor.total_importe) * 100)
                    : "0.0";
                  return (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-3 py-2 text-slate-400">{i + 1}</td>
                      <td className="px-3 py-2 font-medium">{p.producto}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(p.cantidad ?? 0, 0)}</td>
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

// Desglose de HL (Malta/Parranda × 330/500/1500) con selector de SEMANA. "Todo el mes"
// usa los totales del vendedor; una semana usa el desglose semanal (sku_semanal).
function HLBreakdown({ vendor }) {
  const [semana, setSemana] = useState("");
  const weeks = vendor.weeks_disponibles || [];
  const single = semana && weeks.includes(semana);
  const sku = vendor.sku_semanal || [];
  const sizeLabel = { "330": "330 ml", "500": "500 ml", "1500": "1.5 L" };
  const hlOf = (prod, size) => {
    if (!single) return vendor[`${prod.toLowerCase()}_${size}`] || 0;
    const row = sku.find((r) => r.formato === `${prod} ${sizeLabel[size]}`);
    return row ? (row.semanal[semana] || 0) : 0;
  };
  const rowTot = (prod) => hlOf(prod, "330") + hlOf(prod, "500") + hlOf(prod, "1500");
  const colTot = (size) => hlOf("Malta", size) + hlOf("Parranda", size);
  const grand = rowTot("Malta") + rowTot("Parranda");

  return (
    <div className="card">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <h4 className="font-semibold">
          Desglose Hectolitros (Malta / Parranda){single ? ` · ${semana}` : ""}
        </h4>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Semana:</label>
          <select
            className="input text-xs py-1 px-2 w-auto"
            value={semana}
            onChange={(e) => setSemana(e.target.value)}
          >
            <option value="">Todo el mes</option>
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
              <th className="px-3 py-2 text-left">Producto</th>
              <th className="px-3 py-2 text-right">330 ml</th>
              <th className="px-3 py-2 text-right">500 ml</th>
              <th className="px-3 py-2 text-right">1500 ml</th>
              <th className="px-3 py-2 text-right font-bold">Total HL</th>
            </tr>
          </thead>
          <tbody>
            {["Malta", "Parranda"].map((prod) => (
              <tr key={prod} className="border-t border-slate-100">
                <td className="px-3 py-2 font-medium">{prod}</td>
                <td className="px-3 py-2 text-right">{formatNumber(hlOf(prod, "330"))}</td>
                <td className="px-3 py-2 text-right">{formatNumber(hlOf(prod, "500"))}</td>
                <td className="px-3 py-2 text-right">{formatNumber(hlOf(prod, "1500"))}</td>
                <td className="px-3 py-2 text-right font-semibold">{formatNumber(rowTot(prod))}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-slate-300 bg-slate-50">
              <td className="px-3 py-2 font-bold">Total</td>
              <td className="px-3 py-2 text-right font-bold">{formatNumber(colTot("330"))}</td>
              <td className="px-3 py-2 text-right font-bold">{formatNumber(colTot("500"))}</td>
              <td className="px-3 py-2 text-right font-bold">{formatNumber(colTot("1500"))}</td>
              <td className="px-3 py-2 text-right font-bold text-brand-700">{formatNumber(grand)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
