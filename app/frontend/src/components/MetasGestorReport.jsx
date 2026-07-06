import { formatMoney, formatNumber } from "./Kpi.jsx";
import { cn } from "./ui.jsx";

// Filas de cada tabla (como el reporte del script).
const MENSUAL_ROWS = [
  { label: "Meta Total", key: "meta_total", type: "num" },
  { label: "Meta Acumulada", key: "meta_acum", type: "num" },
  { label: "Venta Acumulada", key: "venta_acum", type: "num" },
  { label: "Ultimo Crecimiento", key: "venta_dia", type: "num" },
  { label: "Delta Acumulada", key: "delta_acum", type: "delta" },
  { label: "Delta Acumulada en %", key: "delta_acum_pct", type: "deltapct" },
  { label: "% del Total", key: "pct_total", type: "cumplpct" },
];
const DIARIO_ROWS = [
  { label: "Meta Dia", key: "meta_dia", type: "num" },
  { label: "Venta Dia", key: "venta_dia", type: "num" },
  { label: "Delta Dia", key: "delta_dia", type: "delta" },
  { label: "Delta Dia en %", key: "delta_dia_pct", type: "deltapct" },
  { label: "% Cumplimiento Dia", key: "cumpl_dia_pct", type: "cumplpct" },
];

function cellClass(type, v) {
  if (type === "stock") return "bg-amber-50 text-amber-800";
  if (type === "delta" || type === "deltapct") return v >= 0 ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700";
  if (type === "cumplpct") return v >= 100 ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700";
  return "";
}
function cellVal(type, v) {
  if (type === "deltapct" || type === "cumplpct") return `${Math.round(v)}%`;
  return formatNumber(v, 2);
}

function FormatoTable({ title, rows, block, formatos }) {
  return (
    <div>
      <div className="bg-brand-800 text-white text-center font-semibold text-sm py-1.5 rounded-t-lg">{title}</div>
      <div className="overflow-x-auto scroll-thin border border-slate-200 rounded-b-lg">
        <table className="tbl">
          <thead>
            <tr>
              <th>Indicador</th>
              {formatos.map((f) => <th key={f} className="!text-right">{f}</th>)}
              <th className="!text-right !bg-slate-200/70">TOTAL</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const row = block[r.key] || {};
              return (
                <tr key={r.key}>
                  <td className="font-medium bg-brand-50/50 whitespace-nowrap">{r.label}</td>
                  {formatos.map((f) => (
                    <td key={f} className={cn("text-right tabular-nums", cellClass(r.type, Number(row[f] || 0)))}>{cellVal(r.type, Number(row[f] || 0))}</td>
                  ))}
                  <td className={cn("text-right tabular-nums font-semibold", cellClass(r.type, Number(row.TOTAL || 0)))}>{cellVal(r.type, Number(row.TOTAL || 0))}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Tabla "Resumen general por vendedor" + TOTAL GENERAL (una fila por vendedor).
export function GeneralTable({ data, sel, onSel }) {
  if (!data?.general?.length) return null;
  return (
    <div className="overflow-x-auto scroll-thin border border-slate-200 rounded-lg">
      <table className="tbl">
        <thead>
          <tr>
            <th>Vendedor</th>
            <th className="!text-right">Venta $</th><th className="!text-right">HL</th>
            <th className="!text-right">Meta HL</th><th className="!text-right">% Cumpl.</th>
            <th className="!text-right">V. Día</th><th className="!text-right">Meta Día</th><th className="!text-right">% Día</th>
          </tr>
        </thead>
        <tbody>
          {data.general.map((r) => (
            <tr key={r.gestor} className={cn(onSel && "cursor-pointer hover:bg-slate-50", sel === r.gestor && "bg-brand-50/60")} onClick={() => onSel?.(r.gestor)}>
              <td className="font-medium">{r.gestor}</td>
              <td className="text-right tabular-nums">{formatMoney(r.total_importe)}</td>
              <td className="text-right tabular-nums font-semibold">{formatNumber(r.total_hl, 2)}</td>
              <td className="text-right tabular-nums text-slate-500">{formatNumber(r.meta_hl, 2)}</td>
              <td className={cn("text-right tabular-nums font-medium", r.cumpl_hl_pct >= 100 ? "text-emerald-600" : "text-red-600")}>{Math.round(r.cumpl_hl_pct)}%</td>
              <td className="text-right tabular-nums">{formatNumber(r.venta_dia, 2)}</td>
              <td className="text-right tabular-nums text-slate-500">{formatNumber(r.meta_dia, 2)}</td>
              <td className={cn("text-right tabular-nums", r.cumpl_dia_pct >= 100 ? "text-emerald-600" : "text-red-600")}>{Math.round(r.cumpl_dia_pct)}%</td>
            </tr>
          ))}
          {data.total_general && (
            <tr className="bg-slate-800 text-white font-semibold">
              <td className="px-3 py-2">TOTAL GENERAL</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatMoney(data.total_general.total_importe)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatNumber(data.total_general.total_hl, 2)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatNumber(data.total_general.meta_hl, 2)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{Math.round(data.total_general.cumpl_hl_pct)}%</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatNumber(data.total_general.venta_dia, 2)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatNumber(data.total_general.meta_dia, 2)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{Math.round(data.total_general.cumpl_dia_pct)}%</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// Tablas por formato (mensual + diario) de UN vendedor. Sin selector propio.
export function VendorFormatoTables({ block, formatos }) {
  if (!block) return null;
  return (
    <div className="space-y-4">
      <FormatoTable title={`${block.gestor} — Resumen mensual (HL)`} rows={MENSUAL_ROWS} block={block.mensual} formatos={formatos} />
      <FormatoTable title={`${block.gestor} — Resumen diario (HL)`} rows={DIARIO_ROWS} block={block.diario} formatos={formatos} />
    </div>
  );
}
