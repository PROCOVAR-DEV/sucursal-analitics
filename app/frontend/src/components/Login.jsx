import { LogIn, Lock, User } from "lucide-react";
import { useState } from "react";
import { login } from "../api.js";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const user = await login(username.trim(), password);
      onLogin(user);
    } catch (e) {
      setErr(e?.response?.data?.detail || "No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-screen flex items-center justify-center bg-gradient-to-br from-brand-900 via-brand-700 to-brand-500 p-4">
      <form onSubmit={submit} className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-8 space-y-5">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-brand-800">Sucursal Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">Inicia sesión para continuar</p>
        </div>
        {err && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">{err}</div>}
        <label className="block">
          <span className="block text-xs font-medium text-slate-600 mb-1">Usuario</span>
          <div className="relative">
            <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input className="input w-full pl-10" value={username} autoFocus
              onChange={(e) => setUsername(e.target.value)} placeholder="admin" />
          </div>
        </label>
        <label className="block">
          <span className="block text-xs font-medium text-slate-600 mb-1">Contraseña</span>
          <div className="relative">
            <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input className="input w-full pl-10" type="password" value={password}
              onChange={(e) => setPassword(e.target.value)} placeholder="••••••" />
          </div>
        </label>
        <button className="btn-primary w-full justify-center py-2.5" disabled={loading}>
          <LogIn size={16} /> {loading ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
