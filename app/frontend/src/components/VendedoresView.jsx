import { UserCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { getMetasGestor, getVendedores } from "../api.js";
import { Kpi, formatInt, formatMoney, formatNumber } from "./Kpi.jsx";
import { VendorFormatoTables } from "./MetasGestorReport.jsx";
import FiltroMulti from "./FiltroMulti.jsx";
import { Buscador, filtrarFilas } from "./ui.jsx";

export default function VendedoresView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [metas, setMetas] = useState(null);
  const [err, setErr] = useState(null);
  const [selGestor, setSelGestor] = useState(null);
  // Día de corte elegido (null = el último con datos). Permite mirar días anteriores.
  const [selDia, setSelDia] = useState(null);
  // Grupos comerciales elegidos. Vacío = todos, que es como estaba.
  //
  // Esta pantalla se movía solo con Parranda y Malta —la cuota, la barra y las dos
  // tablas de formato son de hectolitros— y el estudio de un gestor tenía que poder ser
  // de cualquier familia: arroz, papel, baterías. Con «todos» sale todo, como siempre.
  const [grupos, setGrupos] = useState([]);

  useEffect(() => {
    // Descarta respuestas viejas (ver DashboardView): si no, la del acumulado pisa la del mes.
    let cancelled = false;
    setData(null); setErr(null); setSelGestor(null); setSelDia(null);
    getVendedores(sourceId, period, grupos)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });
    return () => { cancelled = true; };
    // `grupos` se serializa: como array suelto sería uno nuevo en cada render y el
    // efecto se dispararía sin parar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId, period, grupos.join("|")]);

  // Las tablas de cumplimiento se recargan solas al cambiar el día de corte.
  useEffect(() => {
    let cancelled = false;
    setMetas(null);
    getMetasGestor(sourceId, period, selDia)
      .then((d) => { if (!cancelled) setMetas(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [sourceId, period, selDia]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6">Cargando…</div>;

  // ¿Lo que se está mirando tiene hectolitros? Solo Parranda y Malta se miden así, y
  // enseñar una cuota de HL, una barra al 0% y dos tablas de formato vacías para el
  // arroz no es enseñar poco: es enseñar que va mal algo que ni existe.
  const hayHL = grupos.length === 0 || grupos.some((g) => String(g).toUpperCase() === "PARRANDA");
  const disponibles = data.grupos_disponibles || [];

  const totalCantidad = data.vendedores.reduce((a, v) => a + (v.total_cantidad || 0), 0);

  const activeGestor = selGestor ?? data.vendedores[0]?.gestor ?? null;
  const vendor = data.vendedores.find((v) => v.gestor === activeGestor);
  const metasBlock = metas?.por_gestor?.find((g) => g.gestor === activeGestor) || null;

  return (
    <div className="space-y-6">
      {/* Cabecera: qué se está mirando, y el mando para cambiarlo al lado del título.
          Estaba abajo del todo en la otra pestaña y aquí no había ninguno: el filtro es
          lo primero que se toca, así que va donde se mira primero. */}
      <div className="flex justify-between items-start flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <UserCheck className="text-brand-600" /> Por Vendedor
          </h2>
          <p className="text-sm text-slate-500">
            {data.rango} · {grupos.length ? grupos.join(", ") : "todos los grupos"}
          </p>
        </div>
        {disponibles.length > 1 && (
          <FiltroMulti
            etiqueta="Grupo"
            opciones={disponibles}
            valor={grupos}
            onChange={setGrupos}
            textoTodos="Todos los grupos"
          />
        )}
      </div>

      {/* Totales de la oficina. La casilla del medio cambia con lo que se mira: los
          hectolitros solo existen en cerveza y malta, y para el arroz o el papel la
          medida es la cantidad. Enseñar "0 HL" ahí no es enseñar poco, es enseñar que
          va mal algo que ni siquiera existe. */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <Kpi label="Total Oficina (importe)" value={formatMoney(data.total_importe)} />
        {hayHL ? (
          <Kpi label="Total Hectolitros" value={formatNumber(data.total_hectolitros, 2)} tone="brand" />
        ) : (
          <Kpi label="Cantidad total" value={formatNumber(totalCantidad, 2)} tone="brand"
            hint="Unidades vendidas: este grupo no se mide en hectolitros" />
        )}
        <Kpi label="Total Operaciones" value={formatInt(data.total_operaciones)} tone="slate" />
      </div>

      {/* Vendor tab selector — fijo (sticky) al hacer scroll para cambiar de vendedor
          sin perderlo de vista mientras miras las tablas de abajo. */}
      {/* La tira de vendedores: se arrastra en móvil. Con nueve nombres envueltos,
          la cabecera pegajosa ocupaba media pantalla y tapaba justo lo que se venía a
          leer. */}
      <div className="sticky top-0 z-20 -mx-3 sm:-mx-6 px-3 sm:px-6 py-3 bg-slate-50/95 backdrop-blur border-b border-slate-200 shadow-sm flex gap-2 overflow-x-auto scroll-thin sm:flex-wrap sm:overflow-visible">
        {data.vendedores.map((v) => {
          const active = v.gestor === activeGestor;
          const pct = v.cumplimiento_pct;
          const tone = pct >= 100 ? "text-emerald-700" : pct >= 80 ? "text-amber-700" : "text-red-700";
          return (
            <button
              key={v.gestor}
              className={`tab shrink-0 flex flex-col items-start gap-0.5 py-2 px-4 ${active ? "tab-active" : ""}`}
              onClick={() => setSelGestor(v.gestor)}
            >
              <span className="font-semibold">{v.nombre || v.gestor}</span>
              {!active && (
                hayHL
                  ? <span className={`text-[10px] font-bold ${tone}`}>{Math.round(pct)}% HL</span>
                  // Sin hectolitros el porcentaje de cuota no significa nada, y todos
                  // saldrían en rojo al 0%. Lo que sí se puede comparar es lo vendido.
                  : <span className="text-[10px] font-bold text-slate-500">{formatMoney(v.total_importe)}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Vendor detail */}
      {vendor && (
        <VendorDetail
          vendor={vendor}
          metasBlock={metasBlock}
          formatos={metas?.formatos}
          reportDate={metas?.report_date}
          diasDisponibles={metas?.dias_disponibles || []}
          diaAnterior={metas?.dia_anterior}
          selDia={selDia}
          onSelDia={setSelDia}
          hayHL={hayHL}
          grupos={grupos}
          comisionSobreTodo={!!data.comision_sobre_todo}
        />
      )}
    </div>
  );
}

function VendorDetail({ vendor, metasBlock, formatos, reportDate, diasDisponibles, diaAnterior, selDia, onSelDia, hayHL = true, grupos = [], comisionSobreTodo = false }) {
  /**
   * Filtrar la lista de productos del gestor.
   *
   * Son todos los que vendió —no un top—, así que en un teléfono la única forma de
   * encontrar uno era deslizando la lista entera.
   */
  const [qProd, setQProd] = useState("");
  const pct = vendor.cumplimiento_pct;
  const barPct = Math.min(pct, 100);
  const barColor = pct >= 100 ? "bg-emerald-500" : pct >= 80 ? "bg-amber-500" : "bg-red-500";
  const badgeBg  = pct >= 100 ? "bg-emerald-100 text-emerald-800" : pct >= 80 ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800";

  return (
    <div className="space-y-4">
      {/* Vendor header card */}
      <div className="card">
        <div className="flex justify-between items-start flex-wrap gap-3">
          <div>
            <h3 className="text-xl font-bold">{vendor.nombre}</h3>
            <p className="text-sm text-slate-500">{vendor.sector} · {vendor.gestor}</p>
          </div>
          {hayHL && (
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${badgeBg}`}>
              {Math.round(pct)}% cumplimiento HL
            </span>
          )}
        </div>

        {/* La cuota es de hectolitros y solo hay hectolitros en cerveza y malta. Con un
            grupo sin HL, esta barra saldría siempre en rojo al 0% — la lectura sería
            "va fatal" cuando la verdad es "esto no se mide así". */}
        {hayHL ? (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>Hectolitros: {formatNumber(vendor.total_hectolitros, 2)}</span>
              <span>Cuota: {formatNumber(vendor.cuota_hl, 2)} HL</span>
            </div>
            <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
              <div
                className={`h-full ${barColor} rounded-full transition-all`}
                style={{ width: `${barPct}%` }}
              />
            </div>
          </div>
        ) : (
          <p className="mt-3 text-xs text-slate-500">
            Viendo <b>{grupos.join(", ")}</b>. No se mide en hectolitros, así que aquí no
            hay cuota ni cumplimiento: lo que cuenta es la cantidad y el importe.
          </p>
        )}
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Total Ventas" value={formatMoney(vendor.total_importe)} />
        {hayHL
          ? <Kpi label="Hectolitros" value={formatNumber(vendor.total_hectolitros, 2)} tone="brand" />
          : <Kpi label="Cantidad" value={formatNumber(vendor.total_cantidad, 2)} tone="brand" hint="Unidades vendidas" />}
        <Kpi label="Operaciones" value={formatInt(vendor.num_operaciones)} tone="slate" />
        <Kpi label="Clientes Únicos" value={formatInt(vendor.num_clientes)} tone="slate" />
      </div>

      {/* Estudio diario/mensual por formato (individual) — como el reporte */}
      {hayHL && metasBlock && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h4 className="font-semibold">Cumplimiento por formato · {vendor.gestor}</h4>
            {/* Día de corte: el acumulado se recalcula HASTA ese día y el diario lo compara
                contra el día anterior con datos. Sirve para mirar atrás y ver cómo iban. */}
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-500">Día:</label>
              <select
                className="input text-xs py-1 px-2 w-auto"
                value={selDia ?? ""}
                onChange={(e) => onSelDia(e.target.value || null)}
              >
                <option value="">Último ({reportDate || "—"})</option>
                {[...(diasDisponibles || [])].reverse().map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              {diaAnterior && (
                <span className="text-xs text-slate-400">vs {diaAnterior}</span>
              )}
            </div>
          </div>
          <VendorFormatoTables block={metasBlock} formatos={formatos} />
        </div>
      )}

      {/* LA COMISIÓN, COMO UNA CUENTA — no como cinco recuadros sueltos.
          Eran cinco casillas en fila y una comisión no son cinco cifras independientes:
          es una resta. En recuadros no se ve que el neto salga de las de al lado, así
          que quien cobraba menos de lo que esperaba no tenía forma de comprobar de
          dónde salió la diferencia — que es justo lo que hace pensar que le quitaron
          dinero sin avisar.
          Escrita como un recibo, la cuenta se sigue con el dedo y cuadra a la vista. */}
      <div className="card">
        <h3 className="font-semibold text-slate-800 mb-1">
          {vendor.es_supervisor ? "Lo que cobra el supervisor" : "Lo que cobra el gestor"}
        </h3>
        <p className="text-xs text-slate-500 mb-3">
          De la comisión bruta al neto, línea a línea.
        </p>
        {/* Una comisión NO se paga por familia: se paga sobre todo lo que la persona
            vendió. Calcularla sobre el grupo elegido daría una cifra más baja que parece
            lo que cobra y no lo es — y de eso no se vuelve: quien la vea una vez ya no se
            fía de ninguna. Así que se calcula sobre el total SIEMPRE, y se dice. */}
        {comisionSobreTodo && (
          <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Esta cuenta es sobre <b>todo</b> lo que vendió, no solo sobre el grupo que
            estás mirando. La comisión no se paga por familia, así que no cuadra a
            propósito con las ventas de arriba.
          </p>
        )}
        <table className="w-full text-sm">
          <tbody>
            <tr className="border-b border-slate-100">
              <td className="py-2 text-slate-600">Comisión sobre lo vendido</td>
              <td className="py-2 text-right tabular-nums font-medium">{formatMoney(vendor.comision)}</td>
            </tr>
            <tr className="border-b border-slate-100">
              <td className="py-2 text-slate-600">
                Descuento por ventas sin pedido
                {/* Cuántas fueron, aquí y no en su propio recuadro: el número solo no
                    dice nada, lo que importa es cuánto costaron. */}
                <span className="ml-1 text-xs text-slate-400">
                  ({formatInt(vendor.sin_pedido || 0)} {vendor.sin_pedido === 1 ? "venta" : "ventas"})
                </span>
              </td>
              <td className={`py-2 text-right tabular-nums ${vendor.descuento > 0 ? "text-red-600" : "text-slate-400"}`}>
                {vendor.descuento ? `− ${formatMoney(vendor.descuento)}` : formatMoney(0)}
              </td>
            </tr>
            {/* Al supervisor no se le descuenta: se le SUMA lo del equipo. Enseñarle un
                «descuento supervisor» a quien ES el supervisor era cobrarle su propia
                comisión. */}
            {vendor.es_supervisor ? (
              <tr className="border-b border-slate-100">
                <td className="py-2 text-slate-600">
                  Comisión del equipo
                  <span className="ml-1 text-xs text-slate-400">(10 % de cada gestor)</span>
                </td>
                <td className="py-2 text-right tabular-nums text-emerald-600">
                  + {formatMoney(vendor.comision_de_los_gestores || 0)}
                </td>
              </tr>
            ) : (
              <tr className="border-b border-slate-100">
                <td className="py-2 text-slate-600">
                  Parte del supervisor
                  <span className="ml-1 text-xs text-slate-400">(10 % de la tuya)</span>
                </td>
                <td className={`py-2 text-right tabular-nums ${vendor.comision_supervisor > 0 ? "text-amber-600" : "text-slate-400"}`}>
                  {vendor.comision_supervisor ? `− ${formatMoney(vendor.comision_supervisor)}` : formatMoney(0)}
                </td>
              </tr>
            )}
            <tr>
              <td className="pt-3 font-semibold text-slate-800">
                {vendor.es_supervisor ? "Total a cobrar" : "Comisión neta"}
              </td>
              <td className="pt-3 text-right tabular-nums text-lg font-bold text-brand-700">
                {formatMoney(vendor.es_supervisor ? vendor.comision_total_supervisor : vendor.comision_neta)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* El desglose es de Malta y Parranda por formato: sin hectolitros a la vista es
          una tabla de ceros con selector de semana incluido. */}
      {hayHL && <HLBreakdown vendor={vendor} />}

      {/* TODOS los productos (ya no es un top): scroll interno + cabecera fija, para
          que la tarjeta no crezca sin límite pero se pueda ver todo lo vendido. */}
      {vendor.top_productos?.length > 0 && (
        <div className="card">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-semibold">
              Productos (por importe){" "}
              <span className="font-normal text-sm text-slate-400">
                — {vendor.top_productos.length} en total
                {qProd.trim() && `, ${filtrarFilas(vendor.top_productos, qProd).length} a la vista`}
              </span>
            </h4>
            <Buscador onChange={setQProd} placeholder="Producto…" value={qProd} />
          </div>
          {/* max-h ≈ cabecera + 10 filas: el scroll se activa a partir de 10 productos */}
          <div className="overflow-auto scroll-thin max-h-[26rem] rounded-lg border border-slate-200">
            <table className="min-w-full text-sm">
              <thead className="sticky top-0 z-10">
                <tr>
                  <th className="px-3 py-2 text-left bg-slate-100">#</th>
                  <th className="px-3 py-2 text-left bg-slate-100">Producto</th>
                  <th className="px-3 py-2 text-right bg-slate-100">Empaques</th>
                  <th className="px-3 py-2 text-right bg-slate-100">Importe</th>
                  <th className="px-3 py-2 text-right bg-slate-100">% del total</th>
                </tr>
              </thead>
              <tbody>
                {filtrarFilas(vendor.top_productos, qProd).map((p, i) => {
                  const pctProd = vendor.total_importe > 0
                    ? Math.round((p.total / vendor.total_importe) * 100)
                    : "0.0";
                  return (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-3 py-2 text-slate-400">{i + 1}</td>
                      <td className="px-3 py-2 font-medium">{p.producto}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(p.cantidad ?? 0, 0)}</td>
                      <td className="px-3 py-2 text-right">{formatMoney(p.total)}</td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-2 bg-slate-200 rounded-full w-16 overflow-hidden">
                            <div
                              className="h-full bg-brand-500 rounded-full"
                              style={{ width: `${pctProd}%` }}
                            />
                          </div>
                          <span className="text-slate-600 w-10 text-right">{pctProd}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// Desglose de HL (Malta/Parranda × 330/500/1500) con selector de SEMANA. "Todo el mes"
// usa los totales del vendedor; una semana usa el desglose semanal (sku_semanal).
function HLBreakdown({ vendor }) {
  const [semana, setSemana] = useState("");
  const weeks = vendor.weeks_disponibles || [];
  const single = semana && weeks.includes(semana);
  const sku = vendor.sku_semanal || [];
  const sizeLabel = { "330": "330 ml", "500": "500 ml", "1500": "1.5 L" };
  const hlOf = (prod, size) => {
    if (!single) return vendor[`${prod.toLowerCase()}_${size}`] || 0;
    const row = sku.find((r) => r.formato === `${prod} ${sizeLabel[size]}`);
    return row ? (row.semanal[semana] || 0) : 0;
  };
  const rowTot = (prod) => hlOf(prod, "330") + hlOf(prod, "500") + hlOf(prod, "1500");
  const colTot = (size) => hlOf("Malta", size) + hlOf("Parranda", size);
  const grand = rowTot("Malta") + rowTot("Parranda");

  return (
    <div className="card">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <h4 className="font-semibold">
          Desglose Hectolitros (Malta / Parranda){single ? ` · ${semana}` : ""}
        </h4>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Semana:</label>
          <select
            className="input text-xs py-1 px-2 w-auto"
            value={semana}
            onChange={(e) => setSemana(e.target.value)}
          >
            <option value="">Todo el mes</option>
            {weeks.map((w) => (
              <option key={w} value={w}>{w}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-100">
            <tr>
              <th className="px-3 py-2 text-left">Producto</th>
              <th className="px-3 py-2 text-right">330 ml</th>
              <th className="px-3 py-2 text-right">500 ml</th>
              <th className="px-3 py-2 text-right">1500 ml</th>
              <th className="px-3 py-2 text-right font-bold">Total HL</th>
            </tr>
          </thead>
          <tbody>
            {["Malta", "Parranda"].map((prod) => (
              <tr key={prod} className="border-t border-slate-100">
                <td className="px-3 py-2 font-medium">{prod}</td>
                <td className="px-3 py-2 text-right">{formatNumber(hlOf(prod, "330"))}</td>
                <td className="px-3 py-2 text-right">{formatNumber(hlOf(prod, "500"))}</td>
                <td className="px-3 py-2 text-right">{formatNumber(hlOf(prod, "1500"))}</td>
                <td className="px-3 py-2 text-right font-semibold">{formatNumber(rowTot(prod))}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-slate-300 bg-slate-50">
              <td className="px-3 py-2 font-bold">Total</td>
              <td className="px-3 py-2 text-right font-bold">{formatNumber(colTot("330"))}</td>
              <td className="px-3 py-2 text-right font-bold">{formatNumber(colTot("500"))}</td>
              <td className="px-3 py-2 text-right font-bold">{formatNumber(colTot("1500"))}</td>
              <td className="px-3 py-2 text-right font-bold text-brand-700">{formatNumber(grand)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
