import { AlarmClock, Target } from "lucide-react";
import { useEffect, useState } from "react";

import { getClientesDormidos } from "../api.js";
import FiltroMulti from "./FiltroMulti.jsx";
import { Kpi, formatInt, formatMoney, formatNumber } from "./Kpi.jsx";
import { Panel, PanelHeader, cn } from "./ui.jsx";

/**
 * Quién lleva sin comprar, medido contra SU propio ritmo.
 *
 * «Perdido» depende de dónde se pongan los cortes del periodo: quien compra cada cinco
 * semanas sale perdido un mes y recuperado al siguiente sin que haya pasado nada. Los días
 * sin comprar no dependen de ningún corte.
 *
 * Y cada cliente se compara consigo mismo: uno que compra cada quince días y lleva veinte
 * está empezando a irse; otro que compra cada dos meses y lleva veinte no tiene nada de
 * raro. Un umbral igual para todos marcaría al segundo y dejaría pasar al primero.
 */
export default function ClientesDormidosView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [grupos, setGrupos] = useState([]);
  const [abierto, setAbierto] = useState(null);

  useEffect(() => {
    let cancelado = false;

    setData(null);
    setErr(null);
    getClientesDormidos(sourceId, period, grupos)
      .then((d) => { if (!cancelado) setData(d); })
      .catch((e) => { if (!cancelado) setErr(e?.response?.data?.detail || e.message); });

    return () => { cancelado = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId, period, grupos.join("|")]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;
  if (!data.totales) return <div className="p-6 text-sm text-slate-400">No hay datos suficientes.</div>;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <AlarmClock className="text-brand-600" /> Quién lleva sin comprar
          </h2>
          {/* Se cuenta hasta el último día CON DATOS, no hasta hoy: si Ventra no ha traído
              lo de hoy, contra hoy todo el mundo llevaría un día de más. */}
          <p className="text-sm text-slate-500">
            Contado hasta el {data.hasta}, el último día con datos. Cada cliente contra
            su propio ritmo de compra.
          </p>
        </div>
        {data.grupos_disponibles?.length > 1 && (
          <FiltroMulti
            etiqueta="Grupo"
            opciones={data.grupos_disponibles}
            valor={grupos}
            onChange={setGrupos}
            textoTodos="Todos los grupos"
          />
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <Kpi label="Clientes dormidos" value={formatInt(data.totales.dormidos)} tone="amber"
          hint="Llevan más del doble de lo que suelen tardar" />
        <Kpi label="Lo que compraban" value={formatMoney(data.totales.importe_dormido)} tone="brand" />
        <Kpi label="Clientes en total" value={formatInt(data.totales.clientes)} tone="slate" />
      </div>

      <Panel>
        <PanelHeader
          icon={AlarmClock}
          title="Por vendedor"
          sub="Ordenado por lo que compraban los dormidos: un cliente grande callado pesa más que cinco pequeños"
        />
        <div className="overflow-x-auto scroll-thin">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Vendedor</th>
                <th className="px-3 py-2 text-right font-semibold">Clientes</th>
                <th className="px-3 py-2 text-right font-semibold">Dormidos</th>
                <th className="px-3 py-2 text-right font-semibold">Compraban</th>
                <th className="px-3 py-2 text-right font-semibold">
                  Depende de 5
                  <span className="block font-normal normal-case text-[10px] text-slate-400">
                    % en sus cinco mayores
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.por_gestor.map((g) => (
                <tr key={g.gestor} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                  onClick={() => setAbierto(abierto === g.gestor ? null : g.gestor)}>
                  <td className="px-3 py-1.5 font-medium">{g.nombre}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{formatInt(g.clientes)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums font-semibold text-amber-600">{formatInt(g.dormidos)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{formatMoney(g.importe_dormido)}</td>
                  {/* Teñido por encima del 60%: no es un fallo, es un riesgo — su mes
                      depende de que no se caiga uno. */}
                  <td className={cn("px-3 py-1.5 text-right tabular-nums",
                    g.concentracion_pct >= 60 ? "font-semibold text-red-600" : "text-slate-600")}>
                    {formatNumber(g.concentracion_pct, 0)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {data.por_gestor.filter((g) => g.lista?.length).map((g) => (
        <Panel key={g.gestor}>
          <PanelHeader
            icon={Target}
            title={`${g.nombre} — callados`}
            sub={`${g.dormidos} clientes que llevan más del doble de lo que suelen tardar`}
          />
          <div className="overflow-x-auto scroll-thin">
            <table className="min-w-full text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Cliente</th>
                  <th className="px-3 py-2 text-right font-semibold">Sin comprar</th>
                  <th className="px-3 py-2 text-right font-semibold">Suele tardar</th>
                  <th className="px-3 py-2 text-right font-semibold">Última compra</th>
                  <th className="px-3 py-2 text-right font-semibold">Compraba</th>
                </tr>
              </thead>
              <tbody>
                {g.lista.map((c) => (
                  <tr key={c.cliente} className="border-t border-slate-100">
                    <td className="px-3 py-1.5">{c.cliente}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-semibold text-amber-600">
                      {formatInt(c.dias_sin_comprar)} días
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">
                      cada {formatNumber(c.suele_tardar, 0)}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{c.ultima_compra}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-medium">{formatMoney(c.compraba)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ))}
    </div>
  );
}
