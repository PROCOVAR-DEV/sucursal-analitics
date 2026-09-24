/**
 * Usar algo sin importarlo NO se ve hasta que esa línea se ejecuta.
 *
 * `VendedoresView` llamaba a `cn(...)` sin importarlo, dentro de la tabla «Sus metas por
 * cantidad» — que sólo se dibuja si el vendedor TIENE metas por cantidad. Como nunca
 * había ninguna, esa rama no corría y el fallo estuvo dormido semanas. El día que se
 * guardó el primer plan por producto, la pantalla de «Quién vende» se cayó entera con un
 * `cn is not defined`.
 *
 * Esto recorre los .jsx y señala lo que se usa de `ui.jsx` o `Kpi.jsx` sin haberlo
 * importado ni declarado en el propio fichero. Sale con 1 para poder ponerlo en el build.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const MODULOS = ["src/components/ui.jsx", "src/components/Kpi.jsx"];

function ficheros(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return n === "node_modules" ? [] : ficheros(p);
    return p.endsWith(".jsx") ? [p] : [];
  });
}

const exportados = new Map();
for (const mod of MODULOS) {
  const txt = readFileSync(mod, "utf8");
  for (const m of txt.matchAll(/export (?:function|const) (\w+)/g)) exportados.set(m[1], mod.split("/").pop());
}

let fallos = 0;
for (const f of ficheros("src")) {
  if (MODULOS.some((m) => f.endsWith(m.split("/").pop()))) continue;
  const src = readFileSync(f, "utf8");
  const importados = new Set();
  for (const m of src.matchAll(/import \{([^}]*)\} from/g)) {
    for (const n of m[1].split(",")) importados.add(n.trim().split(" as ")[0].trim());
  }
  const propios = new Set([...src.matchAll(/(?:function|const|let|class)\s+(\w+)/g)].map((m) => m[1]));

  for (const [nombre, mod] of exportados) {
    if (importados.has(nombre) || propios.has(nombre)) continue;
    if (new RegExp(String.raw`(?<![\w.])${nombre}\s*[({<]`).test(src)) {
      console.log(`${f}: usa «${nombre}» de ${mod} y NO lo importa`);
      fallos++;
    }
  }
}
console.log(fallos ? `\n${fallos} sitio(s) que revientan en cuanto se ejecute esa línea.` : "Imports: todo lo que se usa está importado.");
process.exit(fallos ? 1 : 0);
