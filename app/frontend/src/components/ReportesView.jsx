import { Download, FileSpreadsheet, FileText, Package, TrendingUp, Trophy, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { downloadExport, getGruposComerciales } from "../api.js";

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
    id: "parranda-facturas",
    title: "Ventas por Factura (Parranda / Malta)",
    icon: FileText,
    color: "text-rose-600",
    bg: "bg-rose-50",
    border: "border-rose-100",
    desc: [
      "Una hoja por vendedor con CADA factura (No. Operación, Fecha, Cliente, Mercancía)",
      "Cantidad (empaques), Importe, Suma Total y Hectolitros por factura",
      "Solo Parranda y Malta, ordenado por fecha — para revisar factura por factura",
      "KPIs (ventas, HL, % cumplimiento) y conversión a blisters/pallets",
      "Hoja Supervisor con el resumen de todos los vendedores",
    ],
  },
  {
    // El MISMO por factura pero de TODO lo que se vende. El de arriba nacio copiando
    // `automatizar_parranda.py` y filtra a cerveza, asi que de arroz, aceite, papel o
    // baterias no habia ningun fichero por factura.
    id: "facturas",
    conGrupo: true,
    title: "Ventas por Factura (todos los productos)",
    icon: FileText,
    color: "text-slate-600",
    bg: "bg-slate-50",
    border: "border-slate-200",
    desc: [
      "Lo mismo que el de arriba pero con TODO lo que se vende, no solo cerveza",
      "Una hoja por vendedor con cada factura: operación, fecha, cliente y mercancía",
      "Todos los grupos juntos, o el que elijas en el desplegable de abajo",
      "Los hectolitros de abajo siguen siendo solo de Malta y Parranda: un saco de arroz no tiene HL",
      "Hoja Supervisor con el resumen de todos los vendedores",
    ],
  },
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
  /**
   * Los grupos que existen en estos datos, para el desplegable de los informes que lo
   * admiten. Salen de los datos y no de una lista escrita a mano: el dia que se
   * configure un grupo nuevo aparece solo.
   */
  const [gruposDisponibles, setGruposDisponibles] = useState([]);
  useEffect(() => {
    let vivo = true;
    getGruposComerciales(sourceId, period)
      .then((d) => { if (vivo) setGruposDisponibles(d.grupos || []); })
      .catch(() => { if (vivo) setGruposDisponibles([]); });  // sin lista, solo "todos"
    return () => { vivo = false; };
  }, [sourceId, period]);

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
          <ReportCard key={r.id} report={r} sourceId={sourceId} period={period} gruposDisponibles={gruposDisponibles} />
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

function DownloadBtn({ sourceId, modulo, period, className, label, size = 15, filtros }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      className={className}
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try { await downloadExport(sourceId, modulo, period, filtros || {}); }
        catch (e) { alert(e?.response?.data?.detail || "No se pudo descargar"); }
        finally { setBusy(false); }
      }}
    >
      <Download size={size} /> {busy ? "Generando…" : label}
    </button>
  );
}

function ReportCard({ report, sourceId, period, gruposDisponibles }) {
  const Icon = report.icon;
  const [grupo, setGrupo] = useState("");
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
      {/* Los informes que aceptan grupo llevan su propio selector: el mismo fichero
          sirve para todo junto o para un tipo concreto, y quien lo descarga elige. */}
      {report.conGrupo && (
        <label className="flex items-center gap-2 text-xs text-slate-600">
          <span className="shrink-0">Grupo:</span>
          <select className="input input-sm" value={grupo} onChange={(e) => setGrupo(e.target.value)}>
            <option value="">Todos los grupos</option>
            {(gruposDisponibles || []).map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </label>
      )}
      <DownloadBtn sourceId={sourceId} modulo={report.id} period={period}
        className="btn-primary self-end mt-auto" label="Descargar .xlsx"
        filtros={report.conGrupo && grupo ? { grupos: [grupo] } : {}} />
    </div>
  );
}
