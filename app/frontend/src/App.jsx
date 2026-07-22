import { BarChart3, CalendarDays, Calendar, FileSpreadsheet, LogOut, Package, Settings as SettingsIcon, ShoppingCart, Target, Trophy, UserCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import AdminPanel from "./components/AdminPanel.jsx";
import ClientesAnalisisView from "./components/ClientesAnalisisView.jsx";
import DashboardView from "./components/DashboardView.jsx";
import Login from "./components/Login.jsx";
import MarketView from "./components/MarketView.jsx";
import ProductosView from "./components/ProductosView.jsx";
import RankingView from "./components/RankingView.jsx";
import ReportesView from "./components/ReportesView.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import VendedoresView from "./components/VendedoresView.jsx";
import VentasView from "./components/VentasView.jsx";
import { ALL_SID, getPeriods, getToken, listSucursales, logout, me, setSucursal } from "./api.js";
import { Picker, Select } from "./components/ui.jsx";

const MONTHS_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
function fmtPeriod(p) {
  if (!p) return "Todo (global)";
  const [y, m] = p.split("-");
  return `${MONTHS_ES[parseInt(m, 10) - 1]} ${y}`;
}

const TABS = [
  { id: "dashboard", label: "Resumen", icon: BarChart3, Comp: DashboardView },
  { id: "ventas", label: "Ventas (HL)", icon: Target, Comp: VentasView },
  { id: "market", label: "Market", icon: ShoppingCart, Comp: MarketView },
  { id: "productos", label: "Productos", icon: Package, Comp: ProductosView },
  { id: "ranking", label: "Ranking", icon: Trophy, Comp: RankingView },
  { id: "vendedores", label: "Vendedores", icon: UserCheck, Comp: VendedoresView },
  { id: "clientes", label: "Análisis Clientes", icon: Users, Comp: ClientesAnalisisView },
  { id: "reportes", label: "Reportes", icon: FileSpreadsheet, Comp: ReportesView },
];
const VIEW_IDS = TABS.map((t) => t.id);
export const CONFIG_LABELS = {
  sucursal: "Sucursal", gestores: "Gestores", metas: "Metas", calculadora: "Calculadora de metas",
  grupos: "Grupos y productos", parametros: "Parámetros", sucursales: "Sucursales", usuarios: "Usuarios",
};

// --- Router por hash (sin dependencias): #/<vista> ó #/config/<seccion> ---
function usePath() {
  const read = () => window.location.hash.replace(/^#\/?/, "").replace(/\/+$/, "") || "dashboard";
  const [path, setPath] = useState(read);
  useEffect(() => {
    const on = () => setPath(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (p) => { if (window.location.hash.replace(/^#\/?/, "").replace(/\/+$/, "") !== p) window.location.hash = "#/" + p; };
  return [path, go];
}

export default function App() {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [sucursales, setSucursales] = useState([]);
  const [sid, setSid] = useState(null);
  const [sourceId, setSourceId] = useState("accumulated");
  const [uploads, setUploads] = useState([]);
  const [period, setPeriod] = useState(null);
  const [periods, setPeriods] = useState([]);
  const [path, go] = usePath();

  const isConfig = path === "config" || path.startsWith("config/");
  const configSection = isConfig ? (path.split("/")[1] || "sucursal") : "sucursal";
  const view = !isConfig && VIEW_IDS.includes(path) ? path : "dashboard";

  useEffect(() => {
    if (!getToken()) { setBooting(false); return; }
    me().then((u) => setUser(u)).catch(() => {}).finally(() => setBooting(false));
  }, []);

  const loadSucursales = () => listSucursales().then((items) => {
    setSucursales(items);
    setSid((cur) => {
      if (cur === ALL_SID) { setSucursal(cur); return cur; }  // mantener "Todas las sucursales"
      const next = cur && items.find((s) => s.id === cur) ? cur : items[0]?.id || null;
      setSucursal(next);
      return next;
    });
  });
  useEffect(() => { if (user) loadSucursales(); }, [user]);

  useEffect(() => {
    if (!sid) return;
    setSucursal(sid);
    setSourceId("accumulated");
    setPeriod(null);
  }, [sid]);

  useEffect(() => {
    if (!sid) return;
    setPeriods([]);
    getPeriods(sourceId).then((d) => {
      const ps = d.periods || [];
      setPeriods(ps);
      // Por defecto: el MES ACTUAL si tiene datos; si no, el mes más reciente con datos;
      // y solo si no hay ningún mes, cae en el acumulado global (null).
      const now = new Date();
      const cur = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
      const latest = ps.slice().sort().reverse()[0];
      setPeriod(ps.includes(cur) ? cur : (latest || null));
    }).catch(() => { setPeriods([]); setPeriod(null); });
  }, [sourceId, sid]);

  if (booting) return <div className="h-screen flex items-center justify-center text-slate-400">Cargando…</div>;
  if (!user) return <Login onLogin={setUser} />;

  const currentUpload = uploads.find((u) => u.id === sourceId);
  const Current = TABS.find((t) => t.id === view).Comp;
  const currentSuc = sucursales.find((s) => s.id === sid);
  const viewLabel = TABS.find((t) => t.id === view)?.label;
  const canConfig = user.role === "admin" || user.role === "supervisor";
  const canSeeAll = user.role === "admin" || user.role === "analitico";  // ven todas las sucursales
  const isAll = sid === ALL_SID;
  if (isConfig && (!canConfig || isAll)) { go("dashboard"); }  // config es por-sucursal, no en modo "Todas"

  function doLogout() { logout(); setUser(null); setSucursales([]); setSid(null); }

  return (
    <div className="h-screen flex flex-col">
      <header className="bg-gradient-to-r from-brand-900 via-brand-700 to-brand-500 text-white shadow shrink-0">
        <div className="px-3 sm:px-6 py-3 flex items-center justify-between gap-3 sm:gap-4 flex-wrap">
          <div className="min-w-0">
            <h1 className="text-base sm:text-lg font-bold leading-tight">Sucursal Analytics</h1>
            {/* Breadcrumb: dónde estás */}
            <p className="text-xs text-brand-100/90 flex items-center gap-1.5 truncate">
              <span className="opacity-80">{isAll ? "Todas las sucursales" : (currentSuc?.nombre || "—")}</span>
              <span className="opacity-50">›</span>
              {isConfig ? (
                <><span className="opacity-80">Configuración</span><span className="opacity-50">›</span><span className="font-semibold">{CONFIG_LABELS[configSection] || configSection}</span></>
              ) : (
                <span className="font-semibold">{viewLabel}</span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Picker value={sid || ""} onChange={(v) => { setSucursal(v); setSid(v); }}
              options={[
                ...(canSeeAll ? [{ value: ALL_SID, label: "Todas las sucursales" }] : []),
                ...sucursales.map((s) => ({ value: s.id, label: s.nombre, hint: `${s.gestores ?? ""}${s.gestores ? " gestores" : ""}` })),
              ]} />
            {canConfig && !isAll && (
              <button className={`btn ${isConfig ? "bg-white text-brand-700" : "bg-white/10 hover:bg-white/20 text-white"}`} onClick={() => go(isConfig ? "dashboard" : (user.role === "supervisor" ? "config/metas" : "config/sucursal"))}>
                <SettingsIcon size={16} /> {isConfig ? "Tablero" : "Config"}
              </button>
            )}
            <span className="hidden md:flex items-center gap-1.5 text-brand-100/90 text-xs ml-1">
              {user.nombre} <span className="px-1.5 py-0.5 rounded-full bg-white/15 text-white text-[10px] font-semibold uppercase">{user.role}</span>
            </span>
            <button className="btn bg-white/10 hover:bg-white/20 text-white" onClick={doLogout} title="Salir"><LogOut size={16} /></button>
          </div>
        </div>
      </header>

      {!isConfig && (
        <div className="bg-white border-b border-slate-200 px-3 sm:px-6 py-2 flex items-center gap-2 sm:gap-3 text-sm shrink-0 flex-wrap">
          <Calendar size={15} className="text-slate-400 shrink-0" />
          <span className="text-slate-500 font-medium shrink-0">Periodo:</span>
          <Select width="flex-1 min-w-[10rem] sm:flex-none sm:w-56" value={period || ""} onChange={(v) => setPeriod(v || null)}
            options={[{ value: "", label: "Todo (acumulado)" }, ...periods.map((p) => ({ value: p, label: fmtPeriod(p) }))]} />
          {period && <span className="ml-1 px-2 py-0.5 rounded-full bg-brand-100 text-brand-700 text-xs font-semibold">{fmtPeriod(period)}</span>}
        </div>
      )}

      {/* En móvil el panel de archivos se apila arriba y scrollea toda la página;
          desde md+ vuelve a ser sidebar lateral y solo scrollea el <main>.
          min-w-0 en <main> evita que las tablas anchas estiren el flex. */}
      <div className="flex flex-col md:flex-row flex-1 overflow-y-auto md:overflow-hidden">
        {!isConfig && !isAll && <UploadPanel sourceId={sourceId} onSelect={setSourceId} onRefresh={setUploads} key={sid} />}
        <main className="flex-1 min-w-0 md:overflow-y-auto bg-slate-50">
          <div className="max-w-7xl mx-auto p-3 sm:p-6">
            {isConfig ? (
              sid ? (
                <AdminPanel sid={sid} user={user} sucursales={sucursales} onSucursalesChanged={loadSucursales}
                  section={configSection} onSection={(id) => go("config/" + id)} />
              ) : (
                <div className="p-6 text-slate-400 animate-pulse">Cargando sucursal…</div>
              )
            ) : (
              <>
                <nav className="flex flex-wrap gap-1.5 mb-6 border-b border-slate-200 pb-3">
                  {TABS.map((t) => (
                    <button key={t.id} className={`tab ${t.id === view ? "tab-active" : ""}`} onClick={() => go(t.id)}>
                      <t.icon size={16} /> {t.label}
                    </button>
                  ))}
                </nav>
                {!isAll && uploads.length === 0 && (
                  <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                    Sube un Reporte de Venta (.xls/.xlsx) para ver datos reales de {currentSuc?.nombre}.
                  </div>
                )}
                {sid && (isAll && view !== "dashboard" ? (
                  <div className="p-8 text-center text-slate-400">
                    Elige una sucursal específica para ver «{viewLabel}». La vista combinada solo está disponible en el <b>Resumen</b>.
                  </div>
                ) : (
                  <Current sourceId={sourceId} period={period} />
                ))}
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
