import { Download, FileSpreadsheet, Package, TrendingUp, Trophy, Users } from "lucide-react";
import { useState } from "react";
import { downloadExport } from "../api.js";

const MONTHS_ES = [
  "Enero","Febrero","Marzo","Abril","Mayo","Junio",
  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
];

function formatPeriod(p) {
  if (!p) return "Todo (global)";
  const [y, m] = p.split("-");
  return `${MONTHS_ES[parseInt(m, 10) - 1]} ${y}`;
}

const REPORTS = [
  {
    id: "ventas",
    title: "Parranda y Malta (HL)",
    icon: TrendingUp,
    color: "text-blue-600",
    bg: "bg-blue-50",
    border: "border-blue-100",
    desc: [
      "Una hoja por vendedor con sus transacciones de Malta y Parranda",
      "Desglose por tamaño: Malta/Parranda 330 / 500 / 1500 ml",
      "KPIs: hectolitros totales, cuota, % cumplimiento",
      "Tabla de conversión a blisters y pallets",
      "Hoja Supervisor con resumen de todos los gestores",
    ],
  },
  {
    id: "market",
    title: "Market — HL y CCC semanal",
    icon: FileSpreadsheet,
    color: "text-indigo-600",
    bg: "bg-indigo-50",
    border: "border-indigo-100",
    desc: [
      "Sección HL: real vs cuota semanal (S1–S5) por vendedor",
      "Sección CCC: clientes únicos vs cuota semanal por vendedor",
      "Indicador de color verde/amarillo/rojo por % de cumplimiento",
      "Totales por semana y total mes",
    ],
  },
  {
    id: "productos",
    title: "Productos CES / PROCOVAR",
    icon: Package,
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    border: "border-emerald-100",
    desc: [
      "Hoja de cumplimiento de metas mensuales por producto",
      "Resumen global CES con gráfico de barras",
      "Resumen global PROCOVAR con gráfico de pie",
      "Una hoja por vendedor con su desglose individual",
    ],
  },
  {
    id: "ranking",
    title: "Ranking de Ventas",
    icon: Trophy,
    color: "text-amber-600",
    bg: "bg-amber-50",
    border: "border-amber-100",
    desc: [
      "Ranking general acumulado con medallas 🥇🥈🥉",
      "Ranking semanal con posiciones por semana",
      "Hoja de progreso diario acumulado",
      "Gráfico de líneas con evolución diaria por vendedor",
    ],
  },
  {
    id: "clientes-analisis",
    title: "Análisis de Clientes por Vendedor",
    icon: Users,
    color: "text-purple-600",
    bg: "bg-purple-50",
    border: "border-purple-100",
    desc: [
      "Clientes rankeados por volumen de ventas ($) de mayor a menor",
      "Una columna por cada SKU que el cliente compró (en $)",
      "Total por cliente y # de SKUs que compra cada uno",
      "Hoja Oficina (total) + una hoja por vendedor",
      "Identifica clientes más valiosos y oportunidades de venta cruzada",
    ],
  },
];

export default function ReportesView({ sourceId, period }) {
  const label = period ? formatPeriod(period) : "todos los meses (acumulado)";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <FileSpreadsheet className="text-brand-600" /> Exportar Reportes Excel
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Generando reportes para: <span className="font-semibold text-slate-700">{label}</span>.
          {!period && " Usa el selector de periodo arriba para filtrar por mes."}
        </p>
      </div>

      {/* Individual report cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {REPORTS.map((r) => (
          <ReportCard key={r.id} report={r} sourceId={sourceId} period={period} />
        ))}
      </div>

      {/* Export all - full width */}
      <div className={`card border-2 border-dashed border-slate-300 flex flex-col sm:flex-row items-start sm:items-center gap-4`}>
        <div className="p-3 rounded-xl bg-slate-100 shrink-0">
          <FileSpreadsheet size={28} className="text-slate-600" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-slate-800 text-lg">Exportar Todo en un solo archivo</h3>
          <p className="text-sm text-slate-500 mt-0.5">
            Un único archivo .xlsx con todas las hojas anteriores combinadas. Ideal para compartir o archivar.
          </p>
        </div>
        <DownloadBtn sourceId={sourceId} modulo="all" period={period} className="btn-primary shrink-0 text-base px-6 py-2.5" label="Descargar todo" size={18} />
      </div>
    </div>
  );
}

function DownloadBtn({ sourceId, modulo, period, className, label, size = 15 }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      className={className}
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try { await downloadExport(sourceId, modulo, period); }
        catch (e) { alert(e?.response?.data?.detail || "No se pudo descargar"); }
        finally { setBusy(false); }
      }}
    >
      <Download size={size} /> {busy ? "Generando…" : label}
    </button>
  );
}

function ReportCard({ report, sourceId, period }) {
  const Icon = report.icon;
  return (
    <div className={`card border ${report.border} flex flex-col gap-4`}>
      <div className="flex items-start gap-3">
        <div className={`p-2.5 rounded-xl ${report.bg} shrink-0`}>
          <Icon size={22} className={report.color} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-slate-800">{report.title}</h3>
        </div>
      </div>
      <ul className="space-y-1 text-sm text-slate-600 pl-1">
        {report.desc.map((d, i) => (
          <li key={i} className="flex items-start gap-1.5">
            <span className="text-slate-400 mt-0.5">•</span>
            <span>{d}</span>
          </li>
        ))}
      </ul>
      <DownloadBtn sourceId={sourceId} modulo={report.id} period={period} className="btn-primary self-end mt-auto" label="Descargar .xlsx" />
    </div>
  );
}
