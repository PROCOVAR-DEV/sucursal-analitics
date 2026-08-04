import { Download, Grid3x3 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { downloadExport, getGestorSku } from "../api.js";
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
 *  - Matriz: una fila por GESTOR y una columna por PRODUCTO. Es como se lee de
 *    verdad: "¿qué vendió esta persona?" recorriendo su fila. Los productos van
 *    de cabecera porque son los que se comparan entre sí.
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
  const [bajando, setBajando] = useState(false);

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

  // Importe de cada casilla, indexado una sola vez: recorrer la matriz por cada
  // celda seria O(gestores x productos x matriz) y con 27 productos se nota.
  const celda = useMemo(() => {
    const m = new Map();

    if (data) {
      for (const fila of data.matriz) {
        for (const [g, v] of Object.entries(fila.por_gestor)) {
          m.set(g + "\u0000" + fila.producto, v);
        }
      }
    }

    return m;
  }, [data]);

  // En la matriz el filtro busca por GESTOR (son las filas) o por producto, y en
  // ese caso deja solo las columnas que coinciden.
  const columnas = useMemo(() => {
    if (!data) return [];
    const q = filtro.trim().toLowerCase();
    const porProducto = data.productos.filter((p) => p.toLowerCase().includes(q));

    return !q || !porProducto.length ? data.productos : porProducto;
  }, [data, filtro]);

  const filasMatriz = useMemo(() => {
    if (!data) return [];
    const q = filtro.trim().toLowerCase();
    const coincideGestor = data.gestores.filter((g) => g.nombre.toLowerCase().includes(q));

    return !q || !coincideGestor.length ? data.gestores : coincideGestor;
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
          <button
            className="btn"
            disabled={bajando}
            onClick={async () => {
              setBajando(true);
              try {
                await downloadExport(sourceId, "gestor-sku", period);
              } finally {
                setBajando(false);
              }
            }}
          >
            <Download size={16} /> {bajando ? "Generando…" : "Excel"}
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
          <PanelHeader title="Importe por gestor y producto" />
          {/* overflow-x propio: con muchos productos la tabla es ancha y no debe
              estirar el layout de la página. La primera columna y la cabecera
              quedan fijas para no perder de vista de quién es cada fila, y la
              columna Total se ancla a la derecha: con muchos productos hay que
              desplazarse igual, y si el total se va con ellos la tabla obliga a
              ir y volver para leer una sola fila. */}
          <div className="w-full min-w-0 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b border-slate-200">
                  <th className="py-2 pr-4 sticky left-0 bg-white z-20 shadow-[2px_0_4px_-2px_rgba(0,0,0,.15)]">
                    Gestor
                  </th>
                  {columnas.map((p) => (
                    <th key={p} className="py-2 px-3 text-right whitespace-nowrap">
                      {p}
                    </th>
                  ))}
                  <th className="py-2 pl-3 text-right font-semibold sticky right-0 bg-white z-20 shadow-[-2px_0_4px_-2px_rgba(0,0,0,.15)]">Total</th>
                </tr>
              </thead>
              <tbody>
                {filasMatriz.map((g) => {
                  const tot = data.totales_gestor.find((t) => t.gestor === g.clave);

                  return (
                    <tr key={g.clave} className="border-b border-slate-100">
                      <td className="py-1.5 pr-4 sticky left-0 bg-white z-20 shadow-[2px_0_4px_-2px_rgba(0,0,0,.15)]">
                        {g.nombre}
                      </td>
                      {columnas.map((p) => {
                        const v = celda.get(g.clave + "\u0000" + p) || 0;

                        return (
                          <td
                            key={p}
                            className={cn(
                              "py-1.5 px-3 text-right tabular-nums",
                              !v && "text-slate-300",
                            )}
                          >
                            {formatNumber(v)}
                          </td>
                        );
                      })}
                      <td className="py-1.5 pl-3 text-right font-semibold tabular-nums sticky right-0 bg-white z-20 shadow-[-2px_0_4px_-2px_rgba(0,0,0,.15)]">
                        {formatNumber(tot?.importe || 0)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-300 font-semibold">
                  <td className="py-2 pr-4 sticky left-0 bg-white z-20 shadow-[2px_0_4px_-2px_rgba(0,0,0,.15)]">Total</td>
                  {columnas.map((p) => {
                    const t = data.totales_producto.find((x) => x.producto === p);

                    return (
                      <td key={p} className="py-2 px-3 text-right tabular-nums">
                        {formatNumber(t?.importe || 0)}
                      </td>
                    );
                  })}
                  <td className="py-2 pl-3 text-right tabular-nums sticky right-0 bg-white z-20 shadow-[-2px_0_4px_-2px_rgba(0,0,0,.15)]">
                    {formatNumber(data.total_importe)}
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
          <div className="w-full min-w-0 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b border-slate-200">
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
                    className="border-b border-slate-100"
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
                <tr className="border-t-2 border-slate-300 font-semibold">
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
        <div className="w-full min-w-0 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b border-slate-200">
                <th className="py-2 pr-4">Gestor</th>
                <th className="py-2 px-3 text-right">Importe</th>
                <th className="py-2 px-3 text-right">% del total</th>
                <th className="py-2 px-3 text-right">Hectolitros</th>
                <th className="py-2 pl-3 text-right">Productos distintos</th>
              </tr>
            </thead>
            <tbody>
              {data.totales_gestor.map((t) => (
                <tr key={t.gestor} className="border-b border-slate-100">
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
              <tr className="border-t-2 border-slate-300 font-semibold">
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
