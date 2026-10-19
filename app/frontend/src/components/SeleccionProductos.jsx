import { ListChecks } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import FiltroMulti from "./FiltroMulti.jsx";
import { formatNumber } from "./Kpi.jsx";
import { Badge, Panel, PanelHeader, TablaScroll, cn } from "./ui.jsx";

const CLAVE = "analitics.productos.seleccion";

function leer() {
  try {
    const v = JSON.parse(localStorage.getItem(CLAVE) || "[]");

    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

/**
 * «Productos a mi manera»: se eligen UNO o VARIOS productos, de cualquier grupo, y se ven juntos.
 *
 * Lixander (supervisor de Parranda, 19/10/2026): la pantalla enseñaba los productos por grupo, y
 * por producto sólo dejaba acotar a UN grupo. Lo que pedía es armarse su propia vista: «seleccionar
 * uno o varios productos de todos los grupos».
 *
 * Los datos ya vienen en la respuesta de Productos: `resumen_por_grupo` trae TODOS los productos
 * vendidos de cada grupo (con importe y cantidad) y `cumplimiento` la meta de los que la tienen.
 * No hace falta pedir nada más al servidor.
 *
 * La selección se recuerda en este navegador: es una vista que uno se arma una vez y quiere
 * encontrar igual al día siguiente. Lo que ya no se vende en el periodo se ignora, no se borra.
 */
export default function SeleccionProductos({ data }) {
  const [sel, setSel] = useState(leer);

  useEffect(() => {
    try { localStorage.setItem(CLAVE, JSON.stringify(sel)); } catch { /* sin almacenamiento: no pasa nada */ }
  }, [sel]);

  const { todos, metas } = useMemo(() => {
    const lista = [];
    const vistos = new Set();

    for (const g of data.groups_order || []) {
      for (const x of data.resumen_por_grupo?.[g] || []) {
        if (vistos.has(x.producto)) continue; // el mismo nombre en dos grupos: sale una vez
        vistos.add(x.producto);
        lista.push({ producto: x.producto, grupo: g, total: Number(x.total) || 0, cantidad: Number(x.cantidad) || 0 });
      }
    }

    return { todos: lista, metas: new Map((data.cumplimiento || []).map((c) => [c.producto, c])) };
  }, [data]);

  const opciones = useMemo(() => todos.map((p) => ({ id: p.producto, label: `${p.producto} · ${p.grupo}` })), [todos]);
  const elegidos = useMemo(() => {
    const s = new Set(sel);

    return todos.filter((p) => s.has(p.producto)).sort((a, b) => b.total - a.total);
  }, [todos, sel]);

  const suma = (f) => elegidos.reduce((a, p) => a + f(p), 0);
  const totalImporte = suma((p) => p.total);
  const conMeta = elegidos.filter((p) => metas.has(p.producto));
  const meta = conMeta.reduce((a, p) => a + (Number(metas.get(p.producto).meta) || 0), 0);
  const real = conMeta.reduce((a, p) => a + (Number(metas.get(p.producto).real) || 0), 0);

  return (
    <Panel>
      <PanelHeader
        icon={ListChecks}
        title="Productos a mi manera"
        sub="Elige uno o varios productos, de cualquier grupo, y mira sus ventas juntos"
        right={
          <div className="flex items-center gap-2 flex-wrap justify-end">
            <FiltroMulti
              etiqueta="Productos"
              opciones={opciones}
              valor={sel}
              onChange={setSel}
              textoTodos="Ninguno elegido"
            />
            {sel.length > 0 && (
              <button className="text-xs text-slate-500 underline" onClick={() => setSel([])} type="button">
                Quitar todos
              </button>
            )}
          </div>
        }
      />
      {elegidos.length === 0 ? (
        <div className="py-10 text-center text-sm text-slate-400">
          Todavía no has elegido ningún producto.
          <span className="block mt-1 text-xs">Usa «Productos» arriba a la derecha: puedes marcar los que quieras, de cualquier grupo.</span>
        </div>
      ) : (
        <TablaScroll>
          <table className="tbl">
            <thead>
              <tr>
                <th className="col-fija">Producto</th><th>Grupo</th>
                <th className="!text-right">Ventas ($)</th><th className="!text-right">% de la selección</th>
                <th className="!text-right">Cantidad</th>
                <th className="!text-right">Meta</th><th className="!text-right">Real</th><th className="!text-right">% Cumpl.</th>
              </tr>
            </thead>
            <tbody>
              {elegidos.map((p) => {
                const m = metas.get(p.producto);

                return (
                  <tr key={p.producto} className="hover:bg-slate-50">
                    <td className="col-fija font-medium">{p.producto}</td>
                    <td><Badge tone="slate">{p.grupo}</Badge></td>
                    <td className="text-right tabular-nums">{formatNumber(p.total, 2)}</td>
                    <td className="text-right tabular-nums text-slate-500">{totalImporte ? formatNumber((100 * p.total) / totalImporte, 1) : "—"}%</td>
                    <td className="text-right tabular-nums">{formatNumber(p.cantidad, 0)}</td>
                    <td className="text-right tabular-nums">{m ? formatNumber(m.meta, 0) : <span className="text-slate-300">—</span>}</td>
                    <td className="text-right tabular-nums">{m ? formatNumber(m.real, 2) : <span className="text-slate-300">—</span>}</td>
                    <td className="text-right tabular-nums">{m ? `${formatNumber(m.cumplimiento_pct, 1)}%` : <span className="text-slate-300">—</span>}</td>
                  </tr>
                );
              })}
              <tr className="font-semibold bg-slate-50">
                <td className="col-fija">Selección ({elegidos.length} producto{elegidos.length === 1 ? "" : "s"})</td>
                <td />
                <td className="text-right tabular-nums">{formatNumber(totalImporte, 2)}</td>
                <td className="text-right tabular-nums">100%</td>
                <td className="text-right tabular-nums">{formatNumber(suma((p) => p.cantidad), 0)}</td>
                <td className="text-right tabular-nums">{conMeta.length ? formatNumber(meta, 0) : "—"}</td>
                <td className="text-right tabular-nums">{conMeta.length ? formatNumber(real, 2) : "—"}</td>
                <td className={cn("text-right tabular-nums", meta && real >= meta ? "text-emerald-600" : "")}>
                  {meta ? `${formatNumber((100 * real) / meta, 1)}%` : "—"}
                </td>
              </tr>
            </tbody>
          </table>
        </TablaScroll>
      )}
      {elegidos.length > 0 && conMeta.length < elegidos.length && (
        <p className="px-4 pb-3 text-xs text-slate-400">
          Los productos sin meta no suman en Meta, Real ni % Cumpl.: solo tienen ventas y cantidad.
        </p>
      )}
    </Panel>
  );
}
