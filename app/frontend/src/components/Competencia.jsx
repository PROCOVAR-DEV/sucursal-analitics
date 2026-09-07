import { Trophy } from "lucide-react";
import { useEffect, useState } from "react";

import { getCompetencia } from "../api.js";
import { formatNumber } from "./Kpi.jsx";
import { cn } from "./ui.jsx";

/**
 * La tabla de posiciones de la sucursal: quién va delante y en qué puesto voy yo.
 *
 * # Por qué hace falta
 *
 * Un gestor sólo ve SUS datos, y eso está bien. Pero entonces su cifra no significa nada:
 * un 78 % de cumplimiento es bueno si los demás van por 60 y malo si van por 95, y desde su
 * pantalla no había forma de saberlo.
 *
 * # Qué enseña y qué no
 *
 * Hectolitros, cuota y porcentaje. **Ni importe ni comisión**: saber que un compañero va
 * por delante en hectolitros es sano; saber cuánto dinero hizo no es asunto suyo. El
 * recorte lo hace el servidor, no esta pantalla.
 *
 * # Ordenada por CUMPLIMIENTO, no por hectolitros
 *
 * Quien tiene una cuota pequeña y la cumple va mejor que quien vende más y no llega a la
 * suya. Es lo que se premia, así que es como se ordena.
 */
export function Competencia({ sourceId, period }) {
  const [datos, setDatos] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelado = false;

    setDatos(null);
    setErr(null);
    getCompetencia(sourceId, period)
      .then((d) => { if (!cancelado) setDatos(d); })
      .catch((e) => { if (!cancelado) setErr(e?.response?.data?.detail || e.message); });

    return () => { cancelado = true; };
  }, [sourceId, period]);

  // Sin datos no se pinta un hueco vacío: en «Todas las sucursales» este endpoint no
  // aplica, y una tarjeta con un error dentro sólo asusta.
  if (err || !datos || !datos.filas?.length) return null;

  const { filas, yo, mi_puesto: miPuesto, total } = datos;

  return (
    <div className="card">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-800 flex items-center gap-2">
            <Trophy className="text-brand-600" size={17} /> Cómo va la competencia
          </h3>
          <p className="text-xs text-slate-500">
            Por cumplimiento de la cuota, no por hectolitros: cumplir la tuya vale más que
            vender mucho sin llegar.
          </p>
        </div>
        {miPuesto && (
          <span className="rounded-full bg-brand-50 px-3 py-1 text-sm font-semibold text-brand-700">
            Vas {miPuesto}.º de {total}
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wide text-slate-500">
              <th className="px-2 py-2 text-left font-semibold">#</th>
              <th className="px-2 py-2 text-left font-semibold">Gestor</th>
              <th className="px-2 py-2 text-right font-semibold">HL</th>
              <th className="px-2 py-2 text-right font-semibold">Cuota</th>
              <th className="px-2 py-2 text-right font-semibold">Cumple</th>
              <th className="px-2 py-2 text-left font-semibold w-1/3">&nbsp;</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => {
              const mio = yo && f.gestor === yo;
              // El color dice UNA cosa: si llega a su cuota. Nada de un color por persona.
              const tono =
                f.cumplimiento_pct >= 100 ? "bg-emerald-500"
                  : f.cumplimiento_pct >= 80 ? "bg-amber-500"
                    : "bg-red-400";

              return (
                <tr
                  key={f.gestor}
                  className={cn(
                    "border-t border-slate-100",
                    // La fila propia se marca de verdad: en una lista de veinte, buscarse
                    // por el nombre es lo que hace que nadie la use.
                    mio && "bg-brand-50/70 font-semibold",
                  )}
                >
                  <td className="px-2 py-2 tabular-nums text-slate-400">{f.puesto}</td>
                  <td className="px-2 py-2 whitespace-nowrap">
                    {f.gestor}
                    {mio && <span className="ml-2 text-[10px] uppercase tracking-wide text-brand-600">tú</span>}
                  </td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatNumber(f.hectolitros, 2)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-slate-500">{formatNumber(f.cuota, 0)}</td>
                  <td className={cn(
                    "px-2 py-2 text-right tabular-nums font-semibold",
                    f.cumplimiento_pct >= 100 ? "text-emerald-600"
                      : f.cumplimiento_pct >= 80 ? "text-amber-600" : "text-red-600",
                  )}>
                    {formatNumber(f.cumplimiento_pct, 1)}%
                  </td>
                  <td className="px-2 py-2">
                    {/* La barra es lo que hace que se lea de un vistazo: con veinte
                        porcentajes en columna hay que compararlos de uno en uno. */}
                    <div className="h-2 w-full rounded-full bg-slate-100">
                      <div
                        className={cn("h-2 rounded-full", tono)}
                        style={{ width: `${Math.min(100, Math.max(2, f.cumplimiento_pct))}%` }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
