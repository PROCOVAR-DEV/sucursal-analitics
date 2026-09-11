import { UserCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { getMetasCantidad, getMetasGestor, getVendedores } from "../api.js";
import { Kpi, formatInt, formatMoney, formatNumber } from "./Kpi.jsx";
import { VendorFormatoTables } from "./MetasGestorReport.jsx";
import FiltroMulti from "./FiltroMulti.jsx";
import { Buscador, filtrarFilas } from "./ui.jsx";

/**
 * El nombre en corto para la tira: primero y último.
 *
 * «FIDEL ALBERTO PALMA HECHAVARRIA» y «RIGOBERTO MANUEL MARTINEZ SABORIT» son nombres
 * reales de La Habana, y puestos enteros hacen que ocho vendedores no quepan de ninguna
 * manera. Con el primero y el apellido se distinguen igual —que es para lo que está la
 * tira— y el entero sale al pasar por encima.
 *
 * Dos palabras o menos se dejan tal cual: ahí no hay nada que acortar.
 */
function nombreCorto(nombre) {
  const p = String(nombre || "").trim().split(/\s+/);

  return p.length <= 2 ? String(nombre || "") : `${p[0]} ${p[p.length - 1]}`;
}

export default function VendedoresView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [metas, setMetas] = useState(null);
  /** El mismo estudio, de los productos que no van en hectolitros. */
  const [metasCant, setMetasCant] = useState(null);
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
    setMetasCant(null);
    getMetasCantidad(sourceId, period, selDia)
      .then((d) => { if (!cancelled) setMetasCant(d); })
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
  const metasCantBlock = metasCant?.por_gestor?.find((g) => g.gestor === activeGestor) || null;

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
          {/* La cuota es MENSUAL. Con un rango de fechas se compara contra la parte
              proporcional, y decirlo evita la lectura de "voy al 3%" que salía antes de
              comparar un día suelto contra la meta de todo el mes. */}
          {(data.proporcion_periodo ?? 1) < 1 && (
            <p className="text-xs text-slate-400">
              Cuotas ajustadas a {data.dias_del_rango} de los {data.dias_del_mes} días
              laborales del mes.
            </p>
          )}
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

      {/* LA TIRA DE VENDEDORES: UNA SOLA FILA, SIEMPRE.
          Envolvía en pantalla ancha (`sm:flex-wrap`) y con nombres largos se rompía: en
          La Habana son ocho, con cosas como «RIGOBERTO MANUEL MARTINEZ SABORIT», y la
          tira ocupaba dos y tres renglones. Al ser PEGAJOSA se comía media pantalla y
          empujaba hacia abajo justo lo que se venía a leer — que es el problema que ya se
          había arreglado en móvil y seguía en escritorio.
          Ahora se arrastra en todas las anchuras: una fila, alta fija, pase lo que pase
          con la cantidad de vendedores o el largo de los nombres. */}
      <div className="sticky top-0 z-20 -mx-3 sm:-mx-6 px-3 sm:px-6 py-3 bg-slate-50/95 backdrop-blur border-b border-slate-200 shadow-sm flex gap-2 overflow-x-auto scroll-thin">
        {data.vendedores.map((v) => {
          const active = v.gestor === activeGestor;
          const pct = v.cumplimiento_pct;
          const tone = pct >= 100 ? "text-emerald-700" : pct >= 80 ? "text-amber-700" : "text-red-700";
          // Sin cuota puesta, el cumplimiento no existe: enseñar «0%» en rojo dice que va
          // fatal cuando lo cierto es que no se le ha puesto meta.
          const conCuota = Number(v.cuota_hl) > 0;

          return (
            <button
              key={v.gestor}
              title={v.nombre || v.gestor}
              className={`tab shrink-0 flex flex-col items-start gap-0.5 py-2 px-4 max-w-[11rem] ${active ? "tab-active" : ""}`}
              onClick={() => setSelGestor(v.gestor)}
            >
              <span className="font-semibold truncate w-full text-left">{nombreCorto(v.nombre || v.gestor)}</span>
              {!active && (
                hayHL
                  ? (conCuota
                      ? <span className={`text-[10px] font-bold ${tone}`}>{Math.round(pct)}% HL</span>
                      : <span className="text-[10px] font-bold text-slate-400">sin cuota</span>)
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
          metasCantBlock={metasCantBlock}
          productosConMeta={metasCant?.formatos || []}
          prorrateado={(data.proporcion_periodo ?? 1) < 1}
          diasRango={data.dias_del_rango}
          diasMes={data.dias_del_mes}
        />
      )}
    </div>
  );
}

function VendorDetail({ vendor, metasBlock, formatos, reportDate, diasDisponibles, diaAnterior, selDia, onSelDia, hayHL = true, grupos = [], comisionSobreTodo = false, prorrateado = false, diasRango = 0, diasMes = 0, metasCantBlock = null, productosConMeta = [] }) {
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
  const conCuota = Number(vendor.cuota_hl) > 0;

  return (
    <div className="space-y-4">
      {/* Vendor header card */}
      <div className="card">
        <div className="flex justify-between items-start flex-wrap gap-3">
          <div>
            <h3 className="text-xl font-bold">{vendor.nombre}</h3>
            <p className="text-sm text-slate-500">{vendor.sector} · {vendor.gestor}</p>
          </div>
          {hayHL && (conCuota ? (
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${badgeBg}`}>
              {Math.round(pct)}% cumplimiento HL
            </span>
          ) : (
            <span className="px-3 py-1 rounded-full text-sm font-semibold bg-slate-100 text-slate-500">
              Sin cuota puesta
            </span>
          ))}
        </div>

        {/* La cuota es de hectolitros y solo hay hectolitros en cerveza y malta. Con un
            grupo sin HL, esta barra saldría siempre en rojo al 0% — la lectura sería
            "va fatal" cuando la verdad es "esto no se mide así". */}
        {hayHL && conCuota ? (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>Hectolitros: {formatNumber(vendor.total_hectolitros, 2)}</span>
              {/* Con un rango de fechas la cuota va prorrateada, y hay que decirlo: un
                  «Cuota: 9,3 HL» sin explicar de dónde sale no se puede comprobar. */}
              <span>
                Cuota: {formatNumber(vendor.cuota_hl, 2)} HL
                {prorrateado && (
                  <span className="text-slate-400">
                    {" "}({diasRango} de {diasMes} días · mes: {formatNumber(vendor.cuota_hl_mes, 0)} HL)
                  </span>
                )}
              </span>
            </div>
            <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
              <div
                className={`h-full ${barColor} rounded-full transition-all`}
                style={{ width: `${barPct}%` }}
              />
            </div>
          </div>
        ) : hayHL ? (
          /* Cuota 0 no es «va al 0%»: es que a esa persona no se le ha puesto meta este
             mes. Una barra vacía y un 0% en rojo se leen como un desastre, y lo que hay
             que hacer no es correr más — es ir a Configuración y ponerle la cuota. */
          <p className="mt-3 text-xs text-slate-500">
            Vendió <b>{formatNumber(vendor.total_hectolitros, 2)} HL</b>, pero no tiene
            cuota puesta para este mes, así que no hay cumplimiento que medir. Se pone en
            Configuración › Calculadora de metas.
          </p>
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


      {/* EN QUÉ SE LE FUE EL MES.
          Con todos los grupos puestos, dos personas que facturan lo mismo pueden haber
          hecho trabajos distintos: una vive de la cerveza y otra reparte entre cuatro
          familias. Eso no salía por ningún lado — había una lista de productos y a sumar
          de cabeza. Va antes que el detalle a propósito: primero en qué anda, después
          producto a producto. */}
      {vendor.por_grupo?.length > 1 && (
        <div className="card">
          <h4 className="font-semibold">En qué se le fue el mes</h4>
          <p className="text-xs text-slate-500 mb-3">Cómo reparte lo que vendió entre familias.</p>
          <div className="space-y-2">
            {vendor.por_grupo.map((gr) => (
              <div key={gr.grupo} className="flex items-center gap-3">
                <span className="w-32 sm:w-44 shrink-0 truncate text-sm font-medium">{gr.grupo}</span>
                <div className="h-2 flex-1 min-w-[3rem] overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, gr.pct)}%` }} />
                </div>
                <span className="w-12 shrink-0 text-right text-xs tabular-nums text-slate-500">{formatNumber(gr.pct, 0)}%</span>
                <span className="w-24 shrink-0 text-right text-sm tabular-nums font-semibold">{formatMoney(gr.importe)}</span>
                <span className="hidden md:block w-40 shrink-0 text-right text-xs text-slate-400">
                  {formatInt(gr.productos)} productos · {formatInt(gr.clientes)} clientes
                  {gr.hectolitros > 0 && ` · ${formatNumber(gr.hectolitros, 1)} HL`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}


      {/* SUS METAS POR CANTIDAD, CONTRA LO VENDIDO.
          Los productos que no son cerveza no se miden en hectolitros: se cuentan en
          unidades. Sus metas se ponen por gestor en la calculadora, y hasta ahora se
          guardaban y no se comparaban con nada — o sea, se podían poner y no servían para
          saber cómo iba cada uno, que es justo para lo que se ponen.
          Ordenadas de peor a mejor: lo primero que hay que ver es dónde va flojo. */}
      {vendor.metas_cantidad?.length > 0 && (
        <div className="card">
          <h4 className="font-semibold">Sus metas por cantidad</h4>
          <p className="text-xs text-slate-500 mb-3">
            Los productos que no se miden en hectolitros. En unidades.
          </p>
          <div className="overflow-x-auto scroll-thin">
            <table className="min-w-full text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Producto</th>
                  <th className="px-3 py-2 text-right font-semibold">Meta</th>
                  <th className="px-3 py-2 text-right font-semibold">Vendido</th>
                  <th className="px-3 py-2 text-right font-semibold">Falta</th>
                  <th className="px-3 py-2 text-right font-semibold">% Cumpl.</th>
                </tr>
              </thead>
              <tbody>
                {vendor.metas_cantidad.map((m) => (
                  <tr key={m.producto} className="border-t border-slate-100">
                    <td className="px-3 py-1.5 font-medium">{m.producto}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {formatNumber(m.meta, 0)}
                      {m.meta !== m.meta_mes && (
                        <span className="block text-[10px] text-slate-400">mes: {formatNumber(m.meta_mes, 0)}</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{formatNumber(m.real, 0)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">
                      {m.falta > 0 ? formatNumber(m.falta, 0) : "—"}
                    </td>
                    <td className={cn("px-3 py-1.5 text-right tabular-nums font-semibold",
                      m.cumplimiento_pct >= 100 ? "text-emerald-600" : m.cumplimiento_pct >= 80 ? "text-amber-600" : "text-red-600")}>
                      {formatNumber(m.cumplimiento_pct, 1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* QUÉ VENDIÓ, CON LO QUE HACE FALTA PARA JUZGARLO.
          Eran tres columnas —producto, importe y una barra de porcentaje— y con eso se
          ve cuánto facturó y nada más: ni a cuántos clientes, ni si repitió, ni a qué
          precio, ni si en ese producto es de los que tiran o de los que van a rastras.
          Que es justo lo que hay que saber para sentarse a hablar con la persona.

          «% oficina» es la columna que convierte una cifra en un juicio: 619 de arroz no
          dice si es mucho o poco; «el 21% de todo el arroz que se vendió aquí» sí. */}
      {vendor.top_productos?.length > 0 && (
        <div className="card">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h4 className="font-semibold">Qué vendió</h4>
              <p className="text-xs text-slate-500">
                {vendor.top_productos.length} productos
                {qProd.trim() && `, ${filtrarFilas(vendor.top_productos, qProd).length} a la vista`}
              </p>
              {/* Las dos preguntas distintas que se le pueden hacer a una línea. El
                  contraste entre ellas es lo que sirve: 1% de su venta con 100% de la
                  oficina es un producto que no vende nadie más. */}
              <p className="mt-1 text-xs text-slate-400 max-w-2xl">
                <b>% de su venta</b>: de qué vive esta persona. <b>Su parte de la
                oficina</b>: cuánto puso ella de todo lo que se vendió de ese producto —
                100% quiere decir que fue la única.
              </p>
            </div>
            <Buscador onChange={setQProd} placeholder="Producto o familia…" value={qProd} />
          </div>
          <div className="max-h-[30rem] overflow-auto scroll-thin rounded-lg border border-slate-200">
            <table className="min-w-full text-sm">
              {/* Cabecera pegajosa: son todos los productos, no un top, y al bajar por
                  una lista larga se pierde de qué es cada columna. */}
              <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Producto</th>
                  <th className="px-3 py-2 text-left font-semibold">Familia</th>
                  <th className="px-3 py-2 text-right font-semibold">Importe</th>
                  {/* Se llamaban «% suyo» y «% oficina» y no se entendían: Jose las leyó
                      como «lo que vendió él» y «lo que vendió la oficina», que es otra
                      cosa. Un título de columna que hay que explicar de palabra es un
                      título malo — la explicación va debajo, en la propia cabecera. */}
                  <th className="px-3 py-2 text-right font-semibold" title="Qué parte de TODO lo que vendió esta persona es este producto. La columna suma 100%.">
                    % de su venta
                    <span className="block font-normal normal-case text-[10px] text-slate-400">cuánto pesa en lo suyo</span>
                  </th>
                  <th className="px-3 py-2 text-right font-semibold" title="De todo lo que la oficina vendió DE ESTE PRODUCTO, qué parte puso esta persona. 100% = fue la única que lo vendió.">
                    su parte de la oficina
                    <span className="block font-normal normal-case text-[10px] text-slate-400">de todo lo vendido de ese producto</span>
                  </th>
                  <th className="px-3 py-2 text-right font-semibold">Cantidad</th>
                  {hayHL && <th className="px-3 py-2 text-right font-semibold">HL</th>}
                  <th className="px-3 py-2 text-right font-semibold">Precio medio</th>
                  <th className="px-3 py-2 text-right font-semibold">Clientes</th>
                  <th className="px-3 py-2 text-right font-semibold">Oper.</th>
                </tr>
              </thead>
              <tbody>
                {filtrarFilas(vendor.top_productos, qProd).map((p) => (
                  <tr key={p.producto} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-3 py-1.5 font-medium">{p.producto}</td>
                    <td className="px-3 py-1.5 text-xs text-slate-500">{p.grupo || "—"}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{formatMoney(p.total)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{formatNumber(p.pct_del_gestor, 1)}%</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">
                      {/* Teñida: de un vistazo se ve en qué productos manda él. */}
                      <span
                        className="inline-block rounded px-1.5 py-0.5"
                        style={p.pct_de_la_oficina ? { background: `rgba(37, 99, 235, ${0.05 + 0.35 * Math.min(1, p.pct_de_la_oficina / 50)})` } : undefined}
                      >
                        {formatNumber(p.pct_de_la_oficina, 1)}%
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{formatNumber(p.cantidad, 2)}</td>
                    {hayHL && <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{formatNumber(p.hectolitros, 2)}</td>}
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{formatMoney(p.precio_medio)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{formatInt(p.clientes)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-slate-500">{formatInt(p.operaciones)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
      {/* EL MISMO ESTUDIO, PARA LO QUE NO SE MIDE EN HECTOLITROS.
          Arriba: acumulado del mes contra la meta que tocaría a estas alturas, y las
          ventas del día contra la meta diaria y contra ayer — pero de cerveza. De los
          demás productos no se podía preguntar nada de eso: sólo había un total contra un
          total. Misma tabla, mismas cuentas, otras columnas y otra unidad. */}
      {metasCantBlock && productosConMeta.length > 0 && (
        <div className="card space-y-3">
          <div>
            <h4 className="font-semibold">Lo que no va en hectolitros · {vendor.gestor}</h4>
            <p className="text-xs text-slate-500">
              Arroz, papel, baterías… en unidades. Las metas se ponen en Config › Calculadora de metas.
            </p>
          </div>
          <VendorFormatoTables
            block={metasCantBlock}
            formatos={productosConMeta}
            unidad="u"
            vacio={<><b>{vendor.nombre}</b> no tiene metas por cantidad puestas este mes.</>}
          />
        </div>
      )}

      {/* El desglose es de Malta y Parranda por formato: sin hectolitros a la vista es
          una tabla de ceros con selector de semana incluido. */}
      {hayHL && <HLBreakdown vendor={vendor} />}
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
