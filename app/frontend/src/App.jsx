import { BarChart3, CalendarDays, Calendar, FileSpreadsheet, LogOut, Package, Settings as SettingsIcon, ShoppingCart, Target, Trophy, UserCheck, Users, Grid3x3 } from "lucide-react";
import { useEffect, useState } from "react";
import AdminPanel from "./components/AdminPanel.jsx";
import ClientesAnalisisView from "./components/ClientesAnalisisView.jsx";
import DashboardView from "./components/DashboardView.jsx";
import Login from "./components/Login.jsx";
import MarketView from "./components/MarketView.jsx";
import ProductosView from "./components/ProductosView.jsx";
import RankingView from "./components/RankingView.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import ReportesView from "./components/ReportesView.jsx";
import VendedoresView from "./components/VendedoresView.jsx";
import GestorSkuView from "./components/GestorSkuView.jsx";
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
  { id: "gestor-sku", label: "Gestor × Producto", icon: Grid3x3, Comp: GestorSkuView },
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
  /**
   * Si está abierto el panel de cargar reportes a mano.
   *
   * Cerrado por defecto: el camino normal es que las ventas las traiga el
   * sincronizador de Ventra, y tener siempre desplegada una columna para subir Excel
   * es ocupar media pantalla con el último recurso. Se abre cuando hace falta —Ventra
   * caído, una sucursal sin histórico todavía— y se cierra al terminar.
   */
  const [verCarga, setVerCarga] = useState(false);
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
      if (cur && items.find((s) => s.id === cur)) { setSucursal(cur); return cur; }

      // Con qué sucursal se entra.
      //
      // Quien ve todas —administrador, analítico— entra en "Todas las sucursales" y
      // elige. Antes caía en la PRIMERA de la lista, que es la primera por orden
      // alfabético y no significa nada: se ponía a mirar Camagüey creyendo que miraba
      // el conjunto, o tenía que acordarse de cambiar cada vez.
      //
      // Quien pertenece a una sucursal entra directo en la suya, que es la única que
      // le interesa. Si le tocaran varias, la primera de las suyas.
      const puedeVerTodas = user?.role === "admin" || user?.role === "analitico";
      const next = puedeVerTodas && items.length > 1 ? ALL_SID : items[0]?.id || null;
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

  const Current = TABS.find((t) => t.id === view).Comp;
  const currentSuc = sucursales.find((s) => s.id === sid);
  const viewLabel = TABS.find((t) => t.id === view)?.label;
  const canConfig = user.role === "admin" || user.role === "supervisor";
  const canSeeAll = user.role === "admin" || user.role === "analitico";  // ven todas las sucursales
  const isAll = sid === ALL_SID;
  if (isConfig && !canConfig) { go("dashboard"); }

  function doLogout() { logout(); setUser(null); setSucursales([]); setSid(null); }

  // overflow-x-hidden en la raiz: la PAGINA no se desplaza de lado nunca. Lo
  // ancho (tablas con muchas columnas) se desplaza DENTRO de su panel. Sin esto
  // una tabla ancha empuja todo el layout: se van de vista la cabecera y las
  // columnas ancladas dejan de anclar, porque el que scrollea pasa a ser la
  // pagina en vez de su contenedor.
  return (
    <div className="h-screen flex flex-col overflow-x-hidden">
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
            {canConfig && (
              <button className={`btn ${isConfig ? "bg-white text-brand-700" : "bg-white/10 hover:bg-white/20 text-white"}`} onClick={() => {
                if (isConfig) { go("dashboard"); return; }
                if (user.role === "supervisor") { go("config/metas"); return; }
                go("config/sucursal");
              }}>
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
          {/* La puerta a la carga manual: un botón pequeño y pegado al selector, no
              empujado al borde. Existe para el día que Ventra no esté, no para usarlo
              todos los días, así que no tiene por qué llamar la atención. */}
          {!isAll && (
            <button
              aria-pressed={verCarga}
              className={`shrink-0 inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
                verCarga
                  ? "border-brand-300 bg-brand-50 text-brand-700"
                  : "border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
              title="Sólo hace falta cuando Ventra no está disponible"
              type="button"
              onClick={() => setVerCarga((v) => !v)}
            >
              <FileSpreadsheet size={13} />
              {verCarga ? "Ocultar carga" : "Carga manual"}
            </button>
          )}
        </div>
      )}

      {/*
        SE ACABÓ SUBIR REPORTES A MANO.

        Los informes leen de Ventra. La columna de subir ficheros y de listarlos ocupaba
        media pantalla para un trabajo que ya no existe, y esa media pantalla se
        aprovecha mejor en los gráficos, que es a lo que se viene.

        El respaldo sigue puesto por detrás: si una sucursal todavía no tiene su
        histórico traído, `_get_source` le sirve el último Excel que subió, así que no
        se queda a oscuras mientras se recupera. Lo que ya no se puede es subir uno
        nuevo, y por eso hay que terminar de recuperar las diez bases.

        En móvil el contenido se apila y scrollea toda la página; desde md+ sólo
        scrollea el <main>. min-w-0 evita que las tablas anchas estiren el flex.
      */}
      <div className="flex flex-col md:flex-row flex-1 overflow-y-auto md:overflow-hidden">
        <main className="flex-1 min-w-0 md:overflow-y-auto bg-slate-50">
          <div className="max-w-7xl mx-auto p-3 sm:p-6">
            {isConfig ? (
              isAll ? (
                <AdminPanel sid={ALL_SID} user={user} sucursales={sucursales} onSucursalesChanged={loadSucursales}
                  section={configSection} onSection={(id) => go("config/" + id)} />
              ) : sid ? (
                <AdminPanel sid={sid} user={user} sucursales={sucursales} onSucursalesChanged={loadSucursales}
                  section={configSection} onSection={(id) => go("config/" + id)} />
              ) : (
                <div className="p-6 text-slate-400 animate-pulse">Cargando sucursal…</div>
              )
            ) : (
              <>
                {/* En móvil se ARRASTRA, no se apila.
                    Son nueve pestañas: envueltas ocupan cuatro filas y se comen la
                    pantalla entera antes de que se vea un solo dato. Arrastrando,
                    ocupan una fila y se llega a todas con el dedo. En pantalla ancha
                    caben todas y se envuelven como siempre. */}
                <nav className="flex gap-1.5 mb-6 border-b border-slate-200 pb-3 overflow-x-auto scroll-thin -mx-3 px-3 sm:mx-0 sm:px-0 sm:flex-wrap sm:overflow-visible">
                  {TABS.map((t) => (
                    <button key={t.id} className={`tab shrink-0 ${t.id === view ? "tab-active" : ""}`} onClick={() => go(t.id)}>
                      <t.icon size={16} /> {t.label}
                    </button>
                  ))}
                </nav>
                {/* Y si una sucursal no tiene NADA —ni Ventra ni un Excel viejo—, se
                    dice qué pasa y qué falta, en vez de enseñar todo a cero, que se
                    lee como que esa sucursal no vendió nada. */}
                {!isAll && !currentSuc?.ventra && (
                  <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
                    Las ventas de {currentSuc?.nombre} todavía no se han traído de Ventra.
                    Lo que se ve abajo es el último reporte que se subió a mano.{" "}
                    <button
                      className="font-semibold underline underline-offset-2"
                      type="button"
                      onClick={() => setVerCarga(true)}
                    >
                      Cargar uno nuevo
                    </button>
                  </div>
                )}
                {/* Ancho completo y arriba del todo cuando se abre: se usa un momento,
                    se cierra, y la pantalla vuelve a ser lo que importa. */}
                {verCarga && !isAll && (
                  <div className="mb-4">
                    <UploadPanel sourceId={sourceId} onSelect={setSourceId} key={sid} />
                  </div>
                )}
                {sid && (isAll && view !== "dashboard" ? (
                  <div className="p-8 text-center text-slate-400">
                    Elige una sucursal específica para ver «{viewLabel}». La vista combinada solo está disponible en el <b>Resumen</b>.
                  </div>
                ) : (
                  <Current sourceId={sourceId} period={period} user={user} />
                ))}
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
