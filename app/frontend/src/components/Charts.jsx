import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const PALETTE = ["#2563eb", "#16a34a", "#f59e0b", "#db2777", "#7c3aed", "#0891b2", "#ef4444"];

function fmt(v) {
  if (v === null || v === undefined || isNaN(v)) return "–";
  return Number(v).toLocaleString("es-CO", { maximumFractionDigits: 0 });
}

function CustomBarTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-sm">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.fill }}>
          {fmt(p.value)}
        </p>
      ))}
    </div>
  );
}

function CustomLineTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-sm max-w-xs">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.stroke }} className="flex justify-between gap-4">
          <span>{p.name}</span>
          <span className="font-medium">{fmt(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

export function BarCard({ title, data, xKey, yKey, subtitle, tone = "#2563eb" }) {
  return (
    <div className="card">
      <div className="mb-2">
        <h3 className="font-semibold text-slate-800">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      <div className="h-72">
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip content={<CustomBarTooltip />} />
            <Bar dataKey={yKey} radius={[6, 6, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/**
 * El ranking, en BARRAS HORIZONTALES. Sustituye a la tarta.
 *
 * # Por que se quito la tarta
 *
 * Repartia el ranking entre mas de VEINTICINCO vendedores. Las etiquetas se montaban unas
 * encima de otras y la mitad eran ilegibles; y aunque se leyeran, comparar angulos de
 * porciones parecidas es imposible. Una tarta deja de funcionar pasadas seis porciones.
 *
 * En barras horizontales el nombre cabe entero, se ordena solo y se compara de un vistazo,
 * que es justo lo que se viene a hacer aqui: ver quien va delante.
 *
 * # Top N y "otros"
 *
 * Con veinticinco barras la pantalla se va de alto y las de abajo no se miran nunca.
 * Se enseñan las `tope` primeras y el resto se suma en una barra gris "otros", que ademas
 * dice cuantos son: asi el total sigue cuadrando y nadie cree que faltan vendedores.
 *
 * # Un solo color
 *
 * El color aqui no significa nada —son personas, no categorias— asi que gastar veinticinco
 * colores solo hace ruido. Van todas del color de marca, y la unica distinta es "otros",
 * que si es otra cosa.
 */
export function RankingBarras({ title, subtitle, data, nameKey, valueKey, tope = 10, unidad = "" }) {
  const ordenadas = [...(data || [])].sort((a, b) => (b[valueKey] || 0) - (a[valueKey] || 0));
  const cabeza = ordenadas.slice(0, tope);
  const resto = ordenadas.slice(tope);
  const filas = cabeza.map((d) => ({ nombre: d[nameKey], valor: d[valueKey], otros: false }));

  if (resto.length) {
    filas.push({
      nombre: `Otros (${resto.length})`,
      valor: resto.reduce((s, d) => s + (d[valueKey] || 0), 0),
      otros: true,
    });
  }

  // El alto crece con las filas: con alto fijo, once barras salen aplastadas y una sola
  // sale como una franja gigante.
  const alto = Math.max(200, filas.length * 30 + 30);

  return (
    <div className="card">
      <div className="mb-2">
        <h3 className="font-semibold text-slate-800">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      <div style={{ height: alto }}>
        <ResponsiveContainer>
          <BarChart data={filas} layout="vertical" margin={{ left: 4, right: 56, top: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={fmt} />
            {/* 130 px de ancho: los nombres son largos y sin esto salen cortados con "…" */}
            <YAxis type="category" dataKey="nombre" width={130} tick={{ fontSize: 11 }} interval={0} />
            <Tooltip content={<CustomBarTooltip />} cursor={{ fill: "#f1f5f9" }} />
            <Bar dataKey="valor" radius={[0, 5, 5, 0]}>
              {filas.map((f, i) => (
                <Cell key={i} fill={f.otros ? "#94a3b8" : "#2563eb"} />
              ))}
              {/* El numero al final de cada barra: sin el hay que ir al eje y estimar. */}
              <LabelList
                dataKey="valor"
                position="right"
                formatter={(v) => `${fmt(v)}${unidad}`}
                style={{ fontSize: 11, fill: "#475569" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function LineCard({ title, data, xKey, series, subtitle }) {
  return (
    <div className="card">
      <div className="mb-2">
        <h3 className="font-semibold text-slate-800">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      <div className="h-80">
        <ResponsiveContainer>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip content={<CustomLineTooltip />} />
            <Legend />
            {series.map((s, i) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
