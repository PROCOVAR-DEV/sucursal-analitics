import { Grid3x3 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getGestorSku } from "../api.js";
import { formatMoney, formatNumber } from "./Kpi.jsx";
import { Panel, PanelHeader, StatTile, cn } from "./ui.jsx";

/**
 * Informe cruzado GESTOR x PRODUCTO por importe.
 *
 * El informe de Vendedores enseña cada gestor con sus productos, uno debajo de
 * otro: para saber quién vende más de un producto concreto hay que ir abriendo
 * gestor por gestor y sumar a mano. Aquí se ve cruzado de un vistazo.
 *
 * Dos formas de la misma verdad, porque cada una responde a una pregunta:
 *  - Matriz: "¿quién vende este producto?" — productos en filas, gestores en
 *    columnas. Se lee en horizontal.
 *  - Tabla:  "¿qué vendió este gestor?" — una fila por par, ordenable y
 *    filtrable. Se lee en vertical.
 *
 * Los totales van en las DOS direcciones (por gestor y por producto) porque sin
 * ellos la tabla obliga a sacar la calculadora, que es justo lo que se quería
 * evitar.
 */
export default function GestorSkuView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [vista, setVista] = useState("matriz");
  const [filtro, setFiltro] = useState("");
  const [soloGestor, setSoloGestor] = useState("");

  useEffect(() => {
    // Descarta respuestas viejas (ver DashboardView): si no, la del acumulado
    // pisa la del mes cuando la primera tarda más.
    let cancelled = false;

    setData(null);
    setErr(null);
    getGestorSku(sourceId, period)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });

    return () => { cancelled = true; };
  }, [sourceId, period]);

  const filas = useMemo(() => {
    if (!data) return [];
    const q = filtro.trim().toLowerCase();

    return data.filas.filter(
      (f) =>
        (!soloGestor || f.gestor === soloGestor) &&
        (!q || f.producto.toLowerCase().includes(q) || f.gestor_nombre.toLowerCase().includes(q)),
    );
  }, [data, filtro, soloGestor]);

  const matriz = useMemo(() => {
    if (!data) return [];
    const q = filtro.trim().toLowerCase();

    return data.matriz.filter((m) => !q || m.producto.toLowerCase().includes(q));
  }, [data, filtro]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;
  if (!data.filas.length) {
    return <div className="p-6 text-slate-400">No hay ventas en este periodo.</div>;
  }

  const gestores = data.gestores;
  // El % que representa cada gestor sobre el total, para leer el peso sin dividir.
  const pesoDe = (v) => (data.total_importe ? (v / data.total_importe) * 100 : 0);

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Grid3x3 size={20} /> Gestor × Producto
          </h2>
          <p className="text-sm text-slate-500">{data.rango}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input
            className="input"
            placeholder="Filtrar producto o gestor…"
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
          />
          <button
            className={cn("tab", vista === "matriz" && "tab-active")}
            onClick={() => setVista("matriz")}
          >
            Matriz
          </button>
          <button
            className={cn("tab", vista === "tabla" && "tab-active")}
            onClick={() => setVista("tabla")}
          >
            Tabla
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Importe total" value={formatMoney(data.total_importe)} />
        <StatTile label="Gestores" value={gestores.length} />
        <StatTile label="Productos" value={data.productos.length} />
        <StatTile label="Hectolitros" value={formatNumber(data.total_hectolitros)} />
      </div>

      {vista === "matriz" ? (
        <Panel>
          <PanelHeader title="Importe por producto y gestor" />
          {/* overflow-x propio: con muchos gestores la tabla es ancha y no debe
              estirar el layout de la página. */}
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b border-slate-200 dark:border-slate-700">
                  <th className="py-2 pr-4 sticky left-0 bg-inherit">Producto</th>
                  {gestores.map((g) => (
                    <th key={g.clave} className="py-2 px-3 text-right whitespace-nowrap">
                      {g.nombre}
                    </th>
                  ))}
                  <th className="py-2 pl-3 text-right font-semibold">Total</th>
                </tr>
              </thead>
              <tbody>
                {matriz.map((m) => (
                  <tr key={m.producto} className="border-b border-slate-100 dark:border-slate-800">
                    <td className="py-1.5 pr-4 sticky left-0 bg-inherit">{m.producto}</td>
                    {gestores.map((g) => {
                      const v = m.por_gestor[g.clave] || 0;

                      return (
                        <td
                          key={g.clave}
                          className={cn(
                            "py-1.5 px-3 text-right tabular-nums",
                            !v && "text-slate-300 dark:text-slate-600",
                          )}
                        >
                          {v ? formatMoney(v) : "—"}
                        </td>
                      );
                    })}
                    <td className="py-1.5 pl-3 text-right font-semibold tabular-nums">
                      {formatMoney(m.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-300 dark:border-slate-600 font-semibold">
                  <td className="py-2 pr-4 sticky left-0 bg-inherit">Total</td>
                  {gestores.map((g) => {
                    const t = data.totales_gestor.find((x) => x.gestor === g.clave);

                    return (
                      <td key={g.clave} className="py-2 px-3 text-right tabular-nums">
                        {formatMoney(t?.importe || 0)}
                      </td>
                    );
                  })}
                  <td className="py-2 pl-3 text-right tabular-nums">
                    {formatMoney(data.total_importe)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Panel>
      ) : (
        <Panel>
          <PanelHeader
            title="Detalle por gestor y producto"
            right={
              <select
                className="input"
                value={soloGestor}
                onChange={(e) => setSoloGestor(e.target.value)}
              >
                <option value="">Todos los gestores</option>
                {gestores.map((g) => (
                  <option key={g.clave} value={g.clave}>
                    {g.nombre}
                  </option>
                ))}
              </select>
            }
          />
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b border-slate-200 dark:border-slate-700">
                  <th className="py-2 pr-4">Gestor</th>
                  <th className="py-2 pr-4">Producto</th>
                  <th className="py-2 px-3 text-right">Importe</th>
                  <th className="py-2 px-3 text-right">Cantidad</th>
                  <th className="py-2 px-3 text-right">HL</th>
                  <th className="py-2 pl-3 text-right">Operaciones</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f, i) => (
                  <tr
                    key={`${f.gestor}-${f.producto}-${i}`}
                    className="border-b border-slate-100 dark:border-slate-800"
                  >
                    <td className="py-1.5 pr-4">{f.gestor_nombre}</td>
                    <td className="py-1.5 pr-4">{f.producto}</td>
                    <td className="py-1.5 px-3 text-right tabular-nums">{formatMoney(f.importe)}</td>
                    <td className="py-1.5 px-3 text-right tabular-nums">{formatNumber(f.cantidad)}</td>
                    <td className="py-1.5 px-3 text-right tabular-nums">{formatNumber(f.hectolitros)}</td>
                    <td className="py-1.5 pl-3 text-right tabular-nums">{f.operaciones}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-300 dark:border-slate-600 font-semibold">
                  <td className="py-2 pr-4" colSpan={2}>
                    Total {soloGestor || filtro ? "(filtrado)" : ""}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums">
                    {formatMoney(filas.reduce((s, f) => s + f.importe, 0))}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums">
                    {formatNumber(filas.reduce((s, f) => s + f.cantidad, 0))}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums">
                    {formatNumber(filas.reduce((s, f) => s + f.hectolitros, 0))}
                  </td>
                  <td className="py-2 pl-3 text-right tabular-nums">
                    {filas.reduce((s, f) => s + f.operaciones, 0)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Panel>
      )}

      <Panel>
        <PanelHeader title="Totales por gestor" />
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b border-slate-200 dark:border-slate-700">
                <th className="py-2 pr-4">Gestor</th>
                <th className="py-2 px-3 text-right">Importe</th>
                <th className="py-2 px-3 text-right">% del total</th>
                <th className="py-2 px-3 text-right">Hectolitros</th>
                <th className="py-2 pl-3 text-right">Productos distintos</th>
              </tr>
            </thead>
            <tbody>
              {data.totales_gestor.map((t) => (
                <tr key={t.gestor} className="border-b border-slate-100 dark:border-slate-800">
                  <td className="py-1.5 pr-4">{t.gestor_nombre}</td>
                  <td className="py-1.5 px-3 text-right tabular-nums">{formatMoney(t.importe)}</td>
                  <td className="py-1.5 px-3 text-right tabular-nums">
                    {pesoDe(t.importe).toFixed(1)}%
                  </td>
                  <td className="py-1.5 px-3 text-right tabular-nums">
                    {formatNumber(t.hectolitros)}
                  </td>
                  <td className="py-1.5 pl-3 text-right tabular-nums">{t.productos_distintos}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-slate-300 dark:border-slate-600 font-semibold">
                <td className="py-2 pr-4">Total</td>
                <td className="py-2 px-3 text-right tabular-nums">
                  {formatMoney(data.total_importe)}
                </td>
                <td className="py-2 px-3 text-right tabular-nums">100,0%</td>
                <td className="py-2 px-3 text-right tabular-nums">
                  {formatNumber(data.total_hectolitros)}
                </td>
                <td className="py-2 pl-3 text-right tabular-nums">{data.productos.length}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Panel>
    </div>
  );
}
