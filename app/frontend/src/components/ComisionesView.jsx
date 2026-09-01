import { AlertTriangle, Globe, Percent, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import {
  addComision, addComisionGlobal, deleteComision, deleteComisionGlobal,
  listComisiones, listComisionesGlobales, updateComision, updateComisionGlobal,
} from "../api.js";
import { Badge, Buscador, Button, ContadorFiltro, Field, IconButton, Panel, PanelHeader, Select, TablaScroll, cn, useFiltroTabla } from "./ui.jsx";

/**
 * Reglas de comisión por producto.
 *
 * Dos ámbitos, misma pantalla:
 *   - GLOBAL (desde "Todas"): la regla vale para las siete sucursales.
 *   - SUCURSAL: solo para esa, y manda sobre la global cuando apuntan a lo mismo.
 *
 * En modo sucursal se enseñan además las globales que le afectan, en gris y sin
 * poder tocarlas. Si no se vieran, alguien crearía aquí una regla sin saber que
 * ya había otra por encima y no entendería el número que sale.
 *
 * Los porcentajes se escriben COMO PORCENTAJE (2 = 2%) y se guardan como
 * fracción (0.02). La conversión se hace aquí porque nadie escribe "0.008"
 * cuando quiere decir 0,8%, y el servidor rechaza cualquier cosa mayor que 1
 * justamente para que un despiste no se convierta en una comisión del 200%.
 */

const TIPOS = [
  { value: "producto", label: "Producto (por su nombre)" },
  { value: "grupo", label: "Grupo comercial entero" },
];

const aPorciento = (pct) => +(Number(pct || 0) * 100).toFixed(4);
const aFraccion = (porciento) => Number(porciento || 0) / 100;

const VACIA = { tipo: "producto", objetivo: "", porciento: "", desde: "", hasta: "", nombre: "" };

export default function ComisionesView({ sid, esGlobal, puedeEditar = true, flash }) {
  const [datos, setDatos] = useState(null);
  const [nueva, setNueva] = useState(VACIA);
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState(null); // {id, porciento, hasta}
  const [error, setError] = useState(null);

  const cargar = async () => {
    const d = esGlobal ? await listComisionesGlobales() : await listComisiones(sid);
    setDatos(d);
    return d;
  };

  useEffect(() => {
    setDatos(null);
    setError(null);
    cargar().catch((e) => setError(detalle(e)));
  }, [sid, esGlobal]);

  function detalle(e) {
    return e?.response?.data?.detail || e?.message || "No se pudo completar la operación";
  }

  async function crear() {
    setError(null);
    try {
      const cuerpo = {
        tipo: nueva.tipo,
        objetivo: nueva.objetivo.trim(),
        pct: aFraccion(nueva.porciento),
        desde: nueva.desde,
        hasta: nueva.hasta || null,
        nombre: nueva.nombre.trim() || undefined,
      };
      const d = esGlobal ? await addComisionGlobal(cuerpo) : await addComision(sid, cuerpo);
      setDatos(d);
      setNueva(VACIA);
      setCreando(false);
      flash?.("ok", "Regla creada");
    } catch (e) {
      setError(detalle(e));
    }
  }

  async function guardarEdicion(r) {
    setError(null);
    try {
      const cuerpo = { pct: aFraccion(editando.porciento), hasta: editando.hasta || null };
      const d = esGlobal
        ? await updateComisionGlobal(r.id, cuerpo)
        : await updateComision(sid, r.id, cuerpo);
      setDatos(d);
      setEditando(null);
      flash?.("ok", "Regla actualizada");
    } catch (e) {
      setError(detalle(e));
    }
  }

  async function borrar(r) {
    const ok = window.confirm(
      `¿Borrar «${r.nombre}»?\n\nOJO: borrar la quita del historial entero, como si nunca ` +
      `hubiera existido, y los informes de meses anteriores cambiarán.\n\n` +
      `Si lo que quieres es que DEJE de aplicarse a partir de ahora, no la borres: ` +
      `edítala y ponle un mes final.`,
    );
    if (!ok) return;
    setError(null);
    try {
      const d = esGlobal ? await deleteComisionGlobal(r.id) : await deleteComision(sid, r.id);
      setDatos(d);
      flash?.("ok", "Regla borrada");
    } catch (e) {
      setError(detalle(e));
    }
  }

  if (!datos && !error) return <div className="p-6 text-slate-500 animate-pulse">Cargando reglas…</div>;

  const items = datos?.items || [];
  const globales = datos?.globales || [];
  const avisos = datos?.avisos || [];
  const mes = datos?.mes_actual || "";

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader
          icon={esGlobal ? Globe : Percent}
          title={esGlobal ? "Comisiones para TODAS las sucursales" : "Comisiones de esta sucursal"}
          sub={
            esGlobal
              ? "Lo que se ponga aquí aplica a las siete. Una sucursal puede tener la suya y esa manda."
              : `Solo para esta sucursal. Lo que no tenga regla cobra la comisión general${
                  datos?.comision_general_pct != null ? ` (${aPorciento(datos.comision_general_pct)}%)` : ""
                }.`
          }
          right={
            puedeEditar && !creando ? (
              <Button icon={Plus} onClick={() => { setCreando(true); setNueva({ ...VACIA, desde: mes }); }}>
                Nueva regla
              </Button>
            ) : null
          }
        />

        {error && (
          <div className="mx-5 mt-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm px-4 py-3">
            {error}
          </div>
        )}

        {/* Los avisos de solape se ven SIEMPRE que existan, no solo al crear la
            regla: si no, quien entre mañana no sabría que dos reglas se pisan. */}
        {avisos.length > 0 && (
          <div className="mx-5 mt-4 space-y-2">
            {avisos.map((a, i) => (
              <div key={i} className="flex gap-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-sm px-4 py-3">
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <span>{a.mensaje}</span>
              </div>
            ))}
          </div>
        )}

        {creando && (
          <div className="mx-5 mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <Field label="¿A qué se aplica?">
                <Select
                  value={nueva.tipo}
                  options={TIPOS}
                  onChange={(v) => setNueva({ ...nueva, tipo: v })}
                />
              </Field>
              <Field
                label={nueva.tipo === "grupo" ? "Grupo comercial" : "El nombre del producto contiene"}
                hint={
                  nueva.tipo === "grupo"
                    ? "Tal cual sale en «Grupos y productos» (ej. PARRANDA)."
                    : "ARROZ coge todos los arroces. ARROZ PATEKO, solo ese."
                }
                value={nueva.objetivo}
                onChange={(e) => setNueva({ ...nueva, objetivo: e.target.value })}
                placeholder={nueva.tipo === "grupo" ? "PARRANDA" : "ARROZ"}
              />
              <Field
                label="Comisión (%)"
                hint="En porciento: 2 es 2%, 0.8 es 0,8%."
                type="number"
                step="0.01"
                value={nueva.porciento}
                onChange={(e) => setNueva({ ...nueva, porciento: e.target.value })}
                placeholder="2"
              />
              <Field
                label="Desde el mes"
                hint={`No puede ser anterior a ${mes}: los meses cerrados ya se pagaron.`}
                type="month"
                min={mes}
                value={nueva.desde}
                onChange={(e) => setNueva({ ...nueva, desde: e.target.value })}
              />
              <Field
                label="Hasta el mes (opcional)"
                hint="Vacío = sigue vigente hasta que se diga lo contrario."
                type="month"
                min={nueva.desde || mes}
                value={nueva.hasta}
                onChange={(e) => setNueva({ ...nueva, hasta: e.target.value })}
              />
              <Field
                label="Nombre (opcional)"
                hint="Para reconocerla en la lista."
                value={nueva.nombre}
                onChange={(e) => setNueva({ ...nueva, nombre: e.target.value })}
                placeholder="Arroz 2%"
              />
            </div>
            <div className="flex gap-2 mt-4">
              <Button icon={Save} onClick={crear}>Crear regla</Button>
              <Button variant="ghost" icon={X} onClick={() => { setCreando(false); setError(null); }}>Cancelar</Button>
            </div>
          </div>
        )}

        <div className="p-5">
          {items.length === 0 ? (
            <div className="text-slate-400 text-sm py-6 text-center">
              Sin reglas propias. Todo cobra la comisión general.
            </div>
          ) : (
            <Tabla
              reglas={items}
              mes={mes}
              puedeEditar={puedeEditar}
              editando={editando}
              setEditando={setEditando}
              onGuardar={guardarEdicion}
              onBorrar={borrar}
            />
          )}
        </div>
      </Panel>

      {/* En modo sucursal, lo global se ve pero no se toca. */}
      {!esGlobal && globales.length > 0 && (
        <Panel>
          <PanelHeader
            icon={Globe}
            title="Reglas globales que también aplican aquí"
            sub="Se editan en Config → Todas → Comisiones. Si esta sucursal tiene una regla para lo mismo, manda la de aquí."
          />
          <div className="p-5">
            <Tabla reglas={globales} mes={mes} puedeEditar={false} soloLectura />
          </div>
        </Panel>
      )}
    </div>
  );
}

function estado(r, mes) {
  // Los tonos son los que existen en index.css: brand, green, amber, red, slate.
  if (r.hasta && r.hasta < mes) return { texto: `Terminó ${r.hasta}`, tono: "slate" };
  if (r.desde > mes) return { texto: `Empieza ${r.desde}`, tono: "brand" };
  return { texto: "Vigente", tono: "green" };
}

function Tabla({ reglas, mes, puedeEditar, editando, setEditando, onGuardar, onBorrar, soloLectura }) {
  const { q, setQ, filtradas } = useFiltroTabla(reglas);

  return (
    <div className="w-full min-w-0">
      {/* Con veinte reglas por sucursal, encontrar la del producto que se busca a ojo es
          justo lo que no se puede hacer en un teléfono. */}
      {(reglas || []).length > 8 && (
        <div className="mb-2 flex justify-end">
          <Buscador onChange={setQ} placeholder="Regla, grupo o producto…" value={q} />
        </div>
      )}
      <ContadorFiltro mostradas={filtradas.length} q={q} total={(reglas || []).length} />
      <TablaScroll className="!mx-0 !px-0">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left border-b border-slate-200 text-slate-500">
            <th className="py-2 pr-4">Regla</th>
            <th className="py-2 pr-4">Se aplica a</th>
            <th className="py-2 pr-4 text-right">%</th>
            <th className="py-2 pr-4">Desde</th>
            <th className="py-2 pr-4">Hasta</th>
            <th className="py-2 pr-4">Estado</th>
            {!soloLectura && <th className="py-2" />}
          </tr>
        </thead>
        <tbody>
          {filtradas.map((r) => {
            const ed = editando?.id === r.id;
            const est = estado(r, mes);

            return (
              <tr key={r.id} className={cn("border-b border-slate-100", soloLectura && "text-slate-500")}>
                <td className="py-2 pr-4 font-medium">{r.nombre}</td>
                <td className="py-2 pr-4">
                  <span className="text-slate-500">{r.tipo === "grupo" ? "Grupo" : "Producto"}</span>{" "}
                  <span className="font-mono text-xs bg-slate-100 rounded px-1.5 py-0.5">{r.objetivo}</span>
                </td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {ed ? (
                    <input
                      type="number" step="0.01"
                      className="w-20 border border-slate-300 rounded px-2 py-1 text-right"
                      value={editando.porciento}
                      onChange={(e) => setEditando({ ...editando, porciento: e.target.value })}
                    />
                  ) : (
                    `${aPorciento(r.pct)}%`
                  )}
                </td>
                <td className="py-2 pr-4 tabular-nums">{r.desde}</td>
                <td className="py-2 pr-4 tabular-nums">
                  {ed ? (
                    <input
                      type="month" min={mes}
                      className="border border-slate-300 rounded px-2 py-1"
                      value={editando.hasta}
                      onChange={(e) => setEditando({ ...editando, hasta: e.target.value })}
                    />
                  ) : (
                    r.hasta || <span className="text-slate-400">—</span>
                  )}
                </td>
                <td className="py-2 pr-4"><Badge tone={est.tono}>{est.texto}</Badge></td>
                {!soloLectura && (
                  <td className="py-2 text-right whitespace-nowrap">
                    {puedeEditar && (ed ? (
                      <>
                        <IconButton icon={Save} onClick={() => onGuardar(r)} title="Guardar" />
                        <IconButton icon={X} onClick={() => setEditando(null)} title="Cancelar" />
                      </>
                    ) : (
                      <>
                        <IconButton
                          icon={Percent}
                          title="Cambiar % o cerrar la regla"
                          onClick={() => setEditando({ id: r.id, porciento: aPorciento(r.pct), hasta: r.hasta || "" })}
                        />
                        <IconButton icon={Trash2} variant="danger" title="Borrar" onClick={() => onBorrar(r)} />
                      </>
                    ))}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      </TablaScroll>
    </div>
  );
}
