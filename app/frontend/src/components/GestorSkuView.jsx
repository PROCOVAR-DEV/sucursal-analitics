import { Download, Grid3x3 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { downloadExport, getGestorSku } from "../api.js";
import { formatMoney, formatNumber } from "./Kpi.jsx";
import { Panel, PanelHeader, StatTile, cn } from "./ui.jsx";
import FiltroMulti from "./FiltroMulti.jsx";

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
/**
 * Etiquetas cortas para las cabeceras, calculadas MIRANDO TODA LA TABLA.
 *
 * # Por qué no vale acortar cada nombre por su cuenta
 *
 * «CERVEZA PARRANDA 1500 ML BLISTER 6U» de cabecera ocupa media pantalla, y con veinte
 * productos la tabla se va tan a la derecha que no se lee una fila entera. Pero la primera
 * versión de esto acortaba cada nombre aislado, y al probarla contra los productos de
 * verdad **cuatro de cada cuarenta quedaban con la misma etiqueta**:
 *
 *     DETERGENTE KAPITAL 1000ML   <- INDUSTRIAL, LAVADO 10U y LAVADO 12U
 *     ENERGIZANTE GO+ 24U         <- AZUL, DAY ROJO y NIGHT NEGRO
 *
 * Dos columnas con el mismo rótulo son peores que un rótulo largo: se lee mal y encima no
 * se sabe cuál es cuál.
 *
 * Lo que distingue a un producto no está en el nombre suelto: está en **con cuáles
 * compite**. «LAVADO» sobra si no hay ningún «INDUSTRIAL» al lado, y hace falta si lo hay.
 * Así que se corta contra el conjunto: se prueba con dos palabras, y sólo si choca con otro
 * se le añade una más, hasta que sea única.
 *
 * El nombre entero sigue estando en el `title`.
 */
const RELLENO = new Set(["DE", "DEL", "LA", "EL", "CON", "PARA", "PACA", "BLISTER", "CAJA", "PACK", "UND", "SACO"]);
// Dos clases de unidad, y no valen lo mismo.
// MEDIDA es lo que contiene el envase —500 G, 1500 ML, 13 PIES— y es lo que distingue un
// formato de otro. CUENTA es cuántos vienen en la caja —24 U— y es de logística.
const MEDIDA = /^(ML|L|KG|G|M|CM|WH|PIES)$/;
const CUENTA = /^(U|UND|P|PUERTA)$/;
// Anclada, y escrita entera. Construirla juntando las otras dos con `.source` dejaba una
// expresión SIN anclas, y entonces «AZUCAR» contaba como unidad por llevar una U dentro y
// «ENERGY» por la G: el cuerpo del nombre se vaciaba y la etiqueta quedaba en «10KG».
const UNIDADES = /^(ML|L|KG|G|M|CM|WH|PIES|U|UND|P|PUERTA)$/;

/**
 * El tamaño que va en la etiqueta.
 *
 * Se prefiere la MEDIDA sobre la cuenta. «DETERGENTE BOW 500 G PACA 40U» es el de medio
 * kilo; que vengan cuarenta por paca no lo distingue de nada, porque la paca cambia sin que
 * cambie el producto. Cogiendo el último número con unidad salía «BOW 40U», que dice lo de
 * menos.
 *
 * Se busca de derecha a izquierda porque cuando hay varios números el del final suele ser
 * el del envase: «AZUCAR ENERGY ICUMSA 45 10 KG» son diez kilos, no cuarenta y cinco.
 */
function tamanoDe(palabras) {
  const buscar = (unidad) => {
    for (let i = palabras.length - 1; i >= 0; i--) {
      const w = palabras[i];
      const pegado = /^(\d+([.,]\d+)?)([A-Z]+)$/.exec(w);

      if (pegado && unidad.test(pegado[3])) return pegado[0];
      if (/^\d+([.,]\d+)?$/.test(w) && unidad.test(palabras[i + 1] || "")) {
        return w + palabras[i + 1];
      }
    }

    return "";
  };

  return buscar(MEDIDA) || buscar(CUENTA);
}

export function etiquetasCortas(nombres) {
  const desglose = new Map();

  for (const n of nombres) {
    const limpio = String(n || "").trim().toUpperCase();
    const palabras = limpio.split(/\s+/);
    const tam = tamanoDe(palabras);
    // Fuera el relleno, los números sueltos y los trozos del tamaño: lo que queda son las
    // palabras que de verdad nombran el producto.
    // La PRIMERA palabra no se tira nunca, aunque esté en la lista de relleno: es la que
    // dice de qué es el producto. En «CAJA PARA BUFFET», CAJA es el producto —son cajas de
    // cartón— y quitarla dejaba «PARA BUFFET», que no se entiende. En «ACEITE SOYA CAJA
    // 20U», la de en medio sí sobra.
    const cuerpo = palabras.filter(
      (w, j) => (j === 0 || !RELLENO.has(w)) && !/^\d/.test(w) && !UNIDADES.test(w),
    );

    desglose.set(n, { cuerpo, tam, limpio });
  }

  const salida = new Map();

  for (const n of nombres) {
    const { cuerpo, tam, limpio } = desglose.get(n);
    let etiqueta = limpio;

    for (let k = 2; k <= Math.max(2, cuerpo.length); k++) {
      const cand = [...cuerpo.slice(0, k), tam].filter(Boolean).join(" ");
      // ¿La comparte con algún otro producto de esta misma tabla?
      const choca = nombres.some((m) => {
        if (m === n) return false;

        const o = desglose.get(m);

        return [...o.cuerpo.slice(0, k), o.tam].filter(Boolean).join(" ") === cand;
      });

      if (!choca) {
        etiqueta = cand;
        break;
      }
    }

    salida.set(n, etiqueta || limpio);
  }

  return salida;
}

export default function GestorSkuView({ sourceId, period }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [vista, setVista] = useState("matriz");
  const [filtro, setFiltro] = useState("");
  const [soloGestor, setSoloGestor] = useState("");
  const [bajando, setBajando] = useState(false);
  // Grupos comerciales elegidos. Vacio = todos, que es como estaba.
  const [grupos, setGrupos] = useState([]);
  // "importe" (dolares) o "cantidad" (por empaque, tal como viene del origen).
  const [metrica, setMetrica] = useState("importe");
  // Se conserva entre consultas: el servidor la calcula ANTES de filtrar, pero
  // vaciarla al recargar haria parpadear el desplegable.
  const [gruposDisponibles, setGruposDisponibles] = useState([]);

  useEffect(() => {
    // Descarta respuestas viejas (ver DashboardView): si no, la del acumulado
    // pisa la del mes cuando la primera tarda más.
    let cancelled = false;

    setData(null);
    setErr(null);
    getGestorSku(sourceId, period, grupos, metrica)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        if (d.grupos_disponibles?.length) setGruposDisponibles(d.grupos_disponibles);
      })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });

    return () => { cancelled = true; };
    // `grupos` se serializa: como array suelto es uno nuevo en cada render y
    // relanzaria la peticion sin parar.
  }, [sourceId, period, grupos.join("|"), metrica]);

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

  /**
   * La celda más grande de toda la tabla, que es contra lo que se tiñe el fondo.
   *
   * Del máximo GLOBAL y no del de cada fila: aquí se compara a unos con otros, y tiñendo
   * por fila el mayor de cada gestor saldría igual de oscuro que el mayor del que vende el
   * triple. Parecería que todos venden lo mismo, que es lo contrario de lo que se viene a
   * ver.
   */
  const maxCelda = useMemo(() => {
    let max = 0;

    for (const v of celda.values()) if (v > max) max = v;

    return max || 1;   // nunca cero: se divide por él
  }, [celda]);

  // En la matriz el filtro busca por GESTOR (son las filas) o por producto, y en
  // ese caso deja solo las columnas que coinciden.
  const columnas = useMemo(() => {
    if (!data) return [];
    const q = filtro.trim().toLowerCase();
    const porProducto = data.productos.filter((p) => p.toLowerCase().includes(q));

    return !q || !porProducto.length ? data.productos : porProducto;
  }, [data, filtro]);

  // Las etiquetas se calculan contra LAS COLUMNAS QUE SE VEN, y por eso va aquí y no
  // arriba: al filtrar por grupo quedan menos productos, y con menos competencia hacen
  // falta menos palabras para distinguirlos.
  const etiquetas = useMemo(() => etiquetasCortas(columnas), [columnas]);

  const filasMatriz = useMemo(() => {
    if (!data) return [];
    const q = filtro.trim().toLowerCase();
    const coincideGestor = data.gestores.filter((g) => g.nombre.toLowerCase().includes(q));

    return !q || !coincideGestor.length ? data.gestores : coincideGestor;
  }, [data, filtro]);

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;

  // En cantidad NO se pone simbolo de moneda: un "$" delante de un numero de
  // empaques es falso, y quien lo lea saca la cuenta equivocada.
  const esCantidad = data.metrica === "cantidad";
  const fmt = (v) => (esCantidad ? formatNumber(Math.round(v || 0)) : formatMoney(v));
  // El total de lo que se esta midiendo. `total_importe` sigue siendo dolares
  // siempre, a proposito: no cambia de significado a mitad.
  const totalMedida = data.total_medida ?? data.total_importe;
  if (!data.filas.length) {
    return <div className="p-6 text-slate-400">No hay ventas en este periodo.</div>;
  }

  const gestores = data.gestores;
  // El % que representa cada gestor sobre el total, para leer el peso sin dividir.
  const pesoDe = (v) => (totalMedida ? (v / totalMedida) * 100 : 0);
  // El peso del primero: es contra lo que se dibujan las barras. Contra 100 saldrían todas
  // cortitas —el primero suele andar por el 20 %— y no se distinguiría ninguna.
  const mayorPeso = Math.max(
    ...(data?.totales_gestor || []).map((x) => pesoDe(x.medida ?? x.importe)),
    1,
  );

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
                await downloadExport(sourceId, "gestor-sku", period, { grupos, metrica });
              } finally {
                setBajando(false);
              }
            }}
          >
            <Download size={16} />{" "}
            {bajando
              ? "Generando…"
              : grupos.length || esCantidad
                ? "Excel de lo que veo"
                : "Excel"}
          </button>
        </div>
      </div>

      {/* Qué se mide y de qué grupos. La métrica va como par de botones porque
          son dos y no van a crecer; el grupo va en desplegable porque la lista
          crece con el negocio y en fila acabaría partiéndose. */}
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
          <FiltroMulti
            etiqueta="Grupo"
            opciones={gruposDisponibles}
            valor={grupos}
            onChange={setGrupos}
            textoTodos="Todos los grupos"
          />
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label={esCantidad ? "Cantidad total" : "Importe total"} value={fmt(totalMedida)} />
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
                  <th className="py-2 pr-4 whitespace-nowrap sticky left-0 bg-white z-20 shadow-[2px_0_4px_-2px_rgba(0,0,0,.15)]">
                    Gestor
                  </th>
                  {columnas.map((p) => (
                    // Corto y con el entero al pasar por encima. `max-w` para que un
                    // nombre que no se deja acortar no vuelva a estirar la columna.
                    <th
                      key={p}
                      className="py-2 px-3 text-right align-bottom text-xs font-semibold leading-tight max-w-[7.5rem]"
                      title={p}
                    >
                      {etiquetas.get(p) || p}
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
                      {/* `whitespace-nowrap`: sin esto «Jean Ramos» se parte en dos
                          renglones y cada fila mide el doble, con lo que la tabla se va de
                          alto y cuesta seguirla de izquierda a derecha. */}
                      <td className="py-1.5 pr-4 whitespace-nowrap sticky left-0 bg-white z-20 shadow-[2px_0_4px_-2px_rgba(0,0,0,.15)]">
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
                            /* EL COLOR DICE DÓNDE ESTÁ EL VOLUMEN.
                               Una matriz de veinte por diez son doscientos números iguales:
                               para encontrar el grande hay que leerlos uno a uno. Con el
                               fondo teñido según cuánto pesa la celda, el mapa se ve de un
                               vistazo y los números quedan para cuando hace falta el dato
                               exacto.
                               Se tiñe contra el MÁXIMO de toda la tabla, no de la fila: así
                               dos filas se pueden comparar entre sí, que es lo que se hace
                               aquí. Tiñendo por fila, el mayor de cada uno saldría igual de
                               oscuro y parecería que todos venden lo mismo. */
                            style={v ? { background: `rgba(37, 99, 235, ${0.05 + 0.35 * Math.min(1, v / maxCelda)})` } : undefined}
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
                    {formatNumber(totalMedida)}
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
                    <td className="py-1.5 px-3 text-right tabular-nums">{fmt(esCantidad ? f.cantidad : f.importe)}</td>
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
                    {fmt(filas.reduce((s, f) => s + (esCantidad ? f.cantidad : f.importe), 0))}
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
              <tr className="text-left border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-2 w-8">#</th>
                <th className="py-2 pr-4">Gestor</th>
                <th className="py-2 px-3 text-right">{esCantidad ? "Cantidad" : "Importe"}</th>
                <th className="py-2 px-3 text-right">% del total</th>
                <th className="py-2 px-3 w-32">&nbsp;</th>
                <th className="py-2 px-3 text-right">Hectolitros</th>
                <th className="py-2 pl-3 text-right">Productos</th>
              </tr>
            </thead>
            <tbody>
              {data.totales_gestor.map((t, i) => {
                const peso = pesoDe(t.medida ?? t.importe);

                return (
                  <tr key={t.gestor} className="border-b border-slate-100">
                    {/* El puesto delante: la tabla ya viene ordenada por importe y sin el
                        número hay que contar filas con el dedo para decir «va tercero». */}
                    <td className="py-1.5 pr-2 tabular-nums text-slate-300 w-8">{i + 1}</td>
                    <td className="py-1.5 pr-4 whitespace-nowrap">{t.gestor_nombre}</td>
                    <td className="py-1.5 px-3 text-right tabular-nums font-medium">{fmt(t.medida ?? t.importe)}</td>
                    <td className="py-1.5 px-3 text-right tabular-nums text-slate-500">{peso.toFixed(1)}%</td>
                    {/* La barra del porcentaje. Diez números en columna hay que compararlos
                        de uno en uno; en barra se ve de golpe quién carga con el negocio.
                        Va contra el mayor y no contra 100: si el primero tiene el 22 %,
                        todas las barras saldrían cortitas y no se distinguiría ninguna. */}
                    <td className="py-1.5 px-3 w-32">
                      <div className="h-2 w-full rounded-full bg-slate-100">
                        <div
                          className="h-2 rounded-full bg-brand-500"
                          style={{ width: `${Math.max(2, (peso / (mayorPeso || 1)) * 100)}%` }}
                        />
                      </div>
                    </td>
                    <td className="py-1.5 px-3 text-right tabular-nums">
                      {formatNumber(t.hectolitros)}
                    </td>
                    <td className="py-1.5 pl-3 text-right tabular-nums text-slate-500">{t.productos_distintos}</td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-slate-300 font-semibold">
                <td className="py-2 pr-4">Total</td>
                <td className="py-2 px-3 text-right tabular-nums">
                  {fmt(totalMedida)}
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
