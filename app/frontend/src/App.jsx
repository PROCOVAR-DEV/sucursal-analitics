import { BarChart3, LogOut, Package, Target, Trophy, Users } from "lucide-react";
import { useState } from "react";
import ClientesPuntoView from "./components/ClientesPuntoView.jsx";
import DashboardView from "./components/DashboardView.jsx";
import ProductosView from "./components/ProductosView.jsx";
import RankingView from "./components/RankingView.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import VentasView from "./components/VentasView.jsx";

const TABS = [
  { id: "dashboard", label: "Resumen", icon: BarChart3, Comp: DashboardView },
  { id: "ventas", label: "Ventas (HL)", icon: Target, Comp: VentasView },
  { id: "productos", label: "Productos", icon: Package, Comp: ProductosView },
  { id: "ranking", label: "Ranking", icon: Trophy, Comp: RankingView },
  { id: "punto", label: "Clientes Punto", icon: Users, Comp: ClientesPuntoView },
];

export default function App() {
  const [session, setSession] = useState(null);
  const [tab, setTab] = useState("dashboard");

  if (!session) {
    return (
      <div className="min-h-screen">
        <Header />
        <UploadPanel onUploaded={setSession} />
      </div>
    );
  }

  const Current = TABS.find((t) => t.id === tab).Comp;

  return (
    <div className="min-h-screen">
      <Header session={session} onReset={() => setSession(null)} />
      <div className="max-w-7xl mx-auto p-6">
        <nav className="flex flex-wrap gap-2 mb-6 border-b border-slate-200 pb-3">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = t.id === tab;
            return (
              <button
                key={t.id}
                className={`tab ${active ? "tab-active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                <Icon size={16} className="inline mr-1.5 -mt-0.5" /> {t.label}
              </button>
            );
          })}
        </nav>
        <Current sid={session.session_id} />
      </div>
    </div>
  );
}

function Header({ session, onReset }) {
  return (
    <header className="bg-gradient-to-r from-brand-900 via-brand-700 to-brand-500 text-white shadow">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Sucursal Analytics</h1>
          <p className="text-xs text-brand-100/90">
            Dashboard web para el Reporte de Venta diario
          </p>
        </div>
        {session && (
          <div className="flex items-center gap-3">
            <div className="text-right text-xs">
              <div className="font-semibold">{session.filename}</div>
              <div className="opacity-80">
                {session.rango} · {session.filas.toLocaleString("es-CO")} filas
              </div>
            </div>
            <button className="btn bg-white/10 hover:bg-white/20 text-white" onClick={onReset}>
              <LogOut size={16} /> Nuevo archivo
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
