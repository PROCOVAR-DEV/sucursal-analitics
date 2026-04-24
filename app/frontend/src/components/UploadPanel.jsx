import { Upload, FileSpreadsheet, Loader2 } from "lucide-react";
import { useRef, useState } from "react";
import { uploadReport } from "../api.js";

export default function UploadPanel({ onUploaded }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  async function handleFile(file) {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await uploadReport(file);
      onUploaded(res);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-6">
      <div className="max-w-xl w-full card">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-brand-50 rounded-lg text-brand-600">
            <FileSpreadsheet size={28} />
          </div>
          <div>
            <h2 className="text-xl font-bold">Cargar Reporte de Venta</h2>
            <p className="text-sm text-slate-500">
              Sube el archivo diario (.xls o .xlsx) para generar el tablero.
            </p>
          </div>
        </div>

        <label
          htmlFor="file"
          className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-xl p-10 cursor-pointer hover:border-brand-500 hover:bg-brand-50/40 transition"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFile(e.dataTransfer.files?.[0]);
          }}
        >
          {loading ? (
            <Loader2 className="animate-spin text-brand-600" size={36} />
          ) : (
            <Upload size={36} className="text-slate-400" />
          )}
          <p className="mt-3 text-sm text-slate-600">
            {loading ? "Procesando…" : "Arrastra aquí o haz clic para seleccionar"}
          </p>
          <p className="text-xs text-slate-400 mt-1">Formatos: .xls, .xlsx</p>
          <input
            id="file"
            ref={inputRef}
            type="file"
            accept=".xls,.xlsx"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
        </label>

        {error && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-200">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
