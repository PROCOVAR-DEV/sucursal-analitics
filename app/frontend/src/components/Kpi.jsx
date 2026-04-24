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

export function formatNumber(n, digits = 2) {
  if (n === null || n === undefined || isNaN(n)) return "–";
  return Number(n).toLocaleString("es-CO", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatInt(n) {
  if (n === null || n === undefined || isNaN(n)) return "–";
  return Number(n).toLocaleString("es-CO");
}

export function formatMoney(n) {
  return `$ ${formatNumber(n, 2)}`;
}
