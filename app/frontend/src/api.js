import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export async function uploadReport(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getDashboard(sid) {
  const { data } = await api.get(`/session/${sid}/dashboard`);
  return data;
}
export async function getVentas(sid)   { return (await api.get(`/session/${sid}/ventas`)).data; }
export async function getProductos(sid){ return (await api.get(`/session/${sid}/productos`)).data; }
export async function getRanking(sid)  { return (await api.get(`/session/${sid}/ranking`)).data; }
export async function getPunto(sid)    { return (await api.get(`/session/${sid}/clientes-punto`)).data; }

export function exportUrl(sid, modulo) {
  return `/api/session/${sid}/export/${modulo}.xlsx`;
}
