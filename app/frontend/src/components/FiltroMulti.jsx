import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "./ui.jsx";

/**
 * Elegir varias opciones de una lista que puede crecer.
 *
 * Los filtros estaban como pestañas: una por opción, en fila. Con tres opciones
 * se lee bien; con quince —los grupos comerciales, los gestores— la fila se
 * parte, empuja la tabla hacia abajo y hay que buscar con la vista. Y cada grupo
 * nuevo que se configure lo empeora un poco más.
 *
 * Una pestaña es para cambiar de sitio; un filtro es para acotar lo que ya se
 * está viendo. Además, una lista que crece con el negocio no cabe en una fila
 * fija, así que la regla aquí es: **lo que puede crecer va en desplegable**.
 *
 * El panel se dibuja con un portal, fuera del contenedor. Dentro no vale ni
 * siendo `absolute`: las tablas tienen su propio desplazamiento y el panel las
 * estira desde dentro — sale barra lateral y las filas de abajo se mueven. Un
 * desplegable no puede mover la página que hay debajo.
 *
 * `valor` vacío significa TODAS: "Todos" no es una opción más, es no filtrar.
 * Eso es lo que hace que una opción nueva entre sola sin que nadie tenga que
 * volver aquí a marcarla.
 */
export default function FiltroMulti({
  etiqueta,
  opciones,
  valor = [],
  onChange,
  textoTodos = "Todos",
}) {
  const [abierto, setAbierto] = useState(false);
  const [caja, setCaja] = useState(null);
  const boton = useRef(null);
  const panel = useRef(null);

  const colocar = useCallback(() => {
    const r = boton.current?.getBoundingClientRect();

    if (!r) return;

    const ALTO = 280;
    // Si no cabe debajo se abre hacia arriba: en la parte baja de la pantalla la
    // lista se salía por el borde y había que desplazarse para verla.
    const arriba = r.bottom + ALTO > window.innerHeight && r.top > ALTO;

    setCaja({
      left: r.left,
      top: arriba ? undefined : r.bottom + 4,
      bottom: arriba ? window.innerHeight - r.top + 4 : undefined,
      minWidth: Math.max(r.width, 200),
    });
  }, []);

  useEffect(() => {
    if (!abierto) return;

    colocar();

    const fuera = (e) => {
      // El panel vive FUERA de este componente, así que hay que mirar los dos:
      // mirando solo el botón, marcar una opción contaría como clic de fuera y
      // se cerraría en cuanto se tocara la primera.
      if (boton.current?.contains(e.target)) return;
      if (panel.current?.contains(e.target)) return;
      setAbierto(false);
    };
    const esc = (e) => e.key === "Escape" && setAbierto(false);

    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", esc);
    window.addEventListener("scroll", colocar, true);
    window.addEventListener("resize", colocar);

    return () => {
      document.removeEventListener("mousedown", fuera);
      document.removeEventListener("keydown", esc);
      window.removeEventListener("scroll", colocar, true);
      window.removeEventListener("resize", colocar);
    };
  }, [abierto, colocar]);

  function alternar(id) {
    onChange(valor.includes(id) ? valor.filter((x) => x !== id) : [...valor, id]);
  }

  const resumen =
    valor.length === 0
      ? textoTodos
      : valor.length === 1
        ? valor[0]
        : `${valor[0]} +${valor.length - 1}`;

  return (
    <div className="flex items-center gap-1.5">
      {etiqueta && <span className="text-xs text-slate-500">{etiqueta}</span>}
      <button
        ref={boton}
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className={cn(
          "flex items-center gap-1.5 min-w-[150px] max-w-[260px] px-2.5 py-1.5 rounded-lg border text-xs text-left transition-colors",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400",
          valor.length
            ? "border-slate-900 bg-slate-900 text-white font-semibold"
            : "border-slate-200 bg-white text-slate-600 hover:border-slate-300",
        )}
      >
        <span className="flex-1 truncate">{resumen}</span>
        <span className="text-[9px] opacity-60">{abierto ? "▲" : "▼"}</span>
      </button>

      {abierto &&
        caja &&
        createPortal(
          <div
            ref={panel}
            style={{
              position: "fixed",
              left: caja.left,
              top: caja.top,
              bottom: caja.bottom,
              minWidth: caja.minWidth,
            }}
            className="z-50 max-h-72 overflow-auto rounded-lg border border-slate-200 bg-white shadow-xl py-1"
          >
            <button
              type="button"
              onClick={() => onChange([])}
              className="w-full text-left px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 border-b border-slate-100"
            >
              {textoTodos}
            </button>
            {opciones.map((o) => {
              const id = typeof o === "string" ? o : o.id;
              const label = typeof o === "string" ? o : o.label;

              return (
                <label
                  key={id}
                  className="flex items-center gap-2 px-3 py-1.5 text-xs cursor-pointer hover:bg-slate-50 whitespace-nowrap"
                >
                  <input
                    type="checkbox"
                    checked={valor.includes(id)}
                    onChange={() => alternar(id)}
                    className="w-3.5 h-3.5 accent-slate-900"
                  />
                  <span>{label}</span>
                </label>
              );
            })}
          </div>,
          document.body,
        )}
    </div>
  );
}
