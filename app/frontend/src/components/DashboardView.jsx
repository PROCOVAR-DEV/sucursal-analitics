import { useEffect, useState } from "react";
import { getDashboard } from "../api.js";
import { Kpi, formatInt, formatMoney, formatNumber } from "./Kpi.jsx";
import { RankingBarras } from "./Charts.jsx";
import { Competencia } from "./Competencia.jsx";

export default function DashboardView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    // `cancelled` descarta respuestas VIEJAS: al abrir, el periodo aún es null y se pide el
    // acumulado (lento, muchas filas); cuando entra el mes se pide lo filtrado (rápido). Sin
    // esta guarda, la respuesta lenta del acumulado llegaba después y PISABA a la del mes.
    let cancelled = false;
    setData(null); setErr(null);
    getDashboard(sourceId, period)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });
    return () => { cancelled = true; };
  }, [sourceId, period]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  const { kpis } = data;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold">Resumen General</h2>
          <p className="text-sm text-slate-500">
            {sourceId === "accumulated" ? "Acumulado global · " : ""}
            Periodo: {data.rango} · {data.filas.toLocaleString("es-CO")} filas
          </p>
          {/* Dónde fue a parar lo que estaba aquí.
              Se quitaron dos bloques que eran copia literal de otras pestañas —el gráfico
              de hectolitros por gestor y la tabla de cumplimiento por producto—, y quien
              los buscaba tiene que poder encontrarlos sin preguntar. Este aviso se borra
              cuando la gente ya sepa dónde están. */}
          <p className="text-xs text-slate-400 mt-1">
            Los hectolitros por gestor están en <b>Ventas (HL)</b> · el cumplimiento por
            producto, en <b>Productos</b>.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Hectolitros" value={formatNumber(kpis.total_hectolitros, 2)} hint={`Meta: ${formatNumber(kpis.meta_hectolitros, 0)}`} />
        <Kpi label="% Cumplimiento" value={`${formatNumber(kpis.cumplimiento_pct, 1)} %`}
          tone={kpis.cumplimiento_pct >= 100 ? "green" : kpis.cumplimiento_pct >= 80 ? "amber" : "red"} />
        <Kpi label="Venta Total" value={formatMoney(kpis.total_importe)} tone="slate" />
        <Kpi label="Clientes" value={formatInt(kpis.total_clientes)}
          hint={`${formatInt(kpis.total_skus)} SKUs vendidos`} tone="brand" />
      </div>

      {/* UN SOLO GRÁFICO PRINCIPAL, y es el que contesta «¿quién está tirando?».
          Aquí había dos del mismo tamaño compitiendo: «Hectolitros por gestor» —que es
          EXACTAMENTE el mismo panel que abre la pestaña Ventas (HL)— y la tarta del
          ranking. El primero se quitó por repetido; el segundo pasó a barras porque una
          tarta con veinticinco porciones no se puede leer. */}
      <RankingBarras
        data={data.ranking_general}
        nameKey="vendedor"
        subtitle="Por vendedor, tal como viene el nombre en Ventra — un gestor puede aparecer con varios. Los diez primeros por importe; el resto, sumado en «otros»."
        title="Quién vende más"
        valueKey="ventas"
      />

      {/* LA TABLA DE POSICIONES.
          Va aquí, en la primera pantalla, y no en una pestaña propia: es lo primero que
          quiere saber quien entra —«¿voy bien?»— y una cifra de cumplimiento no significa
          nada sin saber por dónde van los demás.
          Se pinta sola o no se pinta: en «Todas las sucursales» no aplica y desaparece sin
          dejar un hueco. */}
      <Competencia period={period} sourceId={sourceId} />

      {/* Desglose GENERAL por formato (hectolitros, no dinero) — cada SKU de Parranda y Malta */}
      {Array.isArray(data.desglose_formato) && data.desglose_formato.length > 0 && (
        <div className="card">
          <h3 className="font-semibold mb-1">Desglose general por formato</h3>
          <p className="text-sm text-slate-500 mb-3">
            Hectolitros por SKU de Cerveza Parranda y Malta Guajira (todos los vendedores)
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {["Parranda", "Malta"].map((prod) => {
              const rows = data.desglose_formato.filter((r) => r.producto === prod);
              const subtotal = rows.reduce((s, r) => s + (r.hectolitros || 0), 0);
              return (
                <div key={prod} className="rounded-xl border border-slate-200 overflow-hidden">
                  <div className="px-4 py-2.5 bg-slate-700 text-white flex items-center justify-between">
                    <span className="font-semibold">{prod}</span>
                    <span className="text-sm tabular-nums">{formatNumber(subtotal, 2)} HL</span>
                  </div>
                  <table className="w-full text-sm">
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.formato} className="border-t border-slate-100">
                          <td className="px-4 py-2 text-slate-700">{r.tamano}</td>
                          <td className="px-4 py-2 text-right font-mono tabular-nums text-slate-900">
                            {formatNumber(r.hectolitros, 2)} HL
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })}
          </div>
          <div className="mt-3 pt-3 border-t border-slate-200 flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-600">Total (Malta + Parranda)</span>
            <span className="text-lg font-bold text-brand-700 tabular-nums">
              {formatNumber(data.desglose_formato.reduce((s, r) => s + (r.hectolitros || 0), 0), 2)} HL
            </span>
          </div>
        </div>
      )}

    </div>
  );
}
