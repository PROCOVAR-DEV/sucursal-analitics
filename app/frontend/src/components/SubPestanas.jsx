import { cn } from "./ui.jsx";

/**
 * El conmutador de profundidad dentro de una vista.
 *
 * # Por qué existe
 *
 * Arriba había nueve pestañas y muchas contestaban la misma pregunta desde otra
 * profundidad: «Resumen», «Ventas (HL)» y «Market» son las tres «¿cómo vamos?» —el
 * panorama, el detalle por gestor y la semana a semana—. Puestas al mismo nivel parecían
 * nueve temas distintos y había que abrirlas una a una para recordar cuál era cuál.
 *
 * Aquí la pregunta se elige arriba y la profundidad, dentro. La barra de arriba pasa a
 * tener cuatro entradas y cada una dice lo que contesta.
 *
 * # Por qué no un desplegable
 *
 * Son dos o tres opciones y hay que poder saltar entre ellas todo el rato comparando.
 * Un desplegable esconde las que no están elegidas y obliga a dos clics para cada salto.
 */
export function SubPestanas({ opciones, valor, onCambio }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-200 pb-2">
      {opciones.map((o) => (
        <button
          key={o.id}
          className={cn(
            "shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            valor === o.id
              ? "bg-brand-600 text-white"
              : o.desactivada
                ? "text-slate-300 cursor-not-allowed"
                : "text-slate-600 hover:bg-slate-100",
          )}
          disabled={o.desactivada}
          // El porqué de que esté apagada, al pasar por encima: una pestaña gris sin
          // explicación se lee como que algo está roto.
          title={o.desactivada ? o.motivo || "" : o.sub || ""}
          type="button"
          onClick={() => !o.desactivada && onCambio(o.id)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
