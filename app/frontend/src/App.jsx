import { BarChart3, Package, Settings as SettingsIcon, Target, Trophy, UserCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import ClientesPuntoView from "./components/ClientesPuntoView.jsx";
import DashboardView from "./components/DashboardView.jsx";
import ProductosView from "./components/ProductosView.jsx";
import RankingView from "./components/RankingView.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import VendedoresView from "./components/VendedoresView.jsx";
import VentasView from "./components/VentasView.jsx";

const TABS = [
  { id: "dashboard", label: "Resumen", icon: BarChart3, Comp: DashboardView },
  { id: "ventas", label: "Ventas (HL)", icon: Target, Comp: VentasView },
  { id: "productos", label: "Productos", icon: Package, Comp: ProductosView },
  { id: "ranking", label: "Ranking", icon: Trophy, Comp: RankingView },
  { id: "vendedores", label: "Vendedores", icon: UserCheck, Comp: VendedoresView },
  { id: "punto", label: "Clientes Punto", icon: Users, Comp: ClientesPuntoView },
];

export default function App() {
  const [sourceId, setSourceId] = useState("accumulated");
  const [tab, setTab] = useState("dashboard");
  const [uploads, setUploads] = useState([]);
  const [showSettings, setShowSettings] = useState(false);

  const currentUpload = uploads.find((u) => u.id === sourceId);

  // If the active source was deleted, fall back to accumulated
  useEffect(() => {
    if (sourceId !== "accumulated" && uploads.length > 0 && !currentUpload) {
      setSourceId("accumulated");
    }
  }, [uploads, sourceId, currentUpload]);

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
                    return (
                      <button key={t.id} className={`tab ${active ? "tab-active" : ""}`} onClick={() => setTab(t.id)}>
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
                <Current sourceId={sourceId} />
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
