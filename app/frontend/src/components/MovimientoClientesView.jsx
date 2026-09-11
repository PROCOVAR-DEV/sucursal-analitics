import { UserMinus, UserPlus, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { getMovimientoClientes } from "../api.js";
import FiltroMulti from "./FiltroMulti.jsx";
import { Kpi, formatInt, formatMoney } from "./Kpi.jsx";
import { Panel, PanelHeader, cn } from "./ui.jsx";

/**
 * Quién entró y quién dejó de comprar.
 *
 * # Por qué hacía falta
 *
 * La app sabía decir cuánto se vendió, a quién y de qué. No sabía decir **quién dejó de
 * comprar** — y eso es lo que se pierde sin que nadie lo note: el importe del mes puede
 * quedar igual mientras por debajo entran cinco clientes y se van otros cinco más
 * grandes. Un cliente que deja de comprar no sale en ninguna lista de ventas,
 * precisamente porque no vendió.
 *
 * # Por qué salen los nombres
 *
 * Saber que se perdieron once clientes no sirve de nada. Saber CUÁLES y cuánto compraban
 * es una lista de llamadas para mañana. Por eso los perdidos van ordenados por lo que
 * compraban, no por orden alfabético: el primero de la lista es el que más duele.
 */
export default function MovimientoClientesView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [grupos, setGrupos] = useState([]);
  const [abierto, setAbierto] = useState(null);

  useEffect(() => {
    let cancelado = false;

    setData(null);
    setErr(null);
    getMovimientoClientes(sourceId, period, grupos)
      .then((d) => { if (!cancelado) setData(d); })
      .catch((e) => { if (!cancelado) setErr(e?.response?.data?.detail || e.message); });

    return () => { cancelado = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId, period, grupos.join("|")]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;

  const o = data.oficina;

  if (!o) return <div className="p-6 text-sm text-slate-400">No hay datos para este periodo.</div>;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Users className="text-brand-600" /> Quién entró y quién se fue
          </h2>
          {/* Contra QUÉ se compara, escrito: sin esto, «11 perdidos» no se puede
              comprobar ni discutir. */}
          <p className="text-sm text-slate-500">
            {data.rango_actual} comparado con los {data.dias} días de antes ({data.rango_anterior})
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

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Nuevos" value={formatInt(o.nuevos)} tone="green"
          hint={`${formatMoney(o.importe_nuevos)} que antes no estaban`} />
        <Kpi label="Recuperados" value={formatInt(o.recuperados)} tone="brand"
          hint={`${formatMoney(o.importe_recuperados)} · compraban antes y volvieron`} />
        <Kpi label="Se mantienen" value={formatInt(o.mantenidos)} tone="slate" />
        {/* El que importa y el único que no se ve en ninguna otra pantalla. */}
        <Kpi label="Perdidos" value={formatInt(o.perdidos)} tone="amber"
          hint={`${formatMoney(o.importe_perdido)} que compraban y ya no`} />
      </div>

      <Panel>
        <PanelHeader
          icon={UserMinus}
          title="Por vendedor"
          sub="Ordenado por lo que se dejó de vender, no por cuántos clientes: perder tres pequeños no es perder uno grande"
        />
        <div className="overflow-x-auto scroll-thin">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Vendedor</th>
                <th className="px-3 py-2 text-right font-semibold">Nuevos</th>
                <th className="px-3 py-2 text-right font-semibold">Recuperados</th>
                <th className="px-3 py-2 text-right font-semibold">Se mantienen</th>
                <th className="px-3 py-2 text-right font-semibold">Perdidos</th>
                <th className="px-3 py-2 text-right font-semibold">Dejó de vender</th>
                <th className="px-3 py-2 text-right font-semibold">Clientes antes → ahora</th>
              </tr>
            </thead>
            <tbody>
              {data.por_gestor.map((g) => {
                const open = abierto === g.gestor;
                const creció = g.clientes_ahora >= g.clientes_antes;

                return (
                  <tr key={g.gestor} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                    onClick={() => setAbierto(open ? null : g.gestor)}>
                    <td className="px-3 py-1.5 font-medium">{g.nombre}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-emerald-600">{formatInt(g.nuevos)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-brand-600">{formatInt(g.recuperados)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{formatInt(g.mantenidos)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-semibold text-red-600">{formatInt(g.perdidos)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{formatMoney(g.importe_perdido)}</td>
                    <td className={cn("px-3 py-1.5 text-right tabular-nums", creció ? "text-emerald-600" : "text-red-600")}>
                      {formatInt(g.clientes_antes)} → {formatInt(g.clientes_ahora)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* La lista de llamadas. Saber que se perdieron once no sirve; saber cuáles, sí. */}
      {data.por_gestor.filter((g) => g.lista_perdidos?.length).map((g) => (
        <Panel key={g.gestor}>
          <PanelHeader
            icon={UserPlus}
            title={`${g.nombre} — a quién llamar`}
            sub={`${g.perdidos} clientes que compraban y este periodo no, por lo que compraban`}
          />
          <div className="p-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {g.lista_perdidos.map((c) => (
              <div key={c.cliente} className="flex items-baseline justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2">
                <span className="truncate text-sm">{c.cliente}</span>
                <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-600">{formatMoney(c.compraba)}</span>
              </div>
            ))}
          </div>
        </Panel>
      ))}
    </div>
  );
}
