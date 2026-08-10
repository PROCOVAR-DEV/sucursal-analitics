import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// Sucursal "virtual" = vista combinada de TODAS las sucursales permitidas.
export const ALL_SID = "__all__";

// ---- Estado de sesión (token + sucursal activa) ----
let _sucursal = null;

export function setToken(token) {
  if (token) localStorage.setItem("token", token);
  else localStorage.removeItem("token");
}
export function getToken() {
  return localStorage.getItem("token");
}
export function setSucursal(sid) {
  _sucursal = sid;
  if (sid) localStorage.setItem("sucursal", sid);
}
export function getSucursalId() {
  return _sucursal || localStorage.getItem("sucursal");
}

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      setToken(null);
      if (!location.pathname.includes("login")) location.reload();
    }
    return Promise.reject(err);
  }
);

// ---- Auth ----
export async function login(username, password) {
  const { data } = await api.post("/auth/login", { username, password });
  setToken(data.token);
  return data.user;
}
export function logout() {
  setToken(null);
  localStorage.removeItem("sucursal");
}
export async function me() {
  const { data } = await api.get("/auth/me");
  return data;
}

// ---- Usuarios (admin) ----
export async function listUsers() { return (await api.get("/users")).data.items; }
export async function createUser(payload) { return (await api.post("/users", payload)).data; }
export async function updateUser(username, payload) { return (await api.put(`/users/${username}`, payload)).data; }
export async function deleteUser(username) { await api.delete(`/users/${username}`); }

// ---- Sucursales ----
export async function listSucursales() { return (await api.get("/sucursales")).data.items; }
export async function createSucursal(payload) { return (await api.post("/sucursales", payload)).data; }
export async function getSucursal(sid) { return (await api.get(`/sucursales/${sid}`)).data; }
export async function updateSucursal(sid, payload) { return (await api.put(`/sucursales/${sid}`, payload)).data; }
export async function deleteSucursal(sid) { await api.delete(`/sucursales/${sid}`); }
export async function resetSucursal(sid) { return (await api.post(`/sucursales/${sid}/reset`)).data; }

// ---- Gestores (CRUD) ----
export async function addGestor(sid, payload) { return (await api.post(`/sucursales/${sid}/gestores`, payload)).data; }
export async function updateGestor(sid, clave, payload) { return (await api.put(`/sucursales/${sid}/gestores/${encodeURIComponent(clave)}`, payload)).data; }
export async function deleteGestor(sid, clave) { await api.delete(`/sucursales/${sid}/gestores/${encodeURIComponent(clave)}`); }

// --- reglas de comisión por producto -----------------------------------------
// Todas devuelven la lista COMPLETA y los avisos de solape, no solo lo tocado:
// crear una regla puede cambiar cuál manda en otra, así que la pantalla tiene
// que repintarse entera con lo que diga el servidor.
export async function listComisiones(sid) { return (await api.get(`/sucursales/${sid}/comisiones`)).data; }
export async function addComision(sid, payload) { return (await api.post(`/sucursales/${sid}/comisiones`, payload)).data; }
export async function updateComision(sid, rid, payload) { return (await api.put(`/sucursales/${sid}/comisiones/${rid}`, payload)).data; }
export async function deleteComision(sid, rid) { return (await api.delete(`/sucursales/${sid}/comisiones/${rid}`)).data; }

// Ámbito GLOBAL: la regla vale para todas las sucursales. Ruta aparte a
// propósito — desde la pantalla de una sucursal no debe poder tocarse algo que
// afecta a las siete.
export async function listComisionesGlobales() { return (await api.get(`/comisiones`)).data; }
export async function addComisionGlobal(payload) { return (await api.post(`/comisiones`, payload)).data; }
export async function updateComisionGlobal(rid, payload) { return (await api.put(`/comisiones/${rid}`, payload)).data; }
export async function deleteComisionGlobal(rid) { return (await api.delete(`/comisiones/${rid}`)).data; }

// ---- Uploads (sucursal activa) ----
// En modo "Todas las sucursales" las consultas van a /all/... (agregado en el backend).
function base() {
  const sid = getSucursalId();
  return sid === ALL_SID ? "/all" : `/sucursales/${sid}`;
}
export async function uploadFile(file, { force = false } = {}) {
  const form = new FormData();
  form.append("file", file);
  if (force) form.append("force", "true");
  const { data } = await api.post(`${base()}/uploads`, form, { headers: { "Content-Type": "multipart/form-data" } });
  return data;
}
export async function listUploads() { return (await api.get(`${base()}/uploads`)).data.items; }
export async function deleteUpload(id) { await api.delete(`${base()}/uploads/${id}`); }
export async function deleteAllUploads() { await api.delete(`${base()}/uploads`); }

// ---- Consultas (id = uuid | "accumulated") ----
function q(mes) { return mes ? `?mes=${encodeURIComponent(mes)}` : ""; }
const src = (id) => `${base()}/sources/${id}`;

export async function getDashboard(id, mes = null)  { return (await api.get(`${src(id)}/dashboard${q(mes)}`)).data; }
export async function getVentas(id, mes = null)     { return (await api.get(`${src(id)}/ventas${q(mes)}`)).data; }
export async function getProductos(id, mes = null)  { return (await api.get(`${src(id)}/productos${q(mes)}`)).data; }
export async function getMarket(id, mes = null)     { return (await api.get(`${src(id)}/market${q(mes)}`)).data; }
export async function getRanking(id, mes = null)    { return (await api.get(`${src(id)}/ranking${q(mes)}`)).data; }
// `grupos` acota a unos grupos comerciales; vacio = todos. `metrica` es
// "importe" (dolares) o "cantidad" (por empaque, tal como viene del origen).
export async function getClientesAnalisis(id, mes = null, grupos = [], metrica = "importe") {
  const p = new URLSearchParams();

  if (mes) p.set("mes", mes);
  for (const g of grupos) p.append("grupo", g);
  if (metrica && metrica !== "importe") p.set("metrica", metrica);

  const qs = p.toString();

  return (await api.get(`${src(id)}/clientes-analisis${qs ? `?${qs}` : ""}`)).data;
}
export async function getVendedores(id, mes = null) { return (await api.get(`${src(id)}/vendedores${q(mes)}`)).data; }
// Informe cruzado gestor x producto por importe, con totales en ambas direcciones.
export async function getGestorSku(id, mes = null) { return (await api.get(`${src(id)}/gestor-sku${q(mes)}`)).data; }
export async function getDiario(id, mes = null, gestor = null) {
  const qs = [mes ? `mes=${encodeURIComponent(mes)}` : "", gestor ? `gestor=${encodeURIComponent(gestor)}` : ""].filter(Boolean).join("&");
  return (await api.get(`${src(id)}/diario${qs ? "?" + qs : ""}`)).data;
}
// `dia` = día de corte elegido (para mirar días anteriores). Sin él, el último con datos.
export async function getMetasGestor(id, mes = null, dia = null) {
  const qs = [mes ? `mes=${encodeURIComponent(mes)}` : "", dia ? `dia=${encodeURIComponent(dia)}` : ""].filter(Boolean).join("&");
  return (await api.get(`${src(id)}/metas-gestor${qs ? "?" + qs : ""}`)).data;
}
export async function getPeriods(id)                { return (await api.get(`${src(id)}/periods`)).data; }

// ---- Descarga de export (con auth → blob) ----
export async function downloadExport(id, modulo, mes = null) {
  const resp = await api.get(`${src(id)}/export/${modulo}.xlsx${q(mes)}`, { responseType: "blob" });
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${modulo}${mes ? "_" + mes : ""}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
