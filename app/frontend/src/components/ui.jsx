// Primitivos de UI reutilizables (estética shadcn, sin dependencias extra).
import { Building2, Check, ChevronDown, ChevronsUpDown, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function cn(...xs) {
  return xs.flat().filter(Boolean).join(" ");
}

function useDropdown() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (triggerRef.current?.contains(e.target) || menuRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const onEsc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onEsc); };
  }, [open]);
  return { open, setOpen, triggerRef, menuRef };
}

// Panel del dropdown en un PORTAL con posición fija: flota sobre todo,
// nunca crece ni recorta la tabla/contenedor donde vive el trigger.
function Menu({ triggerRef, menuRef, open, onClose, align = "left", children }) {
  const [style, setStyle] = useState(null);
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const r = triggerRef.current.getBoundingClientRect();
    const GAP = 6, MIN = 140, PAD = 8;

    // Vertical: si abajo no cabe (última fila de una tabla, p. ej.) se voltea
    // hacia arriba. La altura máxima se ajusta al hueco real que haya.
    const below = window.innerHeight - r.bottom - GAP;
    const above = r.top - GAP;
    const flip = below < MIN && above > below;
    const maxHeight = Math.max(MIN, (flip ? above : below) - PAD);

    // Horizontal: no dejar que se salga por los bordes de la ventana.
    const width = Math.round(r.width);
    let horizontal;
    if (align === "right") {
      horizontal = { right: Math.max(PAD, Math.round(window.innerWidth - r.right)) };
    } else {
      const maxLeft = window.innerWidth - width - PAD;
      horizontal = { left: Math.round(Math.min(Math.max(PAD, r.left), Math.max(PAD, maxLeft))) };
    }

    setStyle({
      position: "fixed",
      ...(flip
        ? { bottom: Math.round(window.innerHeight - r.top + GAP) }
        : { top: Math.round(r.bottom + GAP) }),
      minWidth: width,
      maxWidth: Math.round(window.innerWidth - PAD * 2),
      maxHeight: Math.round(maxHeight),
      zIndex: 1000,
      ...horizontal,
    });
  }, [open, align, triggerRef]);
  useEffect(() => {
    if (!open) return;
    const onScroll = (e) => { if (!menuRef.current?.contains(e.target)) onClose(); };
    window.addEventListener("resize", onClose);
    window.addEventListener("scroll", onScroll, true);
    return () => { window.removeEventListener("resize", onClose); window.removeEventListener("scroll", onScroll, true); };
  }, [open, onClose, menuRef]);
  if (!open || !style) return null;
  return createPortal(
    <div ref={menuRef} style={style} onMouseDown={(e) => e.stopPropagation()}
      className="max-h-64 overflow-auto scroll-thin rounded-xl bg-white shadow-pop border border-slate-200 p-1 animate-fade-in">
      {children}
    </div>,
    document.body
  );
}

// Select single custom (reemplaza <select> nativo) para fondos claros.
export function Select({ value, options, onChange, placeholder = "Seleccionar", className, width = "w-full", align = "left" }) {
  const { open, setOpen, triggerRef, menuRef } = useDropdown();
  const current = options.find((o) => o.value === value);
  return (
    <div className={cn("relative", width, className)}>
      <button ref={triggerRef} type="button" onClick={() => setOpen((o) => !o)}
        className="input flex items-center justify-between gap-2 cursor-pointer w-full text-left">
        <span className={cn("truncate", !current && "text-slate-400")}>{current?.label || placeholder}</span>
        <ChevronDown size={15} className={cn("text-slate-400 shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      <Menu triggerRef={triggerRef} menuRef={menuRef} open={open} onClose={() => setOpen(false)} align={align}>
        {options.map((o) => (
          <button key={o.value} type="button" onClick={() => { onChange(o.value); setOpen(false); }}
            className={cn("w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm text-left transition whitespace-nowrap",
              o.value === value ? "bg-brand-50 text-brand-700 font-semibold" : "text-slate-700 hover:bg-slate-100")}>
            <Check size={14} className={cn("shrink-0", o.value === value ? "opacity-100" : "opacity-0")} />
            {o.label}
          </button>
        ))}
      </Menu>
    </div>
  );
}

// Select con BARRA DE BÚSQUEDA. Para listas largas donde escribir a mano es
// incómodo y propenso a errores (ej. la clave del gestor de una sucursal).
export function SearchSelect({
  value, options, onChange,
  placeholder = "Seleccionar", searchPlaceholder = "Buscar…",
  emptyText = "Sin opciones", disabled = false,
  className, width = "w-full", align = "left",
}) {
  const { open, setOpen, triggerRef, menuRef } = useDropdown();
  const [q, setQ] = useState("");
  const inputRef = useRef(null);
  const current = options.find((o) => o.value === value);

  // Al abrir: limpia la búsqueda y enfoca el campo (se puede teclear de una).
  useEffect(() => {
    if (!open) return;
    setQ("");
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    return () => clearTimeout(t);
  }, [open]);

  const needle = q.trim().toLowerCase();
  const shown = needle
    ? options.filter((o) =>
        String(o.label).toLowerCase().includes(needle) || String(o.value).toLowerCase().includes(needle))
    : options;

  return (
    <div className={cn("relative", width, className)}>
      <button ref={triggerRef} type="button" disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        className={cn("input flex items-center justify-between gap-2 w-full text-left",
          disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer")}>
        <span className={cn("truncate", !current && "text-slate-400")}>{current?.label || placeholder}</span>
        <ChevronsUpDown size={15} className="text-slate-400 shrink-0" />
      </button>
      <Menu triggerRef={triggerRef} menuRef={menuRef} open={open} onClose={() => setOpen(false)} align={align}>
        <div className="sticky top-0 p-1 -m-1 mb-1 bg-white">
          <input ref={inputRef} className="input input-sm w-full" placeholder={searchPlaceholder}
            value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && shown.length === 1) { onChange(shown[0].value); setOpen(false); }
            }} />
        </div>
        {shown.length === 0 && <div className="px-2.5 py-2 text-xs text-slate-400">{emptyText}</div>}
        {shown.map((o) => (
          <button key={o.value} type="button" onClick={() => { onChange(o.value); setOpen(false); }}
            className={cn("w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm text-left transition whitespace-nowrap",
              o.value === value ? "bg-brand-50 text-brand-700 font-semibold" : "text-slate-700 hover:bg-slate-100")}>
            <Check size={14} className={cn("shrink-0", o.value === value ? "opacity-100" : "opacity-0")} />
            {o.label}
          </button>
        ))}
      </Menu>
    </div>
  );
}

// MultiSelect colapsable (checklist en popover) — para asignar sucursales, etc.
export function MultiSelect({ value = [], options, onChange, placeholder = "Ninguna", width = "w-48", align = "left" }) {
  const { open, setOpen, triggerRef, menuRef } = useDropdown();
  const sel = options.filter((o) => value.includes(o.value));
  const label = sel.length === 0 ? placeholder : sel.length <= 2 ? sel.map((s) => s.label).join(", ") : `${sel.length} seleccionadas`;
  const toggle = (v) => onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <div className={cn("relative", width)}>
      <button ref={triggerRef} type="button" onClick={() => setOpen((o) => !o)}
        className="input flex items-center justify-between gap-2 cursor-pointer w-full text-left">
        <span className={cn("truncate", sel.length === 0 && "text-slate-400")}>{label}</span>
        <ChevronDown size={15} className={cn("text-slate-400 shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      <Menu triggerRef={triggerRef} menuRef={menuRef} open={open} onClose={() => setOpen(false)} align={align}>
        {options.length === 0 && <div className="px-2.5 py-2 text-xs text-slate-400">Sin opciones</div>}
        {options.map((o) => {
          const on = value.includes(o.value);
          return (
            <button key={o.value} type="button" onClick={() => toggle(o.value)}
              className={cn("w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-sm text-left transition whitespace-nowrap", on ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100")}>
              <span className={cn("grid place-items-center w-4 h-4 rounded border shrink-0", on ? "bg-brand-600 border-brand-600 text-white" : "border-slate-300")}>
                {on && <Check size={12} />}
              </span>
              {o.label}
            </button>
          );
        })}
      </Menu>
    </div>
  );
}

// Selector custom para el header (sucursal). Reemplaza el <select> nativo.
export function Picker({ value, options, onChange, icon: Icon = Building2, placeholder = "Seleccionar" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    function onDoc(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    function onEsc(e) { if (e.key === "Escape") setOpen(false); }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onEsc); };
  }, []);
  const current = options.find((o) => o.value === value);
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 pl-2.5 pr-2 py-1.5 rounded-lg bg-white/15 hover:bg-white/25 text-white text-sm font-semibold transition min-w-[150px]">
        <Icon size={15} className="opacity-90 shrink-0" />
        <span className="truncate flex-1 text-left">{current?.label || placeholder}</span>
        <ChevronsUpDown size={15} className="opacity-80 shrink-0" />
      </button>
      {open && (
        <div className="absolute right-0 mt-1.5 min-w-[200px] max-h-72 overflow-auto scroll-thin rounded-xl bg-white shadow-pop border border-slate-200 p-1 z-50 animate-fade-in">
          {options.map((o) => (
            <button key={o.value} onClick={() => { onChange(o.value); setOpen(false); }}
              className={cn("w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm text-left transition",
                o.value === value ? "bg-brand-50 text-brand-700 font-semibold" : "text-slate-700 hover:bg-slate-100")}>
              <Check size={15} className={cn("shrink-0", o.value === value ? "opacity-100" : "opacity-0")} />
              <span className="truncate">{o.label}</span>
              {o.hint && <span className="ml-auto text-[11px] text-slate-400">{o.hint}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Panel({ className, children }) {
  return <div className={cn("panel", className)}>{children}</div>;
}

export function PanelHeader({ title, sub, right, icon: Icon }) {
  return (
    <div className="card-header">
      <div className="flex items-center gap-2.5 min-w-0">
        {Icon && <span className="grid place-items-center w-8 h-8 rounded-lg bg-brand-50 text-brand-600 shrink-0"><Icon size={16} /></span>}
        <div className="min-w-0">
          <h3 className="card-title truncate">{title}</h3>
          {sub && <p className="card-sub truncate">{sub}</p>}
        </div>
      </div>
      {right}
    </div>
  );
}

const VARIANTS = {
  primary: "btn-primary", outline: "btn-outline", ghost: "btn-ghost",
  subtle: "btn-subtle", danger: "btn-danger",
};
export function Button({ variant = "primary", size, icon: Icon, children, className, ...rest }) {
  return (
    <button className={cn(VARIANTS[variant] || "btn-primary", size === "sm" && "btn-sm", className)} {...rest}>
      {Icon && <Icon size={size === "sm" ? 13 : 15} />} {children}
    </button>
  );
}

export function IconButton({ variant = "ghost", icon: Icon, className, size = 15, ...rest }) {
  return (
    <button className={cn("btn-icon", VARIANTS[variant] || "btn-ghost", className)} {...rest}>
      <Icon size={size} />
    </button>
  );
}

export function Field({ label, hint, className, children, ...rest }) {
  return (
    <label className={cn("block", className)}>
      {label && <span className="label">{label}</span>}
      {children || <input className="input" {...rest} />}
      {hint && <span className="block mt-1 text-[10px] text-slate-400">{hint}</span>}
    </label>
  );
}

export function Segmented({ options, value, onChange, className }) {
  return (
    <div className={cn("inline-flex items-center gap-1 p-1 rounded-lg bg-slate-100", className)}>
      {options.map((o) => (
        <button key={o.value} className={cn("seg", value === o.value && "seg-active")} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Badge({ tone = "slate", children, className }) {
  return <span className={cn(`badge-${tone}`, className)}>{children}</span>;
}

export function StatTile({ label, value, hint, accent = "slate", icon: Icon }) {
  const ring = {
    brand: "text-brand-600", green: "text-emerald-600", amber: "text-amber-600",
    red: "text-red-600", slate: "text-slate-700",
  }[accent];
  return (
    <div className="kpi-card">
      <div className="flex items-center justify-between">
        <span className="kpi-label">{label}</span>
        {Icon && <Icon size={15} className="text-slate-300" />}
      </div>
      <span className={cn("kpi-value", ring)}>{value}</span>
      {hint && <span className="text-xs text-slate-400">{hint}</span>}
    </div>
  );
}

export function Empty({ children }) {
  return <div className="card text-center text-slate-400 text-sm py-10">{children}</div>;
}

// Notificación flotante: card fija abajo-derecha, sobre todo, con botón cerrar.
export function Toast({ msg, onClose }) {
  if (!msg) return null;
  const tone = msg.t || msg.type;
  const ok = tone === "ok";
  const warn = tone === "warn";
  const border = ok ? "border-emerald-200" : warn ? "border-amber-200" : "border-red-200";
  const iconBg = ok ? "bg-emerald-100 text-emerald-600" : warn ? "bg-amber-100 text-amber-600" : "bg-red-100 text-red-600";
  return createPortal(
    <div className="fixed bottom-5 right-5 z-[2000] max-w-sm animate-fade-in">
      <div className={cn("flex items-start gap-3 pl-3 pr-2 py-3 rounded-xl border shadow-pop bg-white", border)}>
        <span className={cn("grid place-items-center w-7 h-7 rounded-lg shrink-0 mt-0.5", iconBg)}>
          {ok ? <Check size={16} /> : <span className="font-bold">!</span>}
        </span>
        <p className="text-sm text-slate-700 flex-1 pt-0.5">{msg.m || msg.text}</p>
        <button onClick={onClose} className="text-slate-300 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 shrink-0" title="Cerrar">
          <X size={15} />
        </button>
      </div>
    </div>,
    document.body
  );
}
