import { Upload, FileSpreadsheet, Loader2, Trash2, FileText, Layers } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { deleteAllUploads, deleteUpload, listUploads, uploadFile } from "../api.js";

export default function UploadPanel({ sourceId, onSelect, onRefresh }) {
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  async function refresh() {
    try {
      const items = await listUploads();
      setUploads(items);
      onRefresh?.(items);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    }
  }
  useEffect(() => { refresh(); }, []);

  async function handleFile(file, { force = false } = {}) {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const up = await uploadFile(file, { force });
      await refresh();
      onSelect?.(up.id);
    } catch (e) {
      const status = e?.response?.status;
      const data = e?.response?.data;
      if (status === 409 && data?.conflicts?.length) {
        const lines = data.conflicts
          .map((c) => `  • ${c.filename}  (${c.rango})`)
          .join("\n");
        const ok = confirm(
          `Este archivo se solapa con otro ya subido:\n\n${lines}\n\n` +
            "¿Quieres REEMPLAZAR los archivos en conflicto por el nuevo?"
        );
        if (ok) {
          await handleFile(file, { force: true });
          return;
        }
      } else {
        setError(data?.detail || e.message);
      }
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete(id) {
    if (!confirm("¿Eliminar este archivo del histórico?")) return;
    await deleteUpload(id);
    await refresh();
    if (sourceId === id) onSelect?.("accumulated");
  }

  async function handleClear() {
    if (!confirm("¿Borrar TODOS los archivos acumulados? Esta acción no se puede deshacer.")) return;
    await deleteAllUploads();
    await refresh();
    onSelect?.("accumulated");
  }

  return (
    <aside className="w-72 shrink-0 border-r border-slate-200 bg-white flex flex-col">
      <div className="p-4 border-b border-slate-200">
        <label
          htmlFor="file-input"
          className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-lg p-4 cursor-pointer hover:border-brand-500 hover:bg-brand-50/40 transition"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); handleFile(e.dataTransfer.files?.[0]); }}
        >
          {loading ? (
            <Loader2 className="animate-spin text-brand-600" size={24} />
          ) : (
            <Upload size={24} className="text-slate-400" />
          )}
          <p className="mt-2 text-xs text-slate-600 text-center">
            {loading ? "Procesando…" : "Arrastra o haz clic para subir (.xls/.xlsx)"}
          </p>
          <input id="file-input" ref={inputRef} type="file" accept=".xls,.xlsx" className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])} />
        </label>
        {error && <div className="mt-2 p-2 text-xs bg-red-50 text-red-700 rounded border border-red-200">{error}</div>}
      </div>

      <div className="p-3 border-b border-slate-200">
        <button
          onClick={() => onSelect?.("accumulated")}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition ${
            sourceId === "accumulated" ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-700 hover:bg-brand-100"
          }`}
        >
          <Layers size={16} /> Acumulado global
          <span className="ml-auto text-xs opacity-80">{uploads.length}</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="px-3 pt-3 pb-1 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase">Archivos</span>
          {uploads.length > 0 && (
            <button onClick={handleClear} className="text-xs text-red-600 hover:text-red-700" title="Borrar todos">
              <Trash2 size={14} />
            </button>
          )}
        </div>
        {uploads.length === 0 ? (
          <p className="px-3 py-4 text-xs text-slate-400">Aún no has subido archivos.</p>
        ) : (
          <ul className="px-2 pb-3 space-y-1">
            {uploads.map((u) => {
              const active = sourceId === u.id;
              return (
                <li key={u.id}>
                  <div
                    className={`group flex items-start gap-2 px-2 py-2 rounded-lg cursor-pointer text-sm ${
                      active ? "bg-brand-100 text-brand-900" : "hover:bg-slate-100"
                    }`}
                    onClick={() => onSelect?.(u.id)}
                  >
                    <FileText size={14} className="mt-0.5 shrink-0 text-slate-500" />
                    <div className="flex-1 min-w-0">
                      <div className="truncate text-xs font-medium">{u.filename}</div>
                      <div className="text-[10px] text-slate-500 truncate">{u.rango}</div>
                      <div className="text-[10px] text-slate-400">{u.filas.toLocaleString("es-CO")} filas</div>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(u.id); }}
                      className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700"
                      title="Eliminar"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
