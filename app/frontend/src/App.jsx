import { BarChart3, Calendar, FileSpreadsheet, Package, Settings as SettingsIcon, Target, Trophy, UserCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import ClientesPuntoView from "./components/ClientesPuntoView.jsx";
import DashboardView from "./components/DashboardView.jsx";
import ProductosView from "./components/ProductosView.jsx";
import RankingView from "./components/RankingView.jsx";
import ReportesView from "./components/ReportesView.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import VendedoresView from "./components/VendedoresView.jsx";
import VentasView from "./components/VentasView.jsx";
import { getPeriods } from "./api.js";

const MONTHS_ES = [
  "Enero","Febrero","Marzo","Abril","Mayo","Junio",
  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
];
function fmtPeriod(p) {
  if (!p) return "Todo (global)";
  const [y, m] = p.split("-");
  return `${MONTHS_ES[parseInt(m, 10) - 1]} ${y}`;
}

const TABS = [
  { id: "dashboard",  label: "Resumen",        icon: BarChart3,       Comp: DashboardView },
  { id: "ventas",     label: "Ventas (HL)",     icon: Target,          Comp: VentasView },
  { id: "productos",  label: "Productos",       icon: Package,         Comp: ProductosView },
  { id: "ranking",    label: "Ranking",         icon: Trophy,          Comp: RankingView },
  { id: "vendedores", label: "Vendedores",      icon: UserCheck,       Comp: VendedoresView },
  { id: "punto",      label: "Clientes Punto",  icon: Users,           Comp: ClientesPuntoView },
  { id: "reportes",   label: "Reportes",        icon: FileSpreadsheet, Comp: ReportesView },
];

export default function App() {
  const [sourceId, setSourceId] = useState("accumulated");
  const [tab, setTab] = useState("dashboard");
  const [uploads, setUploads] = useState([]);
  const [showSettings, setShowSettings] = useState(false);
  const [period, setPeriod] = useState(null);       // null = all | "YYYY-MM"
  const [periods, setPeriods] = useState([]);       // available months

  const currentUpload = uploads.find((u) => u.id === sourceId);

  // If the active source was deleted, fall back to accumulated
  useEffect(() => {
    if (sourceId !== "accumulated" && uploads.length > 0 && !currentUpload) {
      setSourceId("accumulated");
    }
  }, [uploads, sourceId, currentUpload]);

  // Fetch available months whenever source changes
  useEffect(() => {
    setPeriod(null);
    setPeriods([]);
    getPeriods(sourceId)
      .then((d) => setPeriods(d.periods || []))
      .catch(() => setPeriods([]));
  }, [sourceId]);

  const Current = TABS.find((t) => t.id === tab).Comp;

  const headerLabel = showSettings
    ? "Configuración"
    : sourceId === "accumulated"
    ? `Acumulado global · ${uploads.length} archivo${uploads.length === 1 ? "" : "s"}`
    : currentUpload
    ? `${currentUpload.filename} · ${currentUpload.rango}`
    : "Sin fuente";

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-gradient-to-r from-brand-900 via-brand-700 to-brand-500 text-white shadow shrink-0">
        <div className="px-6 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold">Sucursal Analytics</h1>
            <p className="text-xs text-brand-100/90">{headerLabel}</p>
          </div>
          <button
            className={`btn ${showSettings ? "bg-white text-brand-700" : "bg-white/10 hover:bg-white/20 text-white"}`}
            onClick={() => setShowSettings((s) => !s)}
          >
            <SettingsIcon size={16} /> {showSettings ? "Volver al tablero" : "Metas / Config"}
          </button>
        </div>
      </header>

      {/* Period selector bar */}
      {!showSettings && (
        <div className="bg-white border-b border-slate-200 px-6 py-2 flex items-center gap-3 text-sm shrink-0">
          <Calendar size={15} className="text-slate-400 shrink-0" />
          <span className="text-slate-500 font-medium shrink-0">Periodo:</span>
          <select
            className="input py-1 text-sm"
            value={period || ""}
            onChange={(e) => setPeriod(e.target.value || null)}
          >
            <option value="">Todo (acumulado global)</option>
            {periods.map((p) => (
              <option key={p} value={p}>{fmtPeriod(p)}</option>
            ))}
          </select>
          {period && (
            <button
              className="text-xs text-slate-400 hover:text-red-500 transition font-medium"
              onClick={() => setPeriod(null)}
            >
              ✕ Limpiar
            </button>
          )}
          {period && (
            <span className="ml-1 px-2 py-0.5 rounded-full bg-brand-100 text-brand-700 text-xs font-semibold">
              {fmtPeriod(period)}
            </span>
          )}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <UploadPanel sourceId={sourceId} onSelect={setSourceId} onRefresh={setUploads} />

        <main className="flex-1 overflow-y-auto bg-slate-50">
          <div className="max-w-7xl mx-auto p-6">
            {showSettings ? (
              <SettingsPanel />
            ) : (
              <>
                <nav className="flex flex-wrap gap-2 mb-6 border-b border-slate-200 pb-3">
                  {TABS.map((t) => {
                    const Icon = t.icon;
                    const active = t.id === tab;
                    const isReportes = t.id === "reportes";
                    return (
                      <button
                        key={t.id}
                        className={`tab ${active ? "tab-active" : ""} ${isReportes && !active ? "border border-brand-200 text-brand-700 hover:bg-brand-50" : ""}`}
                        onClick={() => setTab(t.id)}
                      >
                        <Icon size={16} className="inline mr-1.5 -mt-0.5" /> {t.label}
                      </button>
                    );
                  })}
                </nav>
                {uploads.length === 0 && (
                  <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                    Todavía no hay archivos cargados. Los KPIs muestran las metas configuradas; sube un Reporte de Venta
                    cuando quieras para ver datos reales.
                  </div>
                )}
                <Current sourceId={sourceId} period={period} />
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
