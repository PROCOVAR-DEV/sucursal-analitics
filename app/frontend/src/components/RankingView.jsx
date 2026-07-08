import { Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getRanking } from "../api.js";
import { LineCard } from "./Charts.jsx";
import { formatMoney } from "./Kpi.jsx";

const MEDAL = { 1: "🥇", 2: "🥈", 3: "🥉" };
const MONTHS_ES = {
  1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
  5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
  9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
};

/** Extracts month number from a week label like "30/03 - 03/04" (uses end date). */
function weekMonth(semana) {
  const parts = semana.split(" - ");
  const end = parts[parts.length - 1]; // "03/04"
  return parseInt(end.split("/")[1], 10);
}

export default function RankingView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [selMonth, setSelMonth] = useState(null);
  const [selWeek, setSelWeek] = useState(null);

  useEffect(() => {
    setData(null); setErr(null); setSelMonth(null); setSelWeek(null);
    getRanking(sourceId, period)
      .then(setData)
      .catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sourceId, period]);

  const diarioChart = useMemo(() => {
    if (!data) return { series: [], data: [] };
    const vendedores = [...new Set(data.diario.map((r) => r.vendedor))];
    const fechas = [...new Set(data.diario.map((r) => r.fecha))].sort();
    const byFecha = {};
    for (const f of fechas) byFecha[f] = { fecha: f };
    for (const r of data.diario) byFecha[r.fecha][r.vendedor] = r.acumulado;
    return { series: vendedores.map((v) => ({ key: v, label: v })), data: fechas.map((f) => byFecha[f]) };
  }, [data]);

  /** Unique months found in semanal data, sorted ascending. */
  const months = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.semanal.map((r) => weekMonth(r.semana)))].sort((a, b) => a - b);
  }, [data]);

  const activeMonth = selMonth ?? months[months.length - 1] ?? null;

  /** Unique week labels in the selected month, sorted. */
  const weeksInMonth = useMemo(() => {
    if (!data || activeMonth === null) return [];
    return [
      ...new Set(
        data.semanal
          .filter((r) => weekMonth(r.semana) === activeMonth)
          .map((r) => r.semana)
      ),
    ].sort();
  }, [data, activeMonth]);

  const activeWeek =
    selWeek && weeksInMonth.includes(selWeek) ? selWeek : weeksInMonth[0] ?? null;

  const weekRanking = useMemo(() => {
    if (!data || !activeWeek) return [];
    return data.semanal.filter((r) => r.semana === activeWeek);
  }, [data, activeWeek]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Trophy className="text-amber-500" /> Ranking de ventas
        </h2>
      </div>

      {/* General ranking */}
      <div className="card">
        <h3 className="font-semibold mb-3">General (acumulado total)</h3>
        <div className="overflow-x-auto scroll-thin">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">Vendedor</th>
              <th className="px-3 py-2 text-right">Ventas</th>
            </tr>
          </thead>
          <tbody>
            {data.general.map((r) => (
              <tr key={r.vendedor} className="border-t border-slate-100">
                <td className="px-3 py-2 text-xl">{MEDAL[r.posicion] || r.posicion}</td>
                <td className="px-3 py-2 font-medium">{r.vendedor}</td>
                <td className="px-3 py-2 text-right font-semibold">{formatMoney(r.ventas)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* Daily evolution chart */}
      <LineCard
        title="Acumulado diario por vendedor"
        subtitle="Evolución del monto acumulado por día"
        data={diarioChart.data}
        xKey="fecha"
        series={diarioChart.series}
      />

      {/* Weekly ranking with month selector + week tabs */}
      <div className="card space-y-4">
        <h3 className="font-semibold">Por semana</h3>

        {/* Month selector */}
        {months.length > 1 && (
          <div className="flex gap-2 flex-wrap">
            {months.map((m) => (
              <button
                key={m}
                className={`tab ${m === activeMonth ? "tab-active" : ""}`}
                onClick={() => { setSelMonth(m); setSelWeek(null); }}
              >
                {MONTHS_ES[m] ?? m}
              </button>
            ))}
          </div>
        )}

        {/* Week tabs */}
        {weeksInMonth.length > 1 && (
          <div className="flex gap-2 flex-wrap border-b border-slate-200 pb-3">
            {weeksInMonth.map((w) => (
              <button
                key={w}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  w === activeWeek
                    ? "bg-brand-100 text-brand-700 border border-brand-300"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
                onClick={() => setSelWeek(w)}
              >
                {w}
              </button>
            ))}
          </div>
        )}

        {/* Ranking table for selected week */}
        {activeWeek && (
          <div>
            <p className="text-xs text-slate-500 mb-2">Semana: {activeWeek}</p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-100">
                  <tr>
                    <th className="px-3 py-2 text-left">#</th>
                    <th className="px-3 py-2 text-left">Vendedor</th>
                    <th className="px-3 py-2 text-right">Ventas</th>
                  </tr>
                </thead>
                <tbody>
                  {weekRanking.map((r, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-3 py-2 text-xl">{MEDAL[r.posicion] || r.posicion}</td>
                      <td className="px-3 py-2 font-medium">{r.vendedor}</td>
                      <td className="px-3 py-2 text-right font-semibold">{formatMoney(r.ventas)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {!activeWeek && (
          <p className="text-sm text-slate-500">No hay datos de semanas disponibles.</p>
        )}
      </div>
    </div>
  );
}
