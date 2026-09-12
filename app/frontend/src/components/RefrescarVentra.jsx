import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { estadoRefrescoVentra, refrescarVentra } from "../api.js";

/**
 * Traer de Ventra AHORA, sólo lo de esta sucursal.
 *
 * # Para qué
 *
 * Los datos entran solos cada hora y hay la recarga de las 6. Entre medias, quien acaba de
 * facturar y quiere ver su número no tiene nada que hacer salvo esperar sin saber cuánto.
 * Esto es el botón para no esperar.
 *
 * # Por qué tiene freno y se ve
 *
 * Ventra no es nuestro: un botón sin tope son diez personas pulsándolo cuando algo va
 * lento, y eso sí puede tumbarlo para todos. El servidor permite **seis por hora y
 * sucursal**, con un minuto entre dos seguidos, y aquí se enseña cuántos quedan — un botón
 * que se niega sin decir por qué se pulsa más, no menos.
 *
 * Y trae **sólo lo de esta sucursal**: el servidor traduce el id de sucursal a su base de
 * Ventra y no hay forma de que arranque lo de otra.
 */
export default function RefrescarVentra({ sid, onListo }) {
  const [estado, setEstado] = useState(null);
  const [yendo, setYendo] = useState(false);
  const [aviso, setAviso] = useState(null);

  const mirar = useCallback(async () => {
    if (!sid) return;
    try {
      setEstado(await estadoRefrescoVentra(sid));
    } catch {
      // Si no se puede preguntar, el botón se queda como esté: no es motivo para
      // esconderlo ni para bloquearlo.
    }
  }, [sid]);

  useEffect(() => {
    mirar();
  }, [mirar]);

  if (!sid || (estado && !estado.puede && estado.restantes === 0 && !estado.segundos)) {
    // Sucursal sin base en Ventra: no se enseña un botón que nunca va a funcionar.
    return null;
  }

  const puede = estado ? estado.puede : true;

  const traer = async () => {
    setYendo(true);
    setAviso(null);
    try {
      const r = await refrescarVentra(sid);

      setAviso({
        ok: true,
        texto: r.lineas > 0
          ? `${r.lineas.toLocaleString("es")} líneas traídas`
          : "ya estaba al día",
      });
      // Los datos han cambiado, así que quien nos pintó tiene que volver a pedirlos.
      onListo?.();
    } catch (e) {
      setAviso({ ok: false, texto: String(e?.message || e).slice(0, 90) });
    } finally {
      setYendo(false);
      mirar();
      // El aviso se va solo: es una confirmación, no algo que haya que cerrar.
      setTimeout(() => setAviso(null), 6000);
    }
  };

  return (
    <span className="inline-flex items-center gap-2">
      <button
        className={`shrink-0 inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
          puede && !yendo
            ? "border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700"
            : "border-slate-200 text-slate-300 cursor-not-allowed"
        }`}
        disabled={!puede || yendo}
        title={
          yendo
            ? "Trayendo de Ventra…"
            : puede
              ? `Trae ahora lo de esta sucursal. Quedan ${estado?.restantes ?? "?"} esta hora.`
              : `${estado?.motivo ?? "ahora no"}${estado?.segundos ? ` · vuelve a intentarlo en ${estado.segundos} s` : ""}`
        }
        type="button"
        onClick={traer}
      >
        <RefreshCw className={yendo ? "animate-spin" : ""} size={13} />
        {yendo ? "Trayendo…" : "Traer de Ventra"}
      </button>

      {aviso && (
        <span className={`text-xs ${aviso.ok ? "text-emerald-600" : "text-amber-600"}`}>{aviso.texto}</span>
      )}
    </span>
  );
}
