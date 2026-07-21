export function Kpi({ label, value, hint, tone = "brand" }) {
  const toneCls = {
    brand: "text-brand-600",
    green: "text-emerald-600",
    red: "text-red-600",
    amber: "text-amber-600",
    slate: "text-slate-600",
  }[tone];
  return (
    <div className="kpi-card">
      <span className="kpi-label">{label}</span>
      <span className={`kpi-value ${toneCls}`}>{value}</span>
      {hint && <span className="text-xs text-slate-500">{hint}</span>}
    </div>
  );
}

// NÚMEROS SIN DECIMALES en toda la app: se redondea a entero (más fácil de leer).
// El 2º argumento se ignora a propósito — antes se pasaban decimales; ahora todo es entero.
export function formatNumber(n /*, digits */) {
  if (n === null || n === undefined || isNaN(n)) return "–";
  return Number(n).toLocaleString("es-CO", { maximumFractionDigits: 0 });
}

export function formatInt(n) {
  if (n === null || n === undefined || isNaN(n)) return "–";
  return Number(n).toLocaleString("es-CO", { maximumFractionDigits: 0 });
}

export function formatMoney(n) {
  return `$ ${formatNumber(n)}`;
}
