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
export async function getDashboard(id)  { return (await api.get(`/sources/${id}/dashboard`)).data; }
export async function getVentas(id)     { return (await api.get(`/sources/${id}/ventas`)).data; }
export async function getProductos(id)  { return (await api.get(`/sources/${id}/productos`)).data; }
export async function getRanking(id)    { return (await api.get(`/sources/${id}/ranking`)).data; }
export async function getPunto(id)      { return (await api.get(`/sources/${id}/clientes-punto`)).data; }
export async function getSummary(id)    { return (await api.get(`/sources/${id}/summary`)).data; }

export function exportUrl(id, modulo) {
  return `/api/sources/${id}/export/${modulo}.xlsx`;
}

// ---- Settings ----
export async function getSettings()           { return (await api.get("/settings")).data; }
export async function saveSettings(payload)   { return (await api.put("/settings", payload)).data; }
export async function resetSettings()         { return (await api.post("/settings/reset")).data; }
