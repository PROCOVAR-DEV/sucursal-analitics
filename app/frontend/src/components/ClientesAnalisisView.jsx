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
  // Grupos comerciales elegidos. Vacio = todos, que es como estaba.
  const [grupos, setGrupos] = useState([]);
  // "importe" (dolares) o "cantidad" (por empaque, tal como viene del origen).
  const [metrica, setMetrica] = useState("importe");
  // La lista de grupos se conserva entre consultas: el servidor la calcula ANTES
  // de filtrar, pero si se vaciara al recargar, el desplegable parpadearia.
  const [gruposDisponibles, setGruposDisponibles] = useState([]);

  useEffect(() => {
    // Descarta respuestas viejas (ver DashboardView): si no, la del acumulado pisa la del mes.
    let cancelled = false;
    setData(null); setErr(null);
    getClientesAnalisis(sourceId, period, grupos, metrica)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        if (d.grupos_disponibles?.length) setGruposDisponibles(d.grupos_disponibles);
      })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });
    return () => { cancelled = true; };
    // `grupos` se serializa: es un array nuevo en cada render y como dependencia
    // suelta relanzaria la peticion sin parar.
  }, [sourceId, period, grupos.join("|"), metrica]);

  // Al cambiar de periodo o de fuente se vuelve a la vista general: el gestor
  // elegido puede no existir en el periodo nuevo.
  useEffect(() => { setSel("__oficina__"); }, [sourceId, period]);

  const block = useMemo(() => {
    if (!data) return null;
    if (sel === "__oficina__") return data.oficina;
    return data.por_gestor.find((g) => g.gestor === sel) || data.oficina;
  }, [data, sel]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;

  const skus = block.skus || [];
  const clientes = block.clientes || [];
  // En cantidad NO se pone el simbolo de moneda: un "$" delante de un numero de
  // empaques es sencillamente falso, y quien lo lea sacara la cuenta equivocada.
  const esCantidad = data.metrica === "cantidad";
  const fmt = (v) => (esCantidad ? formatInt(Math.round(v || 0)) : formatMoney(v));
  const isOficina = sel === "__oficina__";

  async function handleExport() {
    setBusy(true);
    try { await downloadExport(sourceId, "clientes-analisis", period, { grupos, metrica }); }
    catch (e) { alert(e?.response?.data?.detail || "No se pudo descargar"); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex justify-between items-start gap-4 flex-wrap">
        <div>
          <h2 className="section-title">Análisis de Clientes por Vendedor</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Clientes rankeados por {esCantidad ? "cantidad (por empaque)" : "ventas ($)"}. Cada columna es un producto comprado. · {data.rango}
          </p>
        </div>
        {/* El boton dice QUE se lleva. Antes ponia "Exportar Excel" y sacaba
            siempre el informe completo en importe: con filtros puestos, el
            archivo no era lo que se estaba viendo y no habia forma de saberlo
            hasta abrirlo. */}
        <Button variant="outline" icon={Download} onClick={handleExport} disabled={busy}>
          {busy
            ? "Generando…"
            : grupos.length || esCantidad
              ? "Exportar lo que veo"
              : "Exportar Excel"}
        </Button>
      </div>

      {/* Qué se mide y de qué grupos. Va ANTES del selector de vendedor porque
          aplica a los dos lados —general y por vendedor—: cambiarlo aquí y que
          el número de abajo cambie de significado sin avisar sería peor. */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500">Medir en</span>
          {[
            { id: "importe", label: "Importe" },
            { id: "cantidad", label: "Cantidad" },
          ].map((m) => (
            <button
              key={m.id}
              onClick={() => setMetrica(m.id)}
              className={cn("tab shrink-0", metrica === m.id && "tab-active")}
            >
              {m.label}
            </button>
          ))}
        </div>

        {gruposDisponibles.length > 1 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-slate-500">Grupo</span>
            {/* "Todos" no es un grupo mas: es no filtrar. Por eso vacia la
                seleccion en vez de marcarlos todos — asi un grupo que se
                configure mañana entra solo, sin que nadie tenga que volver a
                marcarlo aqui. */}
            <button
              onClick={() => setGrupos([])}
              className={cn("tab shrink-0", grupos.length === 0 && "tab-active")}
            >
              Todos
            </button>
            {gruposDisponibles.map((g) => {
              const on = grupos.includes(g);

              return (
                <button
                  key={g}
                  onClick={() =>
                    setGrupos(on ? grupos.filter((x) => x !== g) : [...grupos, g])
                  }
                  className={cn("tab shrink-0", on && "tab-active")}
                >
                  {g}
                </button>
              );
            })}
          </div>
        )}
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
        <StatTile label={esCantidad ? "Total cantidad" : "Total ventas"} value={fmt(block.total)} accent="green" />
        <StatTile label={esCantidad ? "Media por cliente" : "Ticket promedio"} value={fmt(block.num_clientes ? block.total / block.num_clientes : 0)} accent="amber" />
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
                    <td className="px-3 py-2 text-right font-semibold text-slate-900 bg-slate-50/60 border-b border-slate-100 tabular-nums">{fmt(c.total)}</td>
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
                  <td className="bg-slate-900 text-white font-bold px-3 py-2.5 text-right tabular-nums">{fmt(block.total)}</td>
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
