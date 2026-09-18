/**
 * Un hook DESPUES de un `return` dentro del mismo componente deja la pantalla en blanco.
 *
 * No es teoria: el 17/09/2026 dos `useState`/`useEffect` quedaron debajo del
 * `if (!gDraft) return null;` de `Metas`, y a los supervisores —que entran directos a
 * `config/metas`— la aplicacion ENTERA se les quedaba en blanco. React no avisa en
 * pantalla: desmonta el arbol y el error solo se ve en la consola del navegador.
 *
 * Esto recorre los .jsx contando llaves: dentro de cada funcion que empiece por
 * mayuscula (un componente), si aparece un `return` a profundidad 1 y DESPUES una
 * llamada a un hook, se señala. Sale con codigo 1 para poder ponerlo antes del build.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const HOOK = /(?:^|[^.\w])(useState|useEffect|useMemo|useCallback|useRef|useReducer|useLayoutEffect)\s*\(/;
const INICIO = /(?:^|\s)(?:export\s+default\s+)?function\s+([A-Z]\w*)\s*\(|const\s+([A-Z]\w*)\s*=\s*(?:\([^)]*\)|\w+)\s*=>/;

function ficheros(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return n === "node_modules" ? [] : ficheros(p);
    return p.endsWith(".jsx") ? [p] : [];
  });
}

let fallos = 0;
for (const f of ficheros("src")) {
  const lineas = readFileSync(f, "utf8").split("\n");
  let dentro = null, base = 0, prof = 0, salioYa = 0, enComentario = false;
  lineas.forEach((l, i) => {
    // Los comentarios de bloque no cuentan: hablan de hooks sin llamarlos.
    let codigo = l.replace(/\/\/.*$/, "");
    if (enComentario) { const fin = codigo.indexOf("*/"); if (fin === -1) return; codigo = codigo.slice(fin + 2); enComentario = false; }
    const ini = codigo.indexOf("/*");
    if (ini !== -1) { enComentario = !codigo.includes("*/", ini); codigo = codigo.slice(0, ini) + (enComentario ? "" : codigo.slice(codigo.indexOf("*/", ini) + 2)); }

    const m = codigo.match(INICIO);
    if (m && prof === 0) { dentro = m[1] || m[2]; base = prof; salioYa = 0; }

    if (dentro && prof === base + 1) {
      if (/^\s*(if\s*\(.*\)\s*)?return\b/.test(codigo)) salioYa = i + 1;
      else if (salioYa && HOOK.test(codigo)) {
        console.log(`${f}:${i + 1}  ${dentro}: hook después del return de la línea ${salioYa}`);
        console.log(`    ${codigo.trim().slice(0, 100)}`);
        fallos++;
        salioYa = 0;   // uno por componente basta
      }
    }
    prof += (codigo.match(/\{/g) || []).length - (codigo.match(/\}/g) || []).length;
    if (dentro && prof <= base) dentro = null;
  });
}
console.log(fallos ? `\n${fallos} sitio(s) donde la pantalla se puede quedar en blanco.` : "Hooks: ningún return por delante.");
process.exit(fallos ? 1 : 0);
