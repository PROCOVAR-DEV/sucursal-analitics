import { RotateCcw, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getSettings, resetSettings, saveSettings } from "../api.js";

const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function periodKey(y, m) {
  return `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}`;
}

function defaultPeriod() {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

export default function SettingsPanel() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [{ year, month }, setPeriod] = useState(defaultPeriod);

  useEffect(() => { getSettings().then(setCfg); }, []);

  if (!cfg) return <div className="p-6">Cargando configuración…</div>;

  const pkey = periodKey(year, month);
  const monthly = (cfg.metas_mensuales && cfg.metas_mensuales[pkey]) || {};
  const monthlyHasHL = Object.prototype.hasOwnProperty.call(monthly, "meta_hectolitros_total");
  const monthlyHasDinero = Object.prototype.hasOwnProperty.call(monthly, "meta_dinero_total");
  const effectiveHL = monthlyHasHL ? monthly.meta_hectolitros_total : cfg.meta_hectolitros_total;
  const effectiveDinero = monthlyHasDinero ? monthly.meta_dinero_total : cfg.meta_dinero_total;
  const effectiveProductos = { ...(cfg.metas_productos_ces || {}), ...(monthly.metas_productos_ces || {}) };

  const years = useMemo(() => {
    const set = new Set([year, new Date().getFullYear()]);
    Object.keys(cfg.metas_mensuales || {}).forEach((k) => {
      const y = parseInt(k.slice(0, 4), 10);
      if (!Number.isNaN(y)) set.add(y);
    });
    return [...set].sort((a, b) => b - a);
  }, [cfg.metas_mensuales, year]);

  function setField(path, value) {
    setCfg((c) => {
      const copy = structuredClone(c);
      const keys = path.split(".");
      let obj = copy;
      for (let i = 0; i < keys.length - 1; i++) {
        if (obj[keys[i]] === undefined || obj[keys[i]] === null) obj[keys[i]] = {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
      return copy;
    });
  }

  function setMonthlyField(subpath, value) {
    setField(`metas_mensuales.${pkey}.${subpath}`, value);
  }

  function clearMonthlyOverride() {
    if (!confirm(`¿Eliminar las metas específicas de ${MONTHS[month - 1]} ${year}? Se volverá a usar la meta global por defecto.`)) return;
    setCfg((c) => {
      const copy = structuredClone(c);
      if (copy.metas_mensuales) delete copy.metas_mensuales[pkey];
      return copy;
    });
  }

  async function handleSave() {
    setSaving(true);
    setMsg(null);
    try {
      // normalizar: el backend espera metas_mensuales[key]=null para borrar
      const payload = structuredClone(cfg);
      if (payload.metas_mensuales) {
        const stored = (cfg.metas_mensuales || {});
        const original = Object.keys(stored);
        const kept = Object.keys(payload.metas_mensuales);
        original.forEach((k) => {
          if (!kept.includes(k)) payload.metas_mensuales[k] = null;
        });
      }
      const saved = await saveSettings(payload);
      setCfg(saved);
      setMsg({ type: "ok", text: "Configuración guardada." });
    } catch (e) {
      setMsg({ type: "err", text: e?.response?.data?.detail || e.message });
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    if (!confirm("¿Restaurar TODOS los valores por defecto? Se perderán las metas mensuales.")) return;
    const def = await resetSettings();
    setCfg(def);
    setMsg({ type: "ok", text: "Valores por defecto restaurados." });
  }

  const productosGlobal = Object.entries(cfg.metas_productos_ces || {});
  const gestores = Object.entries(cfg.gestores || {});

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold">Configuración de metas</h2>
          <p className="text-sm text-slate-500">
            Las metas de hectolitros y productos CES pueden variar cada mes. Abajo eliges el mes y editas sus valores.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn bg-slate-100 hover:bg-slate-200" onClick={handleReset}>
            <RotateCcw size={16} /> Restaurar
          </button>
          <button className="btn-primary" onClick={handleSave} disabled={saving}>
            <Save size={16} /> {saving ? "Guardando…" : "Guardar"}
          </button>
        </div>
      </div>

      {msg && (
        <div className={`p-3 rounded-lg text-sm border ${msg.type === "ok" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200"}`}>
          {msg.text}
        </div>
      )}

      {/* -------- Metas por mes/año -------- */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h3 className="font-semibold">Metas del mes</h3>
          <div className="flex items-center gap-2 text-sm">
            <label className="text-slate-600">Mes:</label>
            <select className="input" value={month} onChange={(e) => setPeriod({ year, month: Number(e.target.value) })}>
              {MONTHS.map((n, i) => (
                <option key={i} value={i + 1}>{n}</option>
              ))}
            </select>
            <label className="text-slate-600">Año:</label>
            <select className="input" value={year} onChange={(e) => setPeriod({ year: Number(e.target.value), month })}>
              {years.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
              <option value={year + 1}>{year + 1}</option>
            </select>
            {(monthlyHasHL || monthlyHasDinero || monthly.metas_productos_ces) && (
              <button className="btn bg-red-50 hover:bg-red-100 text-red-700" onClick={clearMonthlyOverride} title="Borrar override del mes">
                <Trash2 size={14} /> Borrar mes
              </button>
            )}
          </div>
        </div>

        <p className="text-xs text-slate-500">
          {monthlyHasHL || monthlyHasDinero || monthly.metas_productos_ces
            ? `Editando valores específicos para ${MONTHS[month - 1]} ${year}.`
            : `No hay overrides para ${MONTHS[month - 1]} ${year}. Modifica abajo para crear uno, o deja así para usar el global.`}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field
            label={`Meta Hectolitros · ${MONTHS[month - 1]} ${year}`}
            hint={monthlyHasHL ? "override del mes" : `global por defecto: ${cfg.meta_hectolitros_total}`}
            type="number"
            value={effectiveHL}
            onChange={(v) => setMonthlyField("meta_hectolitros_total", Number(v))}
          />
          <Field
            label={`Meta Dinero ($) · ${MONTHS[month - 1]} ${year}`}
            hint={monthlyHasDinero ? "override del mes" : `global por defecto: ${cfg.meta_dinero_total}`}
            type="number"
            value={effectiveDinero}
            onChange={(v) => setMonthlyField("meta_dinero_total", Number(v))}
          />
        </div>

        <div>
          <h4 className="font-semibold text-sm mb-2">Metas de productos CES · {MONTHS[month - 1]} {year}</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {Object.entries(effectiveProductos).map(([prod, val]) => {
              const overridden = monthly.metas_productos_ces && Object.prototype.hasOwnProperty.call(monthly.metas_productos_ces, prod);
              return (
                <Field
                  key={prod}
                  label={prod}
                  hint={overridden ? "override del mes" : `global: ${cfg.metas_productos_ces?.[prod] ?? 0}`}
                  type="number"
                  value={val}
                  onChange={(v) => setMonthlyField(`metas_productos_ces.${prod}`, Number(v))}
                />
              );
            })}
          </div>
        </div>
      </div>

      {/* -------- Metas globales por defecto -------- */}
      <div className="card space-y-4">
        <h3 className="font-semibold">Valores globales por defecto</h3>
        <p className="text-xs text-slate-500">Se usan cuando un mes no tiene valores propios definidos arriba.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Field label="Meta Hectolitros (total)" type="number" value={cfg.meta_hectolitros_total}
            onChange={(v) => setField("meta_hectolitros_total", Number(v))} />
          <Field label="Meta Dinero (total $)" type="number" value={cfg.meta_dinero_total}
            onChange={(v) => setField("meta_dinero_total", Number(v))} />
          <div className="flex items-center gap-2 mt-6">
            <input id="sab" type="checkbox" checked={!!cfg.trabaja_sabado}
              onChange={(e) => setField("trabaja_sabado", e.target.checked)} />
            <label htmlFor="sab" className="text-sm">¿Se trabaja sábado? (afecta días laborales)</label>
          </div>
        </div>
        <div>
          <h4 className="font-semibold text-sm mb-2">Metas de productos CES (global)</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {productosGlobal.map(([prod, val]) => (
              <Field key={prod} label={prod} type="number" value={val}
                onChange={(v) => setField(`metas_productos_ces.${prod}`, Number(v))} />
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3">Gestores de venta</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">Clave</th>
                <th className="px-3 py-2 text-left">Nombre</th>
                <th className="px-3 py-2 text-left">Sector</th>
                <th className="px-3 py-2 text-right">Cuota HL</th>
                <th className="px-3 py-2 text-right">Cuota CCC</th>
              </tr>
            </thead>
            <tbody>
              {gestores.map(([key, g]) => (
                <tr key={key} className="border-t border-slate-100">
                  <td className="px-3 py-2 text-xs text-slate-500">{key}</td>
                  <td className="px-3 py-2">
                    <input className="input w-full" value={g.nombre || ""}
                      onChange={(e) => setField(`gestores.${key}.nombre`, e.target.value)} />
                  </td>
                  <td className="px-3 py-2">
                    <input className="input w-full" value={g.sector || ""}
                      onChange={(e) => setField(`gestores.${key}.sector`, e.target.value)} />
                  </td>
                  <td className="px-3 py-2 w-32">
                    <input className="input w-full text-right" type="number" value={g.cuota_hl ?? 0}
                      onChange={(e) => setField(`gestores.${key}.cuota_hl`, Number(e.target.value))} />
                  </td>
                  <td className="px-3 py-2 w-32">
                    <input className="input w-full text-right" type="number" value={g.cuota_ccc ?? 0}
                      onChange={(e) => setField(`gestores.${key}.cuota_ccc`, Number(e.target.value))} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", hint }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-slate-600 mb-1">{label}</span>
      <input className="input w-full" type={type} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
      {hint && <span className="block mt-1 text-[10px] text-slate-400">{hint}</span>}
    </label>
  );
}
