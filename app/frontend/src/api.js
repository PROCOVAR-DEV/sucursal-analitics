import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// ---- Uploads CRUD ----
export async function uploadFile(file, { force = false } = {}) {
  const form = new FormData();
  form.append("file", file);
  if (force) form.append("force", "true");
  const { data } = await api.post("/uploads", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
export async function listUploads() {
  const { data } = await api.get("/uploads");
  return data.items;
}
export async function deleteUpload(id) {
  await api.delete(`/uploads/${id}`);
}
export async function deleteAllUploads() {
  await api.delete("/uploads");
}

// ---- Source queries (id = uuid | "accumulated") ----
function q(mes) { return mes ? `?mes=${encodeURIComponent(mes)}` : ""; }

export async function getDashboard(id, mes = null)  { return (await api.get(`/sources/${id}/dashboard${q(mes)}`)).data; }
export async function getVentas(id, mes = null)     { return (await api.get(`/sources/${id}/ventas${q(mes)}`)).data; }
export async function getProductos(id, mes = null)  { return (await api.get(`/sources/${id}/productos${q(mes)}`)).data; }
export async function getRanking(id, mes = null)    { return (await api.get(`/sources/${id}/ranking${q(mes)}`)).data; }
export async function getPunto(id, mes = null)      { return (await api.get(`/sources/${id}/clientes-punto${q(mes)}`)).data; }
export async function getVendedores(id, mes = null) { return (await api.get(`/sources/${id}/vendedores${q(mes)}`)).data; }
export async function getSummary(id)                { return (await api.get(`/sources/${id}/summary`)).data; }
export async function getPeriods(id)                { return (await api.get(`/sources/${id}/periods`)).data; }

export function exportUrl(id, modulo, mes = null) {
  return `/api/sources/${id}/export/${modulo}.xlsx${q(mes)}`;
}

// ---- Settings ----
export async function getSettings()           { return (await api.get("/settings")).data; }
export async function saveSettings(payload)   { return (await api.put("/settings", payload)).data; }
export async function resetSettings()         { return (await api.post("/settings/reset")).data; }
