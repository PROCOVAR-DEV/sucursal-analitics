import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { getSinVendedor } from "../api.js";
import { formatMoney } from "./Kpi.jsx";

/**
 * LAS FACTURAS QUE NO TIENEN VENDEDOR, una a una y con su nota.
 *
 * El Resumen sólo da el total («Sin vendedor $ 325»), y con un total no se puede arreglar
 * nada: hace falta saber QUÉ factura es y qué dice su nota —vacía, sin `V-`, con una errata
 * del nombre— para corregirla en Ventra o darle de alta el alias. El 16/10/2026 Jose vio una
 * venta de Holguín «en blanco» y no había dónde mirar cuál era.
 *
 * Administrador y supervisor (el supervisor, sólo sus sucursales). Se abre desde la tarjeta «Sin vendedor» y respeta el mismo periodo y
 * la misma sucursal (o «todas») que el Resumen que la abrió.
 */
export default function ListaSinVendedor({ sourceId, period, todas, onClose }) {
  const [filas, setFilas] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setFilas(null); setErr(null);
    getSinVendedor(sourceId, period)
      .then((d) => { if (!cancelled) setFilas(d.facturas || []); })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || e.message); });
    return () => { cancelled = true; };
  }, [sourceId, period]);

  useEffect(() => {
    const onEsc = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [onClose]);

  const total = (filas || []).reduce((s, f) => s + f.importe, 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-3" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="flex max-h-[85vh] w-full max-w-5xl flex-col rounded-xl bg-white shadow-xl" role="dialog" aria-label="Facturas sin vendedor">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-4">
          <div>
            <h3 className="text-lg font-bold">Facturas sin vendedor</h3>
            <p className="text-xs text-slate-500">
              {todas ? "Todas las sucursales" : "Esta sucursal"} · la nota es lo que hay que corregir en Ventra
              (o darle el alias a su vendedor en la configuración de la sucursal).
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar" className="rounded-lg p-1 text-slate-500 hover:bg-slate-100"><X size={18} /></button>
        </div>

        <div className="overflow-auto p-4">
          {err ? <p className="text-red-600">{err}</p>
            : filas === null ? <p>Cargando…</p>
            : filas.length === 0 ? <p className="text-slate-500">No hay facturas sin vendedor en este periodo.</p>
            : (
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-1 pr-3">Fecha</th>
                    <th className="py-1 pr-3">Factura</th>
                    {todas && <th className="py-1 pr-3">Sucursal</th>}
                    <th className="py-1 pr-3">Cliente</th>
                    <th className="py-1 pr-3 text-right">Importe</th>
                    <th className="py-1">Nota</th>
                  </tr>
                </thead>
                <tbody>
                  {filas.map((f, i) => (
                    <tr key={`${f.sucursal}-${f.factura}-${i}`} className="border-t border-slate-100 align-top">
                      <td className="py-1.5 pr-3 whitespace-nowrap">{f.fecha || "—"}</td>
                      <td className="py-1.5 pr-3 whitespace-nowrap font-medium">{f.factura || "—"}</td>
                      {todas && <td className="py-1.5 pr-3 whitespace-nowrap">{f.sucursal}</td>}
                      <td className="py-1.5 pr-3">
                        {f.cliente || "—"}
                        <span className="block text-xs text-slate-400">{f.punto}{f.punto ? " · " : ""}{f.lineas} línea{f.lineas === 1 ? "" : "s"}</span>
                      </td>
                      <td className="py-1.5 pr-3 text-right whitespace-nowrap tabular-nums">{formatMoney(f.importe)}</td>
                      <td className="py-1.5 font-mono text-xs whitespace-pre-wrap wrap-break-word">
                        {f.nota ? f.nota : <span className="font-sans italic text-red-600">(nota vacía)</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </div>

        {filas && filas.length > 0 && (
          <div className="border-t border-slate-200 p-3 text-right text-sm">
            {filas.length} factura{filas.length === 1 ? "" : "s"} · <b>{formatMoney(total)}</b>
          </div>
        )}
      </div>
    </div>
  );
}
