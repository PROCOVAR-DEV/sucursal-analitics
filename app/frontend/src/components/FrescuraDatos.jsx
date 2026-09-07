import { Database } from "lucide-react";
import { useEffect, useState } from "react";

import { getVentraEstado } from "../api.js";

/**
 * «¿Estos datos están al día?» — la pregunta que se hace antes de creerse ningún número.
 *
 * Los datos de Ventra los trae una corrida diaria, y hasta ahora no había forma de saber si
 * había corrido: el hilo no deja traza en el registro, así que para responderlo había que
 * entrar al servidor y mirar la base.
 *
 * Es una línea en la cabecera. Se pone en ámbar pasadas 26 horas —la corrida es diaria, así
 * que un día y pico sin traer nada es que algo se paró— y al pasar por encima sale el
 * detalle de las diez bases.
 */
const HORAS_SOSPECHA = 26;

function hace(iso) {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);

  if (min < 2) return "hace un momento";
  if (min < 60) return `hace ${min} min`;

  const h = Math.round(min / 60);

  if (h < 24) return h === 1 ? "hace 1 hora" : `hace ${h} horas`;

  const d = Math.round(h / 24);

  return d === 1 ? "hace 1 día" : `hace ${d} días`;
}

export function FrescuraDatos() {
  const [estado, setEstado] = useState(null);

  useEffect(() => {
    let vivo = true;

    getVentraEstado()
      .then((d) => { if (vivo) setEstado(d); })
      .catch(() => {});

    return () => { vivo = false; };
  }, []);

  // Sin dato no se pinta nada: una etiqueta vacía en la cabecera confunde más que la
  // ausencia, y esto es información de apoyo, no una alarma.
  if (!estado?.traido) return null;

  const horas = (Date.now() - new Date(estado.traido).getTime()) / 3600000;
  const viejo = horas > HORAS_SOSPECHA;
  const detalle = (estado.bases || [])
    .map((b) => `${b.base}: ventas hasta ${b.ultima_venta || "—"} · ${b.lineas.toLocaleString("es-CO")} líneas`)
    .join("\n");

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
        viejo ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-500"
      }`}
      title={`Última vez que entró algo de Ventra: ${new Date(estado.traido).toLocaleString("es-ES")}\n\n${detalle}`}
    >
      <Database size={13} />
      Datos {hace(estado.traido)}
      {viejo && " · revisar"}
    </span>
  );
}
