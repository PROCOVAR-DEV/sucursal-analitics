import {
  Building2, Calculator, Layers, Plus, RotateCcw, Save, Settings2, SlidersHorizontal,
  Target, Trash2, UserPlus, Users, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  addGestor, createSucursal, createUser, deleteGestor, deleteSucursal, deleteUser,
  getSucursal, listUsers, resetSucursal, updateGestor, updateSucursal, updateUser,
} from "../api.js";
import CalculadoraView from "./CalculadoraView.jsx";
import { Badge, Button, Field, IconButton, MultiSelect, Panel, PanelHeader, SearchSelect, Select, Toast, cn } from "./ui.jsx";

const ROLE_OPTS = [
  { value: "admin", label: "Admin (todo)" },
  { value: "analitico", label: "Analítico (ve todas, solo lectura)" },
  { value: "supervisor", label: "Supervisor (su sucursal + metas)" },
  { value: "usuario", label: "Usuario (ve su sucursal)" },
  { value: "gestor", label: "Gestor (solo sus datos)" },
];
const sucOpts = (sucursales) => sucursales.map((s) => ({ value: s.id, label: s.nombre }));
const ALL_ROLES = ["admin", "analitico"];

export default function AdminPanel({ sid, user, sucursales, onSucursalesChanged, section = "sucursal", onSection }) {
  const [cfg, setCfg] = useState(null);
  const [msg, setMsg] = useState(null);
  const tab = section;
  const setTab = (id) => onSection?.(id);
  const role = user?.role;
  const isAdmin = role === "admin";
  const isSup = role === "supervisor";

  const load = () => getSucursal(sid).then(setCfg).catch((e) => flash("err", e?.response?.data?.detail || e.message));
  useEffect(() => { if (!sid) return; setCfg(null); load(); }, [sid]);
  // Refresca la config al cambiar de pestaña: cada pestaña siempre ve lo último
  // guardado en otra (sin tener que refrescar la página).
  useEffect(() => { if (sid) getSucursal(sid).then(setCfg).catch(() => {}); }, [section]);
  function flash(t, m) { setMsg({ t, m }); setTimeout(() => setMsg(null), 3500); }
  const reload = async () => setCfg(await getSucursal(sid));

  const ALL_TABS = [
    { id: "sucursal", label: "Sucursal", icon: Building2 },
    { id: "gestores", label: "Gestores", icon: Users },
    { id: "metas", label: "Metas", icon: Target },
    { id: "calculadora", label: "Calculadora de metas", icon: Calculator },
    { id: "grupos", label: "Grupos y productos", icon: Layers },
    { id: "parametros", label: "Parámetros", icon: SlidersHorizontal },
    ...(isAdmin ? [{ id: "sucursales", label: "Sucursales", icon: Building2 }] : []),
    ...(isAdmin ? [{ id: "usuarios", label: "Usuarios", icon: UserPlus }] : []),
  ];
  // Supervisor solo configura metas de su sucursal.
  const TABS = isSup ? ALL_TABS.filter((t) => t.id === "metas" || t.id === "calculadora") : ALL_TABS;
  // Si la sección actual no está permitida para el rol, ir a la primera válida.
  // OJO: este useEffect debe ir ANTES de cualquier return temprano; si queda
  // después de `if (!cfg) return`, el nº de hooks cambia entre renders y React
  // revienta ("Rendered more hooks…") dejando la pantalla en blanco.
  useEffect(() => {
    if (TABS.length && !TABS.some((t) => t.id === tab)) onSection?.(TABS[0].id);
  }, [tab, isSup, isAdmin]);

  if (!cfg) return <div className="p-6 text-slate-500 animate-pulse">Cargando configuración…</div>;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="section-title flex items-center gap-2"><Settings2 className="text-brand-600" size={22} /> Configuración · {cfg.nombre}</h2>
          <p className="text-sm text-slate-500">Todo es editable y se guarda por sucursal.</p>
        </div>
        <Button variant="subtle" icon={RotateCcw} onClick={async () => {
          if (!confirm("¿Restaurar metas y parámetros por defecto? (los gestores se mantienen)")) return;
          setCfg(await resetSucursal(sid)); flash("ok", "Metas y parámetros restaurados");
        }}>Restaurar metas/parámetros</Button>
      </div>

      <Toast msg={msg} onClose={() => setMsg(null)} />

      {/* Sub-navegación */}
      <div className="flex items-center gap-1.5 overflow-x-auto scroll-thin border-b border-slate-200 pb-2">
        {TABS.map((t) => (
          <button key={t.id} className={cn("tab shrink-0", tab === t.id && "tab-active")} onClick={() => setTab(t.id)}>
            <t.icon size={15} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "sucursal" && <DatosSucursal cfg={cfg} sid={sid} onSaved={(c) => { setCfg(c); flash("ok", "Datos guardados"); onSucursalesChanged?.(); }} />}
      {tab === "gestores" && <Gestores cfg={cfg} sid={sid} reload={reload} flash={flash} />}
      {tab === "metas" && <Metas cfg={cfg} sid={sid} onSaved={(c) => { setCfg(c); flash("ok", "Metas guardadas"); }} />}
      {tab === "calculadora" && <CalculadoraView cfg={cfg} sid={sid} onSaved={(c) => setCfg(c)} />}
      {tab === "grupos" && <Grupos cfg={cfg} sid={sid} onSaved={(c) => { setCfg(c); flash("ok", "Grupos guardados"); }} />}
      {tab === "parametros" && <Parametros cfg={cfg} sid={sid} onSaved={(c) => { setCfg(c); flash("ok", "Parámetros guardados"); }} />}
      {tab === "sucursales" && isAdmin && <Sucursales sucursales={sucursales} onChanged={onSucursalesChanged} flash={flash} />}
      {tab === "usuarios" && isAdmin && <Usuarios sucursales={sucursales} flash={flash} />}
    </div>
  );
}

// ---------------- Datos de la sucursal
function DatosSucursal({ cfg, sid, onSaved }) {
  const [nombre, setNombre] = useState(cfg.nombre);
  const [sup, setSup] = useState(cfg.supervisor_nombre || "");
  useEffect(() => { setNombre(cfg.nombre); setSup(cfg.supervisor_nombre || ""); }, [cfg]);
  return (
    <Panel>
      <PanelHeader icon={Building2} title="Datos de la sucursal"
        right={<Button icon={Save} onClick={async () => onSaved(await updateSucursal(sid, { nombre, supervisor_nombre: sup }))}>Guardar</Button>} />
      <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
        <Field label="Nombre del supervisor (en reportes)" value={sup} onChange={(e) => setSup(e.target.value)} />
      </div>
    </Panel>
  );
}

// ---------------- Gestores CRUD
const emptyGestor = { clave: "", nombre: "", sector: "", agencia: "", cuota_hl: 0, cuota_ccc: 0, aliases: "", activo: true };

function Gestores({ cfg, sid, reload, flash }) {
  const [nuevo, setNuevo] = useState(emptyGestor);
  const now = new Date();
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() + 1 });
  const gestores = Object.entries(cfg.gestores || {});
  const pkey = pkeyOf(ym.y, ym.m);
  const monthConf = !!cfg.metas_mensuales?.[pkey];
  const monthG = cfg.metas_mensuales?.[pkey]?.gestores || {};

  // Avisar por notificación cuando el mes elegido no tiene metas configuradas.
  useEffect(() => {
    if (!monthConf) flash("warn", `${MESES[ym.m - 1]} ${ym.y} no tiene metas configuradas. Defínelas en la Calculadora.`);
  }, [pkey, monthConf]);

  async function saveRow(clave, g) {
    await updateGestor(sid, clave, {
      nueva_clave: g._clave, nombre: g.nombre, sector: g.sector, agencia: g.agencia,
      aliases: (g.aliases || "").split(",").map((s) => s.trim()).filter(Boolean), activo: g.activo,
    });
    await reload(); flash("ok", `Gestor ${clave} actualizado`);
  }
  async function addRow() {
    if (!nuevo.clave.trim() && !nuevo.nombre.trim()) return flash("err", "Clave o nombre requerido");
    await addGestor(sid, {
      clave: nuevo.clave || nuevo.nombre, nombre: nuevo.nombre, sector: nuevo.sector, agencia: nuevo.agencia,
      aliases: (nuevo.aliases || "").split(",").map((s) => s.trim()).filter(Boolean),
    });
    setNuevo(emptyGestor); await reload(); flash("ok", "Gestor agregado");
  }

  return (
    <Panel>
      <PanelHeader icon={Users} title="Gestores / Vendedores"
        sub={`${gestores.length} · identidad e historial de meta por mes. Las metas se editan en “Calculadora de metas”.`}
        right={
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Revisar mes:</span>
            <Select width="w-32" value={String(ym.m)} onChange={(v) => setYm({ ...ym, m: Number(v) })} options={MESES.map((n, i) => ({ value: String(i + 1), label: n }))} align="right" />
            <Select width="w-24" value={String(ym.y)} onChange={(v) => setYm({ ...ym, y: Number(v) })} options={[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => ({ value: String(y), label: String(y) }))} align="right" />
          </div>
        } />
      <div className="overflow-x-auto scroll-thin">
        <table className="tbl">
          <thead>
            <tr>{["Clave", "Nombre", "Sector", "Agencia", "Alias", "Activo", `Meta HL · ${MESES[ym.m - 1]}`, "Meta CCC", ""].map((h) => <th key={h}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {gestores.map(([clave, g]) => (
              <GestorRow key={clave} clave={clave} g={g} onSave={saveRow}
                monthConf={monthConf} mg={monthG[clave]} inMonth={clave in monthG}
                onDelete={async () => { if (confirm(`¿Eliminar gestor ${clave}?`)) { await deleteGestor(sid, clave); await reload(); flash("ok", "Gestor eliminado"); } }} />
            ))}
            <tr className="bg-brand-50/50">
              <td className="px-2 py-1.5 border-b border-slate-100"><input className="input input-sm w-24" placeholder="CLAVE" value={nuevo.clave} onChange={(e) => setNuevo({ ...nuevo, clave: e.target.value.toUpperCase() })} /></td>
              <td className="px-2 py-1.5 border-b border-slate-100"><input className="input input-sm w-32" placeholder="Nombre" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} /></td>
              <td className="px-2 py-1.5 border-b border-slate-100"><input className="input input-sm w-20" value={nuevo.sector} onChange={(e) => setNuevo({ ...nuevo, sector: e.target.value })} /></td>
              <td className="px-2 py-1.5 border-b border-slate-100"><input className="input input-sm w-24" value={nuevo.agencia} onChange={(e) => setNuevo({ ...nuevo, agencia: e.target.value })} /></td>
              <td className="px-2 py-1.5 border-b border-slate-100"><input className="input input-sm w-36" placeholder="alias1, alias2" value={nuevo.aliases} onChange={(e) => setNuevo({ ...nuevo, aliases: e.target.value })} /></td>
              <td className="border-b border-slate-100" colSpan={3}></td>
              <td className="px-2 py-1.5 border-b border-slate-100"><Button size="sm" icon={Plus} onClick={addRow}>Agregar</Button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function GestorRow({ clave, g, onSave, onDelete, monthConf, mg, inMonth }) {
  const [row, setRow] = useState({ ...g, _clave: clave, aliases: (g.aliases || []).join(", ") });
  useEffect(() => setRow({ ...g, _clave: clave, aliases: (g.aliases || []).join(", ") }), [g, clave]);
  const set = (k, v) => setRow({ ...row, [k]: v });
  const td = "px-2 py-1.5 border-b border-slate-100";
  return (
    <tr className="hover:bg-slate-50">
      <td className={td}><input className="input input-sm w-24 font-semibold" value={row._clave} onChange={(e) => set("_clave", e.target.value.toUpperCase())} /></td>
      <td className={td}><input className="input input-sm w-32" value={row.nombre} onChange={(e) => set("nombre", e.target.value)} /></td>
      <td className={td}><input className="input input-sm w-20" value={row.sector} onChange={(e) => set("sector", e.target.value)} /></td>
      <td className={td}><input className="input input-sm w-24" value={row.agencia} onChange={(e) => set("agencia", e.target.value)} /></td>
      <td className={td}><input className="input input-sm w-36" value={row.aliases} onChange={(e) => set("aliases", e.target.value)} /></td>
      <td className={cn(td, "text-center")}><input type="checkbox" className="accent-brand-600 w-4 h-4" checked={!!row.activo} onChange={(e) => set("activo", e.target.checked)} /></td>
      <td className={cn(td, "text-right tabular-nums font-semibold")}>{mg?.cuota_hl != null ? formatNumber2(mg.cuota_hl) : <span className="text-slate-300 italic font-normal text-xs">sin configurar</span>}</td>
      <td className={cn(td, "text-right tabular-nums")}>{mg?.cuota_ccc != null ? formatNumber2(mg.cuota_ccc) : <span className="text-slate-300 italic text-xs">—</span>}</td>
      <td className={cn(td, "whitespace-nowrap")}>
        <div className="flex gap-1">
          <IconButton variant="subtle" icon={Save} size={13} onClick={() => onSave(clave, row)} title="Guardar" />
          <IconButton variant="danger" icon={Trash2} size={13} onClick={onDelete} title="Eliminar" />
        </div>
      </td>
    </tr>
  );
}
const formatNumber2 = (n) => Number(n).toLocaleString("es-CO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ---------------- Metas (globales + por mes)
const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const pkeyOf = (y, m) => `${y}-${String(m).padStart(2, "0")}`;

function Metas({ cfg, sid, onSaved }) {
  const now = new Date();
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() + 1 });
  const [mDraft, setMDraft] = useState({});   // override parcial del mes seleccionado
  const [gDraft, setGDraft] = useState(null); // borrador de metas globales

  const pkey = pkeyOf(ym.y, ym.m);
  useEffect(() => { setMDraft(structuredClone(cfg.metas_mensuales?.[pkey] || {})); }, [cfg, pkey]);
  useEffect(() => { setGDraft(structuredClone(cfg.metas || {})); }, [cfg]);
  if (!gDraft) return null;

  const g = gDraft;
  const prods = Object.keys(g.metas_productos_ces || {});
  const hasOverride = Object.keys(mDraft).length > 0;

  // valor efectivo del mes = override ?? global
  const effM = (k) => (k in mDraft ? mDraft[k] : g[k]);
  const effProd = (p) => (mDraft.metas_productos_ces?.[p] ?? g.metas_productos_ces?.[p] ?? 0);
  const setMonthly = (k, v) => setMDraft({ ...mDraft, [k]: v });
  const setMonthlyProd = (p, v) => setMDraft({ ...mDraft, metas_productos_ces: { ...(mDraft.metas_productos_ces || {}), [p]: v } });

  async function saveGlobal() {
    onSaved(await updateSucursal(sid, { metas: {
      meta_hectolitros_total: Number(g.meta_hectolitros_total), meta_dinero_total: Number(g.meta_dinero_total),
      meta_ccc_total: Number(g.meta_ccc_total),
      metas_productos_ces: Object.fromEntries(Object.entries(g.metas_productos_ces || {}).map(([k, v]) => [k, Number(v)])),
    } }));
  }
  async function saveMonth() {
    const payload = {};
    for (const k of ["meta_hectolitros_total", "meta_dinero_total", "meta_ccc_total"]) if (k in mDraft) payload[k] = Number(mDraft[k]);
    if (mDraft.metas_productos_ces) payload.metas_productos_ces = Object.fromEntries(Object.entries(mDraft.metas_productos_ces).map(([k, v]) => [k, Number(v)]));
    onSaved(await updateSucursal(sid, { metas_mensuales: { [pkey]: payload } }));
  }
  async function clearMonth() {
    if (!confirm(`¿Borrar las metas específicas de ${MESES[ym.m - 1]} ${ym.y}? Volverá a usar las globales.`)) return;
    setMDraft({});
    onSaved(await updateSucursal(sid, { metas_mensuales: { [pkey]: null } }));
  }

  const yearOpts = [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => ({ value: String(y), label: String(y) }));
  const addProd = () => {
    const name = prompt("Nombre del nuevo producto")?.trim().toUpperCase();
    if (name) setGDraft({ ...g, metas_productos_ces: { ...g.metas_productos_ces, [name]: 0 } });
  };

  return (
    <div className="space-y-5">
      {/* Metas del mes */}
      <Panel>
        <PanelHeader icon={Target} title="Metas del mes"
          sub="Cada mes puede tener metas distintas. Se aplican al reporte según su fecha."
          right={
            <div className="flex items-center gap-2">
              <Select width="w-32" value={String(ym.m)} onChange={(v) => setYm({ ...ym, m: Number(v) })} options={MESES.map((n, i) => ({ value: String(i + 1), label: n }))} align="right" />
              <Select width="w-24" value={String(ym.y)} onChange={(v) => setYm({ ...ym, y: Number(v) })} options={yearOpts} align="right" />
              {hasOverride && <Button variant="danger" size="sm" icon={Trash2} onClick={clearMonth}>Borrar mes</Button>}
              <Button icon={Save} onClick={saveMonth}>Guardar mes</Button>
            </div>
          } />
        <div className="p-5 space-y-4">
          <div className="text-xs text-slate-500">
            {hasOverride ? `Editando metas específicas de ${MESES[ym.m - 1]} ${ym.y}.` : `Sin metas propias para ${MESES[ym.m - 1]} ${ym.y}: se usan las globales. Edita abajo para crear las del mes.`}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Field label={`Meta Hectolitros · ${MESES[ym.m - 1]}`} hint={"meta_hectolitros_total" in mDraft ? "override del mes" : `global: ${g.meta_hectolitros_total}`}
              type="number" value={effM("meta_hectolitros_total")} onChange={(e) => setMonthly("meta_hectolitros_total", e.target.value)} />
            <Field label="Meta Dinero ($)" hint={"meta_dinero_total" in mDraft ? "override del mes" : `global: ${g.meta_dinero_total}`}
              type="number" value={effM("meta_dinero_total")} onChange={(e) => setMonthly("meta_dinero_total", e.target.value)} />
            <Field label="Meta CCC (clientes)" hint={"meta_ccc_total" in mDraft ? "override del mes" : `global: ${g.meta_ccc_total}`}
              type="number" value={effM("meta_ccc_total")} onChange={(e) => setMonthly("meta_ccc_total", e.target.value)} />
          </div>
          <div>
            <h4 className="font-semibold text-sm mb-2 text-slate-700">Metas por producto · {MESES[ym.m - 1]} {ym.y}</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {prods.map((p) => {
                const ov = mDraft.metas_productos_ces && p in mDraft.metas_productos_ces;
                return (
                  <div key={p} className="rounded-lg border border-slate-200 p-2.5">
                    <span className="block text-[11px] font-semibold text-slate-600 mb-1 truncate" title={p}>{p}</span>
                    <input className="input input-sm num w-full" type="number" value={effProd(p)} onChange={(e) => setMonthlyProd(p, e.target.value)} />
                    <span className="block mt-0.5 text-[10px] text-slate-400">{ov ? "override del mes" : `global: ${g.metas_productos_ces?.[p] ?? 0}`}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </Panel>

      {/* Metas globales por defecto */}
      <Panel>
        <PanelHeader icon={Target} title="Valores globales por defecto"
          sub="Se usan cuando un mes no define sus propias metas"
          right={<Button variant="subtle" icon={Save} onClick={saveGlobal}>Guardar globales</Button>} />
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Field label="Meta Hectolitros (total)" type="number" value={g.meta_hectolitros_total} onChange={(e) => setGDraft({ ...g, meta_hectolitros_total: e.target.value })} />
            <Field label="Meta Dinero ($)" type="number" value={g.meta_dinero_total} onChange={(e) => setGDraft({ ...g, meta_dinero_total: e.target.value })} />
            <Field label="Meta CCC (clientes)" type="number" value={g.meta_ccc_total} onChange={(e) => setGDraft({ ...g, meta_ccc_total: e.target.value })} />
          </div>
          <div>
            <h4 className="font-semibold text-sm mb-2 text-slate-700">Metas por producto (global)</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {prods.map((p) => (
                <div key={p} className="relative rounded-lg border border-slate-200 p-2.5 pr-6">
                  <span className="block text-[11px] font-semibold text-slate-600 mb-1 truncate" title={p}>{p}</span>
                  <input className="input input-sm num w-full" type="number" value={g.metas_productos_ces[p]} onChange={(e) => setGDraft({ ...g, metas_productos_ces: { ...g.metas_productos_ces, [p]: e.target.value } })} />
                  <button className="absolute right-1.5 top-1.5 text-slate-300 hover:text-red-500" onClick={() => { const c = { ...g.metas_productos_ces }; delete c[p]; setGDraft({ ...g, metas_productos_ces: c }); }}><X size={13} /></button>
                </div>
              ))}
            </div>
            <Button variant="subtle" size="sm" icon={Plus} className="mt-3" onClick={addProd}>Agregar producto</Button>
          </div>
        </div>
      </Panel>
    </div>
  );
}

// ---------------- Grupos y productos
function Grupos({ cfg, sid, onSaved }) {
  const [groups, setGroups] = useState(() => cloneGroups(cfg));
  const [nuevoGrupo, setNuevoGrupo] = useState("");
  useEffect(() => setGroups(cloneGroups(cfg)), [cfg]);

  function cloneGroups(c) {
    const kw = c.parametros?.product_groups_keywords || {};
    const order = c.parametros?.groups_order?.length ? c.parametros.groups_order : Object.keys(kw);
    return order.filter((g) => kw[g]).map((g) => ({ nombre: g, items: [...(kw[g] || [])] }));
  }
  const setItems = (gi, items) => setGroups(groups.map((g, i) => (i === gi ? { ...g, items } : g)));

  async function save() {
    const product_groups_keywords = {};
    const groups_order = [];
    groups.forEach((g) => {
      const name = g.nombre.trim().toUpperCase();
      if (!name) return;
      product_groups_keywords[name] = g.items.map((s) => s.trim()).filter(Boolean);
      groups_order.push(name);
    });
    onSaved(await updateSucursal(sid, { parametros: { ...cfg.parametros, product_groups_keywords, groups_order } }));
  }

  return (
    <Panel>
      <PanelHeader icon={Layers} title="Grupos comerciales y sus productos"
        sub="Cada grupo lista los productos/palabras clave que lo identifican en la Nota. Editables, se pueden agregar o quitar."
        right={<Button icon={Save} onClick={save}>Guardar grupos</Button>} />
      <div className="p-5 space-y-4">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {groups.map((g, gi) => (
            <div key={gi} className="rounded-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center gap-2 bg-slate-50 px-3 py-2 border-b border-slate-100">
                <Layers size={14} className="text-brand-600 shrink-0" />
                <input className="input input-sm font-semibold flex-1" value={g.nombre}
                  onChange={(e) => setGroups(groups.map((x, i) => (i === gi ? { ...x, nombre: e.target.value } : x)))} />
                <Badge tone="slate">{g.items.length}</Badge>
                <IconButton variant="danger" icon={Trash2} size={13} title="Eliminar grupo"
                  onClick={() => { if (confirm(`¿Eliminar el grupo ${g.nombre}?`)) setGroups(groups.filter((_, i) => i !== gi)); }} />
              </div>
              <div className="p-3">
                <ChipsEditor items={g.items} onChange={(items) => setItems(gi, items)} />
              </div>
            </div>
          ))}
        </div>
        <div className="flex items-end gap-2 border-t border-slate-100 pt-4">
          <input className="input w-56" placeholder="Nuevo grupo (p. ej. BEBIDAS)" value={nuevoGrupo} onChange={(e) => setNuevoGrupo(e.target.value.toUpperCase())} />
          <Button variant="subtle" icon={Plus} onClick={() => { if (nuevoGrupo.trim()) { setGroups([...groups, { nombre: nuevoGrupo.trim(), items: [] }]); setNuevoGrupo(""); } }}>Agregar grupo</Button>
        </div>
      </div>
    </Panel>
  );
}

function ChipsEditor({ items, onChange }) {
  const [val, setVal] = useState("");
  function add() {
    const v = val.trim().toUpperCase();
    if (v && !items.includes(v)) onChange([...items, v]);
    setVal("");
  }
  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {items.map((it, i) => (
          <span key={i} className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-md bg-slate-100 text-slate-700 text-xs">
            {it}
            <button className="text-slate-400 hover:text-red-500" onClick={() => onChange(items.filter((_, j) => j !== i))}><X size={12} /></button>
          </span>
        ))}
        {!items.length && <span className="text-xs text-slate-400">Sin productos aún.</span>}
      </div>
      <div className="flex gap-2">
        <input className="input input-sm flex-1" placeholder="Agregar producto…" value={val}
          onChange={(e) => setVal(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())} />
        <Button size="sm" variant="subtle" icon={Plus} onClick={add}>Añadir</Button>
      </div>
    </div>
  );
}

// ---------------- Parámetros
function Parametros({ cfg, sid, onSaved }) {
  const [p, setP] = useState(cfg.parametros);
  useEffect(() => setP(cfg.parametros), [cfg]);
  const setSize = (obj, k, v) => setP({ ...p, [obj]: { ...p[obj], [k]: Number(v) } });

  async function save() {
    onSaved(await updateSucursal(sid, { parametros: {
      ...p,
      comision_gestor_pct: Number(p.comision_gestor_pct), comision_supervisor_pct: Number(p.comision_supervisor_pct),
      descuento_sin_pedido: Number(p.descuento_sin_pedido),
      size_mult: Object.fromEntries(Object.entries(p.size_mult).map(([k, v]) => [k, Number(v)])),
      units_per_pallet: Object.fromEntries(Object.entries(p.units_per_pallet).map(([k, v]) => [k, Number(v)])),
      curva_venta: Object.fromEntries(Object.entries(p.curva_venta).map(([k, v]) => [k, Number(v)])),
      frecuencia: Object.fromEntries(Object.entries(p.frecuencia).map(([k, v]) => [k, Number(v)])),
    } }));
  }
  return (
    <Panel>
      <PanelHeader icon={SlidersHorizontal} title="Parámetros de cálculo"
        right={<Button icon={Save} onClick={save}>Guardar parámetros</Button>} />
      <div className="p-5 space-y-5">
        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-brand-600 w-4 h-4" checked={!!p.trabaja_sabado} onChange={(e) => setP({ ...p, trabaja_sabado: e.target.checked })} /> ¿Se trabaja sábado?</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-brand-600 w-4 h-4" checked={!!p.trabaja_domingo} onChange={(e) => setP({ ...p, trabaja_domingo: e.target.checked })} /> ¿Se trabaja domingo?</label>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Comisión gestor (fracción, ej 0.01 = 1%)" type="number" value={p.comision_gestor_pct} onChange={(e) => setP({ ...p, comision_gestor_pct: e.target.value })} />
          <Field label="Comisión supervisor (fracción, ej 0.10 = 10%)" type="number" value={p.comision_supervisor_pct} onChange={(e) => setP({ ...p, comision_supervisor_pct: e.target.value })} />
          <Field label="Descuento por venta SIN pedido ($)" hint="Nota con V- pero sin P-. Se resta de la comisión del gestor." type="number" value={p.descuento_sin_pedido ?? 0} onChange={(e) => setP({ ...p, descuento_sin_pedido: e.target.value })} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <MiniTable title="Hectolitros por tamaño (×)" obj={p.size_mult} onChange={(k, v) => setSize("size_mult", k, v)} step="0.01" />
          <MiniTable title="Unidades por pallet" obj={p.units_per_pallet} onChange={(k, v) => setSize("units_per_pallet", k, v)} />
          <MiniTable title="Curva de venta semanal (S1-S5)" obj={p.curva_venta} onChange={(k, v) => setSize("curva_venta", k, v)} />
          <MiniTable title="Frecuencia semanal (S1-S5)" obj={p.frecuencia} onChange={(k, v) => setSize("frecuencia", k, v)} />
        </div>
      </div>
    </Panel>
  );
}

function MiniTable({ title, obj, onChange, step }) {
  return (
    <div className="rounded-xl border border-slate-200 p-3">
      <h4 className="font-semibold text-sm mb-2 text-slate-700">{title}</h4>
      <div className="flex flex-wrap gap-2">
        {Object.entries(obj || {}).map(([k, v]) => (
          <label key={k} className="text-xs">
            <span className="block text-slate-500 mb-0.5">{k}</span>
            <input className="input input-sm w-20 num" type="number" step={step} value={v} onChange={(e) => onChange(k, e.target.value)} />
          </label>
        ))}
      </div>
    </div>
  );
}

// ---------------- Sucursales (admin)
function Sucursales({ sucursales, onChanged, flash }) {
  const [nombre, setNombre] = useState("");
  const [seed, setSeed] = useState(false);
  return (
    <Panel>
      <PanelHeader icon={Building2} title="Sucursales" sub="Crea o elimina sucursales (cada una con sus datos aislados)" />
      <div className="p-5 space-y-4">
        <div className="flex flex-wrap gap-3 items-end">
          <Field label="Nueva sucursal" value={nombre} onChange={(e) => setNombre(e.target.value)} className="w-56" />
          <label className="flex items-center gap-2 text-sm pb-2"><input type="checkbox" className="accent-brand-600 w-4 h-4" checked={seed} onChange={(e) => setSeed(e.target.checked)} /> Sembrar gestores de ejemplo</label>
          <Button icon={Plus} onClick={async () => { if (!nombre.trim()) return; await createSucursal({ nombre, seed_gestores: seed }); setNombre(""); flash("ok", "Sucursal creada"); onChanged?.(); }}>Crear</Button>
        </div>
        <ul className="divide-y divide-slate-100 border-t border-slate-100">
          {sucursales.map((s) => (
            <li key={s.id} className="flex items-center justify-between py-2.5">
              <span className="text-sm">{s.nombre} <Badge tone="slate">{s.gestores} gestores</Badge></span>
              <IconButton variant="danger" icon={Trash2} size={14} onClick={async () => {
                if (confirm(`¿Eliminar sucursal ${s.nombre} y TODOS sus datos?`)) { await deleteSucursal(s.id); flash("ok", "Sucursal eliminada"); onChanged?.(); }
              }} />
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

// ---------------- Usuarios (admin)
const emptyUser = { username: "", nombre: "", password: "", role: "usuario", sucursales: [], gestor: "" };

// Selector del gestor: en vez de escribir la clave a mano, se eligen SOLO los
// gestores de la(s) sucursal(es) marcadas en esa misma fila, con buscador.
function GestorSelect({ sucursalIds = [], value, onCommit }) {
  const [opts, setOpts] = useState([]);
  const [loading, setLoading] = useState(false);
  const key = sucursalIds.join(",");

  useEffect(() => {
    const ids = sucursalIds.filter(Boolean);
    if (!ids.length) { setOpts([]); return; }
    let cancelado = false;
    setLoading(true);
    Promise.all(ids.map((id) => getSucursal(id).catch(() => null)))
      .then((cfgs) => {
        if (cancelado) return;
        const vistos = new Map();
        cfgs.filter(Boolean).forEach((cfg) => {
          Object.entries(cfg.gestores || {}).forEach(([clave, g]) => {
            if (g?.activo === false || vistos.has(clave)) return;
            vistos.set(clave, { value: clave, label: g?.nombre ? `${clave} — ${g.nombre}` : clave });
          });
        });
        setOpts([...vistos.values()]);
      })
      .finally(() => { if (!cancelado) setLoading(false); });
    return () => { cancelado = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!sucursalIds.length) {
    return <span className="text-xs text-slate-400">Elige la sucursal primero</span>;
  }
  return (
    <SearchSelect
      width="w-40"
      value={value || ""}
      options={opts}
      onChange={onCommit}
      placeholder={loading ? "Cargando…" : "Clave del gestor"}
      searchPlaceholder="Buscar gestor…"
      emptyText="Esta sucursal no tiene gestores"
    />
  );
}

// Celda de alcance según el rol (todas / sucursales / gestor).
function ScopeCell({ role, sucursales, value, gestor, onSucursales, onGestor }) {
  if (ALL_ROLES.includes(role)) return <span className="text-xs text-slate-400">todas</span>;
  return (
    <div className="space-y-1">
      <MultiSelect value={value} options={sucOpts(sucursales)} onChange={onSucursales} placeholder="Elegir sucursal" width="w-40" />
      {role === "gestor" && <GestorSelect sucursalIds={value || []} value={gestor} onCommit={onGestor} />}
    </div>
  );
}

function Usuarios({ sucursales, flash }) {
  const [users, setUsers] = useState([]);
  const [nuevo, setNuevo] = useState(emptyUser);
  const reload = () => listUsers().then(setUsers).catch(() => {});
  useEffect(() => { reload(); }, []);

  async function crear() {
    if (!nuevo.username.trim() || !nuevo.password) return flash("err", "Usuario y contraseña requeridos");
    if (nuevo.role === "gestor" && !nuevo.gestor.trim()) return flash("err", "El rol gestor requiere la clave del gestor");
    try { await createUser(nuevo); setNuevo(emptyUser); reload(); flash("ok", "Usuario creado"); }
    catch (e) { flash("err", e?.response?.data?.detail || "Error"); }
  }
  const td = "px-2 py-1.5 border-b border-slate-100 align-top";
  return (
    <Panel>
      <PanelHeader icon={UserPlus} title="Usuarios" sub="admin ve todas las sucursales · user solo las asignadas" />
      <div className="overflow-x-auto scroll-thin">
        <table className="tbl">
          <thead><tr>{["Usuario", "Nombre", "Rol", "Sucursales", "Contraseña", ""].map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>
            {users.map((u) => <UserRow key={u.username} u={u} sucursales={sucursales} reload={reload} flash={flash} />)}
            <tr className="bg-brand-50/50">
              <td className={td}><input className="input input-sm w-28" placeholder="usuario" value={nuevo.username} onChange={(e) => setNuevo({ ...nuevo, username: e.target.value })} /></td>
              <td className={td}><input className="input input-sm w-32" placeholder="Nombre" value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} /></td>
              <td className={td}><Select width="w-52" value={nuevo.role} onChange={(v) => setNuevo({ ...nuevo, role: v })} options={ROLE_OPTS} /></td>
              <td className={td}><ScopeCell role={nuevo.role} sucursales={sucursales} value={nuevo.sucursales} gestor={nuevo.gestor}
                onSucursales={(v) => setNuevo({ ...nuevo, sucursales: v })} onGestor={(g) => setNuevo({ ...nuevo, gestor: g })} /></td>
              <td className={td}><input className="input input-sm w-32" type="password" placeholder="contraseña" value={nuevo.password} onChange={(e) => setNuevo({ ...nuevo, password: e.target.value })} /></td>
              <td className={td}><Button size="sm" icon={Plus} onClick={crear}>Crear</Button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function UserRow({ u, sucursales, reload, flash }) {
  const [pw, setPw] = useState("");
  const td = "px-2 py-1.5 border-b border-slate-100";
  return (
    <tr className="hover:bg-slate-50">
      <td className={cn(td, "font-medium")}>{u.username}</td>
      <td className={td}>{u.nombre}</td>
      <td className={cn(td, "align-top")}>
        <Select width="w-52" value={u.role} onChange={async (v) => { await updateUser(u.username, { role: v }); reload(); }} options={ROLE_OPTS} />
      </td>
      <td className={cn(td, "align-top")}>
        <ScopeCell role={u.role} sucursales={sucursales} value={u.sucursales} gestor={u.gestor}
          onSucursales={async (v) => { await updateUser(u.username, { sucursales: v }); reload(); }}
          onGestor={async (g) => { await updateUser(u.username, { gestor: g }); reload(); }} />
      </td>
      <td className={cn(td, "whitespace-nowrap")}>
        <div className="flex gap-1 items-center">
          <input className="input input-sm w-28" type="password" placeholder="nueva clave" value={pw} onChange={(e) => setPw(e.target.value)} />
          <IconButton variant="subtle" icon={Save} size={12} title="Cambiar clave" onClick={async () => { if (pw) { await updateUser(u.username, { password: pw }); setPw(""); flash("ok", "Clave cambiada"); } }} />
        </div>
      </td>
      <td className={td}>
        <IconButton variant="danger" icon={Trash2} size={12} title="Eliminar" onClick={async () => { if (confirm(`¿Eliminar usuario ${u.username}?`)) { try { await deleteUser(u.username); reload(); } catch (e) { flash("err", e?.response?.data?.detail || "Error"); } } }} />
      </td>
    </tr>
  );
}

