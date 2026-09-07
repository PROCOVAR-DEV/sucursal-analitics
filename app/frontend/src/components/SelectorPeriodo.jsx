import { Calendar as CalIcon, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "./ui.jsx";

/**
 * El periodo que se está mirando: un mes entero, o un rango de días.
 *
 * # Por qué hacía falta
 *
 * Sólo se podía elegir MES. «Del 1 al 15», «el lunes pasado» o «esta semana» no se podían
 * contestar, y la salida era subir un Excel recortado a esas fechas — o sea, fabricar un
 * dato a mano para poder mirarlo. El backend ya aceptaba `desde`/`hasta` desde hace tiempo;
 * lo que no había era por dónde pedirlo.
 *
 * # Un solo calendario, y un día suelto también
 *
 * Dos campos de fecha sueltos obligan a abrir dos veces el mismo calendario y a acordarse
 * de cuál era cuál. Aquí se pulsa el primer día y luego el segundo, y ya está. **Pulsar dos
 * veces el mismo día es ese día solo**, que es lo que se quiere cuando se mira «lo de
 * ayer»: si hubiera que poner el mismo día en las dos casillas, nadie lo haría.
 *
 * # Cómo viaja
 *
 * El valor sigue siendo UNA cadena, como antes, para no tener que tocar las quince vistas
 * que se lo pasan a la API:
 *
 *     null                      todo el acumulado
 *     "2026-09"                 un mes entero, como siempre
 *     "2026-09-01..2026-09-15"  un rango de días
 *
 * `api.js` es quien la parte y decide si manda `mes=` o `desde=`/`hasta=`.
 */

const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];
const DIAS = ["L", "M", "X", "J", "V", "S", "D"];

/** `AAAA-MM-DD` de una fecha, sin pasar por UTC: `toISOString` cambia el día por la zona. */
const aTexto = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const deTexto = (s) => {
  const [y, m, d] = String(s).split("-").map(Number);

  return new Date(y, m - 1, d);
};

export const esRango = (v) => typeof v === "string" && v.includes("..");

/** Lo que se enseña en el botón y en la etiqueta de al lado. */
export function rotuloPeriodo(v) {
  if (!v) return "Todo (acumulado)";

  if (esRango(v)) {
    const [d, h] = v.split("..");
    const a = deTexto(d);
    const b = deTexto(h);

    if (d === h) return `${a.getDate()} de ${MESES[a.getMonth()]} ${a.getFullYear()}`;
    // Mismo mes: no repetirlo dos veces. «1–15 de septiembre» se lee de un vistazo.
    if (a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()) {
      return `${a.getDate()}–${b.getDate()} de ${MESES[a.getMonth()]} ${a.getFullYear()}`;
    }

    return `${a.getDate()} ${MESES[a.getMonth()].slice(0, 3)} – ${b.getDate()} ${MESES[b.getMonth()].slice(0, 3)} ${b.getFullYear()}`;
  }

  const [y, m] = v.split("-");

  return `${MESES[Number(m) - 1]} ${y}`;
}

/** Los días que se pintan en la rejilla, empezando en lunes y con los huecos del principio. */
function celdasDelMes(ancla) {
  const primero = new Date(ancla.getFullYear(), ancla.getMonth(), 1);
  // getDay() da 0 para domingo; aquí la semana empieza en lunes.
  const hueco = (primero.getDay() + 6) % 7;
  const ultimo = new Date(ancla.getFullYear(), ancla.getMonth() + 1, 0).getDate();
  const celdas = Array.from({ length: hueco }, () => null);

  for (let d = 1; d <= ultimo; d++) celdas.push(new Date(ancla.getFullYear(), ancla.getMonth(), d));

  return celdas;
}

export function SelectorPeriodo({ value, meses = [], onChange, className }) {
  const [abierto, setAbierto] = useState(false);
  // El mes que se está enseñando en el calendario. Arranca en el del periodo elegido, para
  // no obligar a navegar hasta donde ya estabas.
  const [ancla, setAncla] = useState(() => {
    if (esRango(value)) return deTexto(value.split("..")[0]);
    if (value) return deTexto(`${value}-01`);

    return new Date();
  });
  /** El primer día pulsado, mientras se espera el segundo. */
  const [inicio, setInicio] = useState(null);
  /** Sobre qué día está el ratón, para pintar el rango antes de cerrarlo. */
  const [encima, setEncima] = useState(null);
  const caja = useRef(null);

  // Pulsar fuera cierra. Sin esto hay que volver a pulsar el botón, y con el calendario
  // tapando media pantalla eso se siente como que se ha quedado enganchado.
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e) => {
      if (caja.current && !caja.current.contains(e.target)) {
        setAbierto(false);
        setInicio(null);
      }
    };

    document.addEventListener("mousedown", fuera);

    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  const [desdeSel, hastaSel] = esRango(value) ? value.split("..") : [null, null];

  const elegir = (d) => {
    const txt = aTexto(d);

    if (!inicio) {
      setInicio(txt);

      return;
    }

    // El orden da igual: quien pulsa primero el 15 y luego el 1 quiere del 1 al 15.
    const [a, b] = inicio <= txt ? [inicio, txt] : [txt, inicio];

    onChange(`${a}..${b}`);
    setInicio(null);
    setAbierto(false);
  };

  const enRango = (d) => {
    const txt = aTexto(d);

    if (inicio) {
      // Mientras se elige: se pinta contra el día que tiene el ratón encima.
      const otro = encima || inicio;
      const [a, b] = inicio <= otro ? [inicio, otro] : [otro, inicio];

      return txt >= a && txt <= b;
    }

    return desdeSel && txt >= desdeSel && txt <= hastaSel;
  };

  const esExtremo = (d) => {
    const txt = aTexto(d);

    return txt === inicio || txt === desdeSel || txt === hastaSel;
  };

  const hoy = aTexto(new Date());
  const celdas = celdasDelMes(ancla);

  return (
    <div ref={caja} className={cn("relative", className)}>
      <button
        className="w-full inline-flex items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm hover:border-slate-400"
        type="button"
        onClick={() => setAbierto((v) => !v)}
      >
        <span className="flex items-center gap-2 truncate">
          <CalIcon className="text-slate-400 shrink-0" size={15} />
          <span className="truncate">{rotuloPeriodo(value)}</span>
        </span>
        {value && (
          // Quitar el periodo sin abrir nada. Es un `span` y no un `button`: dentro de otro
          // botón, un botón anidado no es HTML válido y el navegador lo saca de su sitio.
          <span
            aria-label="Quitar el periodo"
            className="shrink-0 rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            role="button"
            tabIndex={-1}
            onClick={(e) => {
              e.stopPropagation();
              onChange(null);
            }}
          >
            <X size={13} />
          </span>
        )}
      </button>

      {abierto && (
        <div className="absolute left-0 z-30 mt-1 w-[19rem] rounded-xl border border-slate-200 bg-white p-3 shadow-lg">
          {/* Los meses, en un desplegable.
              Estuvieron como pastillas, una por mes, y con nueve meses de datos ocupaban
              cuatro filas: el calendario quedaba empujado hasta abajo y había que buscarlo.
              Y el año que viene serían el doble.

              Desplegable NATIVO y no el `Select` de la casa: el nuestro dibuja su menú en
              otro sitio del documento, y desde dentro de este panel un clic ahí contaría
              como «has pulsado fuera» y cerraría el panel entero antes de elegir nada. */}
          <div className="mb-3">
            <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Mes completo
            </label>
            <select
              className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 focus:border-brand-500 focus:outline-none"
              value={esRango(value) ? "" : value || "todo"}
              onChange={(e) => {
                const v = e.target.value;

                if (!v) return;   // el hueco de «rango elegido»: no es una opción
                onChange(v === "todo" ? null : v);
                setAbierto(false);
              }}
            >
              <option value="todo">Todo (acumulado)</option>
              {/* Del más reciente al más viejo: septiembre se busca mucho más que enero. */}
              {[...meses].sort().reverse().map((m) => (
                <option key={m} value={m}>
                  {rotuloPeriodo(m)}
                </option>
              ))}
              {/* Con un rango puesto, ningún mes está elegido. Sin esta opción vacía el
                  desplegable enseñaría «Todo» y diría una cosa distinta de la de arriba. */}
              {esRango(value) && <option value="">— rango de días —</option>}
            </select>
          </div>

          <div className="mb-1.5 flex items-center justify-between">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              {inicio ? "Ahora el último día" : "O un rango de días"}
            </div>
            <div className="flex items-center gap-1">
              <button
                aria-label="Mes anterior"
                className="rounded p-1 text-slate-500 hover:bg-slate-100"
                type="button"
                onClick={() => setAncla(new Date(ancla.getFullYear(), ancla.getMonth() - 1, 1))}
              >
                <ChevronLeft size={15} />
              </button>
              <span className="w-32 text-center text-xs font-medium text-slate-600">
                {MESES[ancla.getMonth()]} {ancla.getFullYear()}
              </span>
              <button
                aria-label="Mes siguiente"
                className="rounded p-1 text-slate-500 hover:bg-slate-100"
                type="button"
                onClick={() => setAncla(new Date(ancla.getFullYear(), ancla.getMonth() + 1, 1))}
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-7 gap-0.5 text-center">
            {DIAS.map((d, i) => (
              <div key={i} className="py-1 text-[10px] font-semibold text-slate-400">
                {d}
              </div>
            ))}
            {celdas.map((d, i) =>
              d === null ? (
                <div key={`h${i}`} />
              ) : (
                <button
                  key={aTexto(d)}
                  className={cn(
                    "rounded-md py-1 text-xs tabular-nums",
                    esExtremo(d)
                      ? "bg-brand-600 font-semibold text-white"
                      : enRango(d)
                        ? "bg-brand-100 text-brand-800"
                        : "text-slate-600 hover:bg-slate-100",
                    aTexto(d) === hoy && !esExtremo(d) && "ring-1 ring-brand-400",
                  )}
                  type="button"
                  onClick={() => elegir(d)}
                  onMouseEnter={() => setEncima(aTexto(d))}
                >
                  {d.getDate()}
                </button>
              ),
            )}
          </div>

          <p className="mt-2 text-[11px] leading-snug text-slate-400">
            {inicio
              ? "Pulsa el mismo día otra vez para mirar sólo ese día."
              : "Pulsa el primer día y luego el último."}
          </p>
        </div>
      )}
    </div>
  );
}
