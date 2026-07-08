import { formatMoney, formatNumber } from "./Kpi.jsx";
import { cn } from "./ui.jsx";

// Nombres legibles de cada formato.
const FMT_LABEL = {
  P1500: "Parranda 1.5 L", P500: "Parranda 500 ml", P330: "Parranda 330 ml",
  M1500: "Malta 1.5 L", M500: "Malta 500 ml", M330: "Malta 330 ml",
};
const FMT_TONE = { P: "bg-brand-500", M: "bg-amber-500" };
const label = (f) => FMT_LABEL[f] || f;
const num = (v) => formatNumber(Number(v) || 0, 2);

function pctColor(p) {
  return p >= 100 ? "text-emerald-600" : p >= 80 ? "text-amber-600" : "text-red-600";
}
function barColor(p) {
  return p >= 100 ? "bg-emerald-500" : p >= 80 ? "bg-amber-500" : "bg-red-500";
}

function Bar({ pct }) {
  const p = Math.max(0, Math.min(pct, 100));
  return (
    <div className="flex items-center gap-2 min-w-[130px]">
      <div className="h-2 flex-1 bg-slate-100 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", barColor(pct))} style={{ width: `${p}%` }} />
      </div>
      <span className={cn("text-xs font-bold tabular-nums w-11 text-right", pctColor(pct))}>{Math.round(pct)}%</span>
    </div>
  );
}

function Delta({ v }) {
  const n = Number(v) || 0;
  return <span className={cn("tabular-nums font-medium", n >= 0 ? "text-emerald-600" : "text-red-600")}>{n >= 0 ? "+" : ""}{num(n)}</span>;
}

// Toma las filas presentes (con meta o venta > 0) para no llenar de ceros.
function activeFormatos(formatos, ...rows) {
  return formatos.filter((f) => rows.some((r) => Math.abs(Number(r?.[f]) || 0) > 0.0001));
}

// Tabla profesional: una fila por producto, con barra de cumplimiento.
function CumplTable({ title, subtitle, tone, rows }) {
  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden">
      <div className={cn("px-4 py-2.5 text-white", tone)}>
        <div className="font-semibold text-sm">{title}</div>
        {subtitle && <div className="text-[11px] text-white/80">{subtitle}</div>}
      </div>
      <div className="overflow-x-auto scroll-thin">
      <table className="tbl">
        <thead>
          <tr>
            <th>Producto</th>
            <th className="!text-right">Meta</th>
            <th className="!text-right">Vendido</th>
            <th className="!text-left !pl-4">Cumplimiento</th>
            <th className="!text-right">Δ vs meta</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.f}>
              <td className="whitespace-nowrap">
                <span className="inline-flex items-center gap-2">
                  <span className={cn("w-2 h-2 rounded-full", FMT_TONE[r.f[0]] || "bg-slate-400")} />
                  <span className="font-medium text-slate-700">{label(r.f)}</span>
                </span>
              </td>
              <td className="text-right tabular-nums text-slate-500">{num(r.meta)}</td>
              <td className="text-right tabular-nums font-semibold text-slate-800">{num(r.real)}</td>
              <td className="pl-4"><Bar pct={r.pct} /></td>
              <td className="text-right"><Delta v={r.delta} /></td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="bg-slate-800 text-white font-semibold">
            <td className="px-3 py-2.5">TOTAL</td>
            <td className="px-3 py-2.5 text-right tabular-nums">{num(rows.reduce((s, r) => s + r.meta, 0))}</td>
            <td className="px-3 py-2.5 text-right tabular-nums">{num(rows.reduce((s, r) => s + r.real, 0))}</td>
            <td className="px-3 py-2.5">
              {(() => {
                const m = rows.reduce((s, r) => s + r.meta, 0), v = rows.reduce((s, r) => s + r.real, 0);
                const p = m ? (v / m) * 100 : 0;
                return <div className="flex items-center gap-2"><div className="h-2 flex-1 bg-white/25 rounded-full overflow-hidden"><div className={cn("h-full rounded-full", barColor(p))} style={{ width: `${Math.min(p, 100)}%` }} /></div><span className="text-xs font-bold w-11 text-right tabular-nums">{Math.round(p)}%</span></div>;
              })()}
            </td>
            <td className="px-3 py-2.5 text-right tabular-nums">{(() => { const d = rows.reduce((s, r) => s + r.delta, 0); return `${d >= 0 ? "+" : ""}${num(d)}`; })()}</td>
          </tr>
        </tfoot>
      </table>
      </div>
    </div>
  );
}

// Tablas por formato (acumulado del mes + del día) de UN vendedor.
export function VendorFormatoTables({ block, formatos }) {
  if (!block) return null;
  const m = block.mensual, d = block.diario;

  // Sin metas por formato configuradas: avisar en vez de mostrar ceros.
  const metaFmtTotal = formatos.reduce((s, f) => s + (Number(m.meta_total[f]) || 0), 0);
  if (metaFmtTotal < 0.01) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        <b>{block.gestor}</b> no tiene metas por formato configuradas, por eso el desglose por producto
        aparece vacío. Ve a <b>Config → Calculadora de metas</b>, carga o ajusta el plan y pulsa
        <b> “Guardar todas las metas”</b>. (La cuota total sí está: {num(block.totales?.meta_hl || 0)} HL.)
      </div>
    );
  }

  const fmts = activeFormatos(formatos, m.meta_total, m.venta_acum, d.venta_dia);

  const mesRows = fmts.map((f) => {
    const meta = Number(m.meta_acum[f]) || 0;      // meta a la fecha (acumulada)
    const real = Number(m.venta_acum[f]) || 0;
    return { f, meta, real, pct: meta ? (real / meta) * 100 : (real > 0 ? 100 : 0), delta: Number(m.delta_acum[f]) || 0 };
  });
  const diaRows = fmts.map((f) => {
    const meta = Number(d.meta_dia[f]) || 0;
    const real = Number(d.venta_dia[f]) || 0;
    return { f, meta, real, pct: Number(d.cumpl_dia_pct[f]) || 0, delta: Number(d.delta_dia[f]) || 0 };
  });

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <CumplTable title="Acumulado del mes (HL)" subtitle="Vendido vs. meta a la fecha, por producto" tone="bg-brand-700" rows={mesRows} />
      <CumplTable title="Ventas del día (HL)" subtitle="Vendido hoy vs. meta diaria, por producto" tone="bg-slate-700" rows={diaRows} />
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
            <th className="!text-right">Meta HL</th><th className="!text-left !pl-4">Cumplimiento</th>
          </tr>
        </thead>
        <tbody>
          {data.general.map((r) => (
            <tr key={r.gestor} className={cn(onSel && "cursor-pointer hover:bg-slate-50", sel === r.gestor && "bg-brand-50/60")} onClick={() => onSel?.(r.gestor)}>
              <td className="font-medium">{r.gestor}</td>
              <td className="text-right tabular-nums">{formatMoney(r.total_importe)}</td>
              <td className="text-right tabular-nums font-semibold">{num(r.total_hl)}</td>
              <td className="text-right tabular-nums text-slate-500">{num(r.meta_hl)}</td>
              <td className="pl-4"><Bar pct={r.cumpl_hl_pct} /></td>
            </tr>
          ))}
          {data.total_general && (
            <tr className="bg-slate-800 text-white font-semibold">
              <td className="px-3 py-2.5">TOTAL GENERAL</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatMoney(data.total_general.total_importe)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{num(data.total_general.total_hl)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{num(data.total_general.meta_hl)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{Math.round(data.total_general.cumpl_hl_pct)}%</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
