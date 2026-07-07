import { Calculator, Check, Copy, Download, Info, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getSucursal, getSucursalId, updateSucursal } from "../api.js";
import { formatNumber } from "./Kpi.jsx";
import { Button, IconButton, Panel, PanelHeader, Segmented, Select, Toast, cn } from "./ui.jsx";

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const pkeyOf = (y, m) => `${y}-${String(m).padStart(2, "0")}`;

// Desglose ESTÁNDAR por formato (HL) — plan de Camagüey.
const STD_FMT = { "PARRANDA-1500": 91.08, "PARRANDA-500": 20.16, "PARRANDA-330": 39.68, "MALTA-1500": 36.8775, "MALTA-330": 44.64 };
const CAMAGUEY_PLAN = {
  "ALEXANDER": { total: 235, formato: { ...STD_FMT } },
  "DEYANIRA": { total: 321, formato: { "PARRANDA-1500": 118.8, "PARRANDA-500": 27.216, "PARRANDA-330": 71.424, "MALTA-1500": 36.8775, "MALTA-330": 66.464 } },
  "GEORLIS": { total: 235, formato: { ...STD_FMT } },
  "JEAN MICHEL": { total: 235, formato: { ...STD_FMT } },
  "ERNESTO": { total: 224, formato: { ...STD_FMT, "PARRANDA-500": 10.08 } },
  "ANDY": { total: 224, formato: { ...STD_FMT, "PARRANDA-500": 10.08 } },
  "MAYLEN": { total: 235, formato: { ...STD_FMT } },
};

let _uid = 0;
const codeOf = (r) => `${r.producto}-${r.size}`;
function rowsFromFormato(formato, params) {
  return Object.entries(formato).map(([code, hl]) => {
    const idx = code.lastIndexOf("-");
    const size = idx > 0 ? code.slice(idx + 1) : "330";
    return { id: ++_uid, producto: idx > 0 ? code.slice(0, idx) : code, size, pallets: palletsFromHL(hl, size, params) };
  });
}
const seedRows = (params) => rowsFromFormato(STD_FMT, params || {});

export default function CalculadoraView({ cfg: cfgProp, sid: sidProp, onSaved }) {
  const [cfgLocal, setCfgLocal] = useState(cfgProp || null);
  const cfg = cfgProp || cfgLocal;
  const setCfg = (c) => { setCfgLocal(c); onSaved?.(c); };  // propaga a AdminPanel
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  const [mode, setMode] = useState("rapido");
  const [plans, setPlans] = useState({});
  const [quick, setQuick] = useState({});
  const [quickCcc, setQuickCcc] = useState({});
  const [incluidos, setIncluidos] = useState({});
  const [sel, setSel] = useState(null);
  const [savingAll, setSavingAll] = useState(false);
  const now = new Date();
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() + 1 });
  const [dias, setDias] = useState(23);

  const sid = sidProp || getSucursalId();
  const pkey = pkeyOf(ym.y, ym.m);

  const params = cfg?.parametros || {};
  const sizeMult = params.size_mult || { 330: 0.02, 500: 0.03, 1500: 0.09 };
  const unitsPP = params.units_per_pallet || { 330: 496, 500: 336, 1500: 110 };
  const sizes = params.sizes || ["330", "500", "1500"];
  const productos = useMemo(() => [...new Set(["PARRANDA", "MALTA", ...Object.keys(params.product_groups_keywords || {})])], [params]);
  const gestores = useMemo(() => Object.entries(cfg?.gestores || {}).filter(([, g]) => g.activo !== false), [cfg]);

  // Construye el estado para el mes seleccionado (metas_mensuales[pkey].gestores).
  function buildForMonth(c, key) {
    const gs = Object.entries(c.gestores || {}).filter(([, g]) => g.activo !== false);
    const prm = c.parametros || {};
    const monthConf = !!c.metas_mensuales?.[key];
    const monthG = c.metas_mensuales?.[key]?.gestores || {};
    const initPlans = {}, initQuick = {}, initCcc = {}, initIncl = {};
    gs.forEach(([k, gv]) => {
      initIncl[k] = monthConf ? (k in monthG) : true;
      const mg = monthG[k] || {};
      const mf = mg.metas_formato || {};
      const mfNonZero = Object.values(mf).some((v) => Number(v) > 0);
      const plan = CAMAGUEY_PLAN[k];
      if (mfNonZero) initPlans[k] = rowsFromFormato(mf, prm);
      else if (plan) initPlans[k] = rowsFromFormato(plan.formato, prm);
      else initPlans[k] = seedRows(prm);
      initQuick[k] = mg.cuota_hl != null ? Number(mg.cuota_hl) : (plan ? plan.total : 0);
      initCcc[k] = mg.cuota_ccc != null ? Number(mg.cuota_ccc) : Number(gv.cuota_ccc ?? 0);
    });
    return { gs, initPlans, initQuick, initCcc, initIncl };
  }

  useEffect(() => {
    if (cfgProp) { setCfgLocal(cfgProp); return; }   // usa la config de AdminPanel
    if (!sid) return;
    getSucursal(sid).then((c) => setCfgLocal(c)).catch((e) => setErr(e?.response?.data?.detail || e.message));
  }, [sid, cfgProp]);

  useEffect(() => {
    if (!cfg) return;
    const { gs, initPlans, initQuick, initCcc, initIncl } = buildForMonth(cfg, pkey);
    setPlans(initPlans);
    setQuick(initQuick);
    setQuickCcc(initCcc);
    setIncluidos(initIncl);
    setSel((cur) => cur || gs[0]?.[0] || null);
  }, [cfg, pkey]);

  function cargarPlanJulio() {
    if (!cfg) return;
    const prm = cfg.parametros || {};
    const p = {}, q = {};
    gestores.forEach(([k]) => {
      const plan = CAMAGUEY_PLAN[k];
      p[k] = plan ? rowsFromFormato(plan.formato, prm) : seedRows(prm);
      q[k] = plan ? plan.total : 0;
    });
    setPlans(p); setQuick(q);
    flash("ok", `Plan de referencia cargado en ${MESES[ym.m - 1]} ${ym.y}. Revisa y pulsa “Guardar”.`);
  }

  function calc(row) {
    const upp = Number(unitsPP[row.size] || 0);
    const mult = Number(sizeMult[row.size] || 0);
    const pallets = Number(row.pallets) || 0;
    const blisters = pallets * upp;
    return { upp, mult, pallets, blisters, hl: blisters * mult };
  }
  const vendorRows = (k) => plans[k] || [];
  const detalleHL = (k) => vendorRows(k).reduce((s, r) => s + calc(r).hl, 0);
  const vendorHL = (k) => (mode === "rapido" ? (Number(quick[k]) || 0) : detalleHL(k));
  function vendorFormato(k) { const out = {}; vendorRows(k).forEach((r) => { out[codeOf(r)] = round2(calc(r).hl); }); return out; }
  const enMes = (k) => incluidos[k] !== false;
  const grandTotal = gestores.reduce((s, [k]) => s + (enMes(k) ? vendorHL(k) : 0), 0);
  const grandTotalCcc = gestores.reduce((s, [k]) => s + (enMes(k) ? (Number(quickCcc[k]) || 0) : 0), 0);

  function flash(t, text) { setMsg({ t, text }); setTimeout(() => setMsg(null), 3500); }
  function setRows(k, up) { setPlans((p) => ({ ...p, [k]: typeof up === "function" ? up(p[k] || []) : up })); }
  const update = (k, id, pallets) => setRows(k, (rs) => rs.map((r) => (r.id === id ? { ...r, pallets } : r)));
  const setField = (k, id, f, v) => setRows(k, (rs) => rs.map((r) => (r.id === id ? { ...r, [f]: v } : r)));
  const addRow = (k) => setRows(k, (rs) => [...rs, { id: ++_uid, producto: productos[0] || "PARRANDA", size: sizes[0], pallets: 0 }]);
  const removeRow = (k, id) => setRows(k, (rs) => rs.filter((r) => r.id !== id));
  const resetVendor = (k) => setRows(k, seedRows(cfg?.parametros));
  function copyToAll(k) {
    const src = vendorRows(k);
    setPlans((p) => { const n = { ...p }; gestores.forEach(([g]) => { if (g !== k) n[g] = src.map((r) => ({ id: ++_uid, producto: r.producto, size: r.size, pallets: r.pallets })); }); return n; });
    setQuick((q) => { const n = { ...q }; const hl = detalleHL(k); gestores.forEach(([g]) => { if (g !== k) n[g] = round2(hl); }); return n; });
    flash("ok", `Plan de ${k} aplicado a todos (sin guardar).`);
  }

  async function saveVendor(k) {
    try {
      // Siempre guardamos el desglose por formato (lo usan Vendedores y el reporte).
      const g = { cuota_hl: round2(vendorHL(k)), cuota_ccc: Number(quickCcc[k]) || 0, metas_formato: vendorFormato(k) };
      const fresh = await updateSucursal(sid, { metas_mensuales: { [pkey]: { gestores: { [k]: g } } } });
      setCfg(fresh);
      flash("ok", `Meta de ${k} guardada en ${MESES[ym.m - 1]} ${ym.y}: ${formatNumber(vendorHL(k), 2)} HL.`);
    } catch (e) { flash("err", e?.response?.data?.detail || e.message); }
  }
  async function saveAll() {
    setSavingAll(true);
    try {
      const gestoresPayload = {};
      gestores.forEach(([k]) => {
        if (!enMes(k)) return;   // no incluir en el roster del mes
        gestoresPayload[k] = { cuota_hl: round2(vendorHL(k)), cuota_ccc: Number(quickCcc[k]) || 0, metas_formato: vendorFormato(k) };
      });
      // Reemplaza el roster del mes por los vendedores incluidos.
      const fresh = await updateSucursal(sid, { metas_mensuales: { [pkey]: null } })
        .then(() => updateSucursal(sid, { metas_mensuales: { [pkey]: { gestores: gestoresPayload, meta_hectolitros_total: round2(grandTotal), meta_ccc_total: round2(grandTotalCcc) } } }));
      setCfg(fresh);
      flash("ok", `Metas de ${MESES[ym.m - 1]} ${ym.y} guardadas para ${gestores.length} vendedores. Total: ${formatNumber(grandTotal, 2)} HL.`);
    } catch (e) { flash("err", e?.response?.data?.detail || e.message); }
    finally { setSavingAll(false); }
  }
  async function clearMonth() {
    if (!confirm(`¿Borrar TODAS las metas de ${MESES[ym.m - 1]} ${ym.y}? Ese mes quedará sin meta configurada.`)) return;
    try {
      const fresh = await updateSucursal(sid, { metas_mensuales: { [pkey]: null } });
      setCfg(fresh);
      flash("ok", `Metas de ${MESES[ym.m - 1]} ${ym.y} borradas.`);
    } catch (e) { flash("err", e?.response?.data?.detail || e.message); }
  }

  if (err) return <div className="p-6 text-red-600">{err}</div>;
  if (!cfg) return <div className="p-6 text-slate-400 animate-pulse">Cargando…</div>;
  const rows = vendorRows(sel);
  const monthConfigured = !!cfg.metas_mensuales?.[pkey];
  const yearOpts = [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => ({ value: String(y), label: String(y) }));

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex justify-between items-start gap-4 flex-wrap">
        <div>
          <h2 className="section-title flex items-center gap-2"><Calculator className="text-brand-600" size={22} /> Calculadora de Metas (HL)</h2>
          <p className="text-sm text-slate-500">Las metas son <b>por mes</b>: elige el mes y define la meta de cada vendedor. Cada mes es independiente.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <Select width="w-32" value={String(ym.m)} onChange={(v) => setYm({ ...ym, m: Number(v) })} options={MESES.map((n, i) => ({ value: String(i + 1), label: n }))} align="right" />
          <Select width="w-24" value={String(ym.y)} onChange={(v) => setYm({ ...ym, y: Number(v) })} options={yearOpts} align="right" />
          <span className="text-sm text-slate-600 ml-1">Días</span>
          <input type="number" className="input w-16 num" value={dias} onChange={(e) => setDias(Number(e.target.value) || 0)} />
          <Button variant="outline" icon={Download} onClick={cargarPlanJulio}>Cargar plan ref.</Button>
          {monthConfigured && <Button variant="danger" icon={Trash2} onClick={clearMonth}>Borrar mes</Button>}
          <Button icon={Save} onClick={saveAll} disabled={savingAll}>{savingAll ? "Guardando…" : "Guardar metas del mes"}</Button>
        </div>
      </div>

      <Toast msg={msg} onClose={() => setMsg(null)} />

      <div className="flex items-center justify-between flex-wrap gap-3">
        <Segmented value={mode} onChange={setMode} options={[{ value: "rapido", label: "Rápido (total HL)" }, { value: "detalle", label: "Detallado (por SKU)" }]} />
        <div className={cn("flex items-center gap-2 text-xs rounded-lg px-3 py-1.5 border", monthConfigured ? "bg-emerald-50 border-emerald-100 text-emerald-700" : "bg-amber-50 border-amber-100 text-amber-700")}>
          <Info size={14} className="shrink-0" />
          {monthConfigured ? `${MESES[ym.m - 1]} ${ym.y} tiene metas guardadas.` : `${MESES[ym.m - 1]} ${ym.y} aún sin metas: llena y guarda.`}
        </div>
      </div>

      <Panel>
        <PanelHeader icon={Calculator} title={`Metas por vendedor · ${MESES[ym.m - 1]} ${ym.y}`}
          right={<span className="text-sm text-slate-500">Total: <b className="text-brand-700">{formatNumber(grandTotal, 2)} HL</b></span>} />
        <div className="overflow-x-auto scroll-thin">
          <table className="tbl">
            <thead><tr><th className="!text-center">En el mes</th><th>Vendedor</th><th className="!text-right">Meta HL</th><th className="!text-right">Meta CCC</th><th className="!text-right">HL / Día</th><th className="!text-center">Acción</th></tr></thead>
            <tbody>
              {gestores.map(([k, g]) => {
                const hl = vendorHL(k);
                const on = incluidos[k] !== false;
                return (
                  <tr key={k} className={cn("hover:bg-slate-50 cursor-pointer", !on && "opacity-40", sel === k && "bg-brand-50/50")} onClick={() => setSel(k)}>
                    <td className="text-center"><input type="checkbox" className="accent-brand-600 w-4 h-4" checked={on} onClick={(e) => e.stopPropagation()} onChange={(e) => setIncluidos({ ...incluidos, [k]: e.target.checked })} title="¿Este vendedor existe este mes?" /></td>
                    <td className="font-medium">{k} <span className="text-slate-400 font-normal">· {g.nombre}</span></td>
                    <td className="text-right">
                      {mode === "rapido"
                        ? <input type="number" step="0.01" className="input input-sm w-24 num" disabled={!on} value={round2(quick[k] ?? 0)} onClick={(e) => e.stopPropagation()} onChange={(e) => setQuick({ ...quick, [k]: Number(e.target.value) || 0 })} />
                        : <span className="font-semibold text-slate-800 tabular-nums">{formatNumber(hl, 2)}</span>}
                    </td>
                    <td className="text-right"><input type="number" className="input input-sm w-20 num" disabled={!on} value={quickCcc[k] ?? 0} onClick={(e) => e.stopPropagation()} onChange={(e) => setQuickCcc({ ...quickCcc, [k]: Number(e.target.value) || 0 })} /></td>
                    <td className="text-right text-slate-500 tabular-nums">{formatNumber(dias ? hl / dias : 0, 3)}</td>
                    <td className="text-center"><Button size="sm" variant="subtle" icon={Check} onClick={(e) => { e.stopPropagation(); saveVendor(k); }}>Guardar</Button></td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="bg-slate-800 text-white font-semibold">
                <td></td>
                <td className="px-3 py-2.5">TOTAL SUCURSAL</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatNumber(grandTotal, 2)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatNumber(grandTotalCcc, 0)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatNumber(dias ? grandTotal / dias : 0, 3)}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Panel>

      {mode === "detalle" && sel && (
        <Panel>
          <PanelHeader icon={Calculator} title={`Plan por SKU — ${sel} · ${MESES[ym.m - 1]} ${ym.y}`}
            right={<div className="flex gap-2">
              <Button size="sm" variant="subtle" icon={Copy} onClick={() => copyToAll(sel)}>Aplicar a todos</Button>
              <Button size="sm" variant="subtle" icon={RotateCcw} onClick={() => resetVendor(sel)}>Reiniciar</Button>
            </div>} />
          <div className="overflow-x-auto scroll-thin">
            <table className="tbl">
              <thead><tr><th>Producto</th><th>Formato</th><th className="!text-right">Pallets</th><th className="!text-right">Blísters</th><th className="!text-right">Hectolitros</th><th></th></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const c = calc(r);
                  return (
                    <tr key={r.id} className="hover:bg-slate-50">
                      <td><select className="input input-sm w-40" value={r.producto} onChange={(e) => setField(sel, r.id, "producto", e.target.value)}>{productos.map((p) => <option key={p} value={p}>{p}</option>)}</select></td>
                      <td><select className="input input-sm w-24" value={r.size} onChange={(e) => setField(sel, r.id, "size", e.target.value)}>{sizes.map((s) => <option key={s} value={s}>{s} ml</option>)}</select></td>
                      <td className="text-right"><input type="number" step="0.01" className="input input-sm w-24 num font-semibold" value={num(c.pallets)} onChange={(e) => update(sel, r.id, Number(e.target.value) || 0)} /></td>
                      <td className="text-right"><input type="number" step="1" className="input input-sm w-24 num" value={num(c.blisters)} onChange={(e) => update(sel, r.id, c.upp ? (Number(e.target.value) || 0) / c.upp : 0)} /></td>
                      <td className="text-right"><input type="number" step="0.01" className="input input-sm w-24 num text-brand-700 font-semibold" value={num(c.hl)} onChange={(e) => update(sel, r.id, c.upp && c.mult ? (Number(e.target.value) || 0) / (c.upp * c.mult) : 0)} /></td>
                      <td className="text-center"><IconButton variant="ghost" icon={Trash2} size={14} className="text-slate-300 hover:text-red-500" onClick={() => removeRow(sel, r.id)} /></td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="bg-slate-100 font-semibold">
                  <td className="px-3 py-2" colSpan={2}>TOTAL {sel}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatNumber(rows.reduce((s, r) => s + calc(r).pallets, 0), 2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatNumber(rows.reduce((s, r) => s + calc(r).blisters, 0), 0)}</td>
                  <td className="px-3 py-2 text-right text-brand-700 tabular-nums">{formatNumber(detalleHL(sel), 2)}</td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </div>
          <div className="flex items-center justify-between flex-wrap gap-2 px-4 py-3 border-t border-slate-100">
            <Button variant="subtle" size="sm" icon={Plus} onClick={() => addRow(sel)}>Agregar SKU</Button>
            <p className="text-xs text-slate-400">Factores: {sizes.map((s) => `${s}ml → ${unitsPP[s]} u/pallet · ${sizeMult[s]} HL/u`).join("  |  ")}</p>
          </div>
        </Panel>
      )}
    </div>
  );
}

function palletsFromHL(hl, size, params) {
  const upp = Number((params.units_per_pallet || {})[size] || 0);
  const mult = Number((params.size_mult || {})[size] || 0);
  const denom = upp * mult;
  return denom ? (Number(hl) || 0) / denom : 0;
}
const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
const num = (n) => Math.round((Number(n) || 0) * 10000) / 10000;
