import { useEffect, useState } from "react";

import { recargarLimpio, vigilarVersion } from "../lib/version-nueva";

/** Cuánto se calla el aviso cuando alguien pulsa «Ahora no». */
const POSPUESTO = 30 * 60_000;

/**
 * «Hay una versión nueva — recarga».
 *
 * Va montado junto a <App/>, fuera de todo, para que salga también en la pantalla de
 * entrar. Y no se puede quitar del todo: «Ahora no» lo calla media hora y vuelve. Una ✕
 * definitiva lo convertiría en algo que se cierra sin leer el primer día y ya nunca
 * avisa de nada.
 */
export default function AvisoVersionNueva() {
  const [hayNueva, setHayNueva] = useState(false);

  useEffect(() => vigilarVersion(() => setHayNueva(true)), []);

  if (!hayNueva) return null;

  return (
    <div
      aria-live="polite"
      role="status"
      className="fixed inset-x-3 bottom-3 z-50 mx-auto max-w-md rounded-xl border border-amber-300 bg-amber-50 p-3 shadow-lg sm:inset-x-auto sm:bottom-4 sm:right-4"
    >
      <p className="text-sm font-semibold text-amber-900">Hay una versión nueva</p>
      {/* Aquí importa decir POR QUÉ molesta: en un panel una versión vieja no rompe
          nada, sólo enseña cifras calculadas con código que ya se cambió. */}
      <p className="mt-1 text-xs text-amber-800">
        Esta pestaña está usando una versión anterior y puede estar enseñando cifras
        calculadas con el código de antes. Recarga para verlas con la versión de ahora.
      </p>
      <div className="mt-3 flex gap-2">
        <button
          className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700"
          onClick={recargarLimpio}
        >
          Recargar ahora
        </button>
        <button
          className="rounded-lg px-3 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-100"
          onClick={() => {
            setHayNueva(false);
            // Vuelve sola: el aviso no se puede quitar del todo, sólo aplazar.
            setTimeout(() => setHayNueva(true), POSPUESTO);
          }}
        >
          Ahora no
        </button>
      </div>
    </div>
  );
}
