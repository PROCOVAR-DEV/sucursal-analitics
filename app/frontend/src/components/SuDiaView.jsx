import { CalendarDays, ChevronDown, Package, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { getDiario } from "../api.js";
import { Kpi, formatInt, formatMoney, formatNumber } from "./Kpi.jsx";
import { Panel, PanelHeader, Select, cn } from "./ui.jsx";

/**
 * «Su día» — qué hizo un comercial cada día: a quién le vendió y qué le vendió.
 *
 * # Por qué no bastaba con los números
 *
 * El servicio ya daba, por día, el importe, los hectolitros, las operaciones y cuántos
 * clientes. Con eso se sabe si el día fue bueno o malo y no se puede hacer nada al
 * respecto: para actuar hay que ver los NOMBRES —a quién le vendió y qué—, que es lo
 * que pidieron desde Santiago.
 *
 * # Quién ve qué
 *
 * El servidor manda: al rol `gestor` le recorta los gestores efectivos al suyo antes de
 * mirar una sola fila, así que pedir el de otro no devuelve datos ajenos, devuelve
 * vacío. Aquí solo se corresponde con eso escondiendo un selector que no puede usar.
 * Supervisores y admin sí eligen: el general de la sucursal, o uno por uno.
 *
 * # Por qué los días se despliegan
 *
 * Un mes son veintitantos días y cada uno trae sus clientes y sus productos. Todo
 * abierto es un muro de texto donde no se encuentra nada; todo cerrado obliga a abrir
 * uno a uno para saber cuál mirar. Cerrados PERO con el resumen del día en la fila
 * —hectolitros contra meta, importe, cuántos clientes— se elige cuál abrir de un
 * vistazo, y solo se abre ese.
 */
export default function SuDiaView({ sourceId, period, user }) {
  const esGestor = user?.role === "gestor";
  const [gestor, setGestor] = useState(esGestor ? String(user?.gestor || "").toUpperCase() : "");
  const [grupo, setGrupo] = useState("");
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [abierto, setAbierto] = useState(null);

  useEffect(() => {
    // Se descartan las respuestas viejas: al cambiar de gestor o de grupo con la red
    // lenta, la anterior puede llegar después y pisar la buena.
    let cancelado = false;

    setData(null);
    setErr(null);
    getDiario(sourceId, period, gestor || null, grupo || null)
      .then((d) => { if (!cancelado) setData(d); })
      .catch((e) => { if (!cancelado) setErr(e?.response?.data?.detail || e.message); });

    return () => { cancelado = true; };
  }, [sourceId, period, gestor, grupo]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;

  const dias = [...(data.dias || [])].reverse(); // el último día arriba: es el que se mira
  const t = data.totales || {};

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        {!esGestor && (
          <Select
            width="w-56"
            value={gestor}
            placeholder="General (todos)"
            options={[
              { value: "", label: "General (todos)" },
              ...(data.vendedores || []).map((v) => ({ value: v, label: v })),
            ]}
            onChange={setGestor}
          />
        )}
        <Select
          width="w-56"
          value={grupo}
          placeholder="Todos los grupos"
          options={[
            { value: "", label: "Todos los grupos" },
            ...(data.grupos || []).map((g) => ({ value: g, label: g })),
          ]}
          onChange={setGrupo}
        />
        <span className="text-xs text-slate-400">{data.rango}</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Hectolitros" value={formatNumber(t.hectolitros, 2)} tone="brand"
          hint={`Meta del día: ${formatNumber(data.meta_dia_hl, 2)}`} />
        <Kpi label="Vendido" value={formatMoney(t.importe)} />
        <Kpi label="Operaciones" value={formatInt(t.operaciones)} tone="slate" />
        <Kpi label="Días con venta" value={formatInt(t.dias)} tone="slate"
          hint={`de ${formatInt(data.dias_laborales_totales)} laborables`} />
      </div>

      <Panel>
        <PanelHeader
          icon={CalendarDays}
          title={gestor ? `Día a día — ${gestor}` : "Día a día — toda la sucursal"}
          sub={grupo ? `Solo ${grupo}` : "Todos los grupos"}
        />
        {dias.length === 0 ? (
          <p className="p-6 text-sm text-slate-400">No hay días con venta en este periodo.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {dias.map((d) => {
              const open = abierto === d.fecha;

              return (
                <li key={d.fecha}>
                  <button
                    type="button"
                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition"
                    onClick={() => setAbierto(open ? null : d.fecha)}
                  >
                    {/* El estado va como una franja de color y ADEMÁS como cifra: el
                        color solo no se lee en blanco y negro ni con daltonismo. */}
                    <span className={cn("w-1.5 h-9 rounded-full shrink-0",
                      d.estado === "ok" ? "bg-emerald-500" : d.estado === "alerta" ? "bg-amber-400" : "bg-red-500")} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-slate-800">
                        {d.dia_semana} {d.fecha.slice(8)}/{d.fecha.slice(5, 7)}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatInt(d.clientes)} {d.clientes === 1 ? "cliente" : "clientes"} ·{" "}
                        {formatInt(d.operaciones)} {d.operaciones === 1 ? "operación" : "operaciones"}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-semibold tabular-nums text-slate-800">
                        {formatNumber(d.hectolitros, 2)} HL
                      </p>
                      <p className={cn("text-xs tabular-nums",
                        d.delta_meta_hl >= 0 ? "text-emerald-600" : "text-red-600")}>
                        {d.delta_meta_hl >= 0 ? "+" : "−"}{formatNumber(Math.abs(d.delta_meta_hl), 2)} vs meta
                      </p>
                    </div>
                    <p className="text-sm tabular-nums text-slate-600 w-28 text-right shrink-0 hidden sm:block">
                      {formatMoney(d.importe)}
                    </p>
                    <ChevronDown size={16} className={cn("text-slate-400 shrink-0 transition-transform", open && "rotate-180")} />
                  </button>

                  {open && (
                    <div className="grid gap-4 px-4 pb-4 md:grid-cols-2">
                      <Detalle
                        icon={Users}
                        titulo="A quién le vendió"
                        filas={d.clientes_del_dia}
                        vacio="Sin clientes ese día."
                      />
                      <Detalle
                        icon={Package}
                        titulo="Qué vendió"
                        filas={d.productos_del_dia}
                        vacio="Sin productos ese día."
                        conGrupo={!grupo}
                      />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}

/** Una de las dos listas del día. La misma forma para las dos: se comparan de un vistazo. */
function Detalle({ icon: Icon, titulo, filas, vacio, conGrupo = false }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60">
      <p className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        <Icon size={13} /> {titulo}
        {filas?.length ? <span className="ml-auto font-normal normal-case text-slate-400">{filas.length}</span> : null}
      </p>
      {!filas?.length ? (
        <p className="px-3 pb-3 text-xs text-slate-400">{vacio}</p>
      ) : (
        <div className="max-h-72 overflow-auto scroll-thin">
          <table className="w-full text-sm">
            <tbody>
              {filas.map((f) => (
                <tr key={f.nombre} className="border-t border-slate-200/70">
                  <td className="px-3 py-1.5">
                    <span className="block truncate text-slate-700">{f.nombre}</span>
                    {conGrupo && f.grupo && (
                      <span className="text-[10px] uppercase tracking-wide text-slate-400">{f.grupo}</span>
                    )}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums text-slate-500 whitespace-nowrap">
                    {formatNumber(f.hectolitros, 2)} HL
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums font-medium text-slate-700 whitespace-nowrap">
                    {formatMoney(f.importe)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
