# Sucursal Analytics — Documentación del proyecto

> Dashboard web (estilo Power BI) para analizar el **Reporte de Venta** diario de
> PROCOVAR y generar los reportes gerenciales (Ventas, Productos, Market, Parranda,
> Ranking) con el mismo formato y colores que los scripts de Python originales.
> Multi-sucursal, con login por roles y **toda la configuración dinámica**.

---

## 1. Qué es y de dónde sale

En la carpeta raíz (`sucursal-analitics/`) conviven:

- **Scripts Python originales** (fuente de verdad de los cálculos y del formato):
  - `automatizar_ventas.py` → reporte **VENTAS** (una hoja por gestor con KPIs, mix de
    ventas por grupo comercial, conversión blisters/pallets, detalle de facturas + hoja
    **Supervisor** consolidada). Genera archivos tipo `VENTAS-01-03-JULIO-2026.xlsx`.
  - `automatizar_productos.py` → reporte **PRODUCTOS** (hoja *Cumplimiento* de metas de
    importaciones, hoja *Resumen* con pie charts por grupo, una hoja por gestor).
  - `automatizar_market.py` → reporte **MARKET** (HL y CCC semanal S1–S5 con cuotas,
    curva de venta y semáforos por gestor; supervisor "Camaguey").
  - `automatizar_parranda.py` → reporte **PARRANDA** (solo PARRANDA + MALTA Guajira:
    hectolitros, blisters, pallets por gestor + Supervisor).
  - `make_ranking.py` → reporte **RANKING** (general, semanal, progreso diario con
    medallas 🥇🥈🥉 y gráfico de evolución acumulada).
  - `algoritmo_ventas_por_gestor_actualizado (1).py` → variante con metas por producto
    (P1500/P500/P330/M1500/M500/M330), meta acumulada por avance del mes, comisión 1%.
- **Excels de entrada (crudos)**: `RV JULIO 1-3.xls`, `RV JUNIO 1-29.xls`. Es el
  **Reporte de Ventas** exportado del sistema PROCOVAR: filas transaccionales.
- **Excel generado de ejemplo**: `VENTAS-01-03-JULIO-2026.xlsx` (salida de
  `automatizar_ventas.py`; su hoja **Supervisor** es el consolidado general).
- **App web**: `app/` (backend FastAPI + frontend React).

### El dato de entrada real
El **crudo** `RV JULIO 1-3.xls` es una sola hoja con encabezado en la fila 4. Columnas:

```
No. de Operación | Fecha/Hora | Mercancía | Grupo de la Mercancía | Nombre de socio |
Entidad | Cantidad | Medida | Precio de Venta | Importe | Suma Total | Nota
```

El **gestor (vendedor)** se identifica desde la columna **Nota**, que trae varios
segmentos, p. ej.:

```
P-PAP25-260701-1547; V-ALEXANDER PADRÓN HECAVARRÍA; C-CONSUMO PROPIO (ALEXANDER);
```

- `V-…` = **vendedor** (gestor). ← de aquí se saca el gestor.
- `C-…` = cliente. Puede contener otro nombre; por eso **hay que quedarse solo con el
  segmento `V-`** antes de detectar. (El loader original del app no lo hacía → riesgo
  de asignar mal el gestor. Corregido.)

Validado contra la hoja Supervisor del Excel generado (coincide exacto):

| Gestor | Total Venta |
|---|---|
| ALEXANDER | 14 889.65 |
| MAYLEN | 6 580.41 |
| DEYANIRA | 5 069.70 |
| GEORLIS | 4 774.10 |
| ERNESTO | 3 174.69 |
| JEAN MICHEL | 2 265.15 |
| ANDY | 1 233.83 |
| **TOTAL** | **37 987.53** |

---

## 2. Conceptos y cálculos del dominio

- **Hectolitros** = `Cantidad × SIZE_MULT[tamaño]`, con `SIZE_MULT = {330: 0.02,
  500: 0.03, 1500: 0.09}`. El tamaño se detecta del texto de la mercancía.
- **Producto cerveza**: `MALTA` (requiere "MALTA" + "GUAJIRA") o `PARRANDA`.
  Códigos de columna: `M330 M500 M1500 P330 P500 P1500`.
- **Pallets** = `Blisters(Cantidad) / UNITS_PER_PALLET[(producto,tamaño)]`, con
  `330→496, 500→336, 1500→110`.
- **Grupos comerciales** (para Productos/Market): `PARRANDA`, `IMPORTACIONES`,
  `CONSIGNACION`, `TECNOLOGIA Y KAPITAL`, resto `OTRO`. Se clasifican por el campo
  Grupo y por palabras clave de la Mercancía.
- **Metas de productos CES (importaciones)**: `ACEITE 1000, ARROZ 2500, AZUCAR 5000,
  REFRESCO 2418, SANTA ISABEL 8000` (unidades/mes).
- **Días laborales**: `pd.bdate_range` con weekmask según `trabaja_sabado/domingo`.
  `debería_ir = meta/dias_totales × dias_transcurridos`; delta verde/rojo.
- **Comisión**: gestor `1%` del importe; supervisor `10%` de las comisiones.
- **Ranking**: por importe. General (acumulado), semanal (lun–vie), diario acumulado;
  empates con `rank(method="min")`; podio 🥇🥈🥉.
- **Market (CCC)**: clientes únicos por semana; cuota semanal por curva de venta.

### Paleta de colores de los reportes (a replicar en los export)
- Títulos `#203864` / encabezados `#1F4E79` (texto blanco).
- Banda alterna `#D9E1F2`; bloque KPI naranja `#FCE4D6`; KPI verde `#E2EFDA`.
- OK verde `#C6EFCE`/`#006100`; mal rojo `#FFC7CE`/`#9C0006`; alerta amarillo `#FFEB9C`.
- Grupos: PARRANDA `#1F4E78`, IMPORTACIONES `#375623`, CONSIGNACION `#7B3900`,
  TECNOLOGIA Y KAPITAL `#4A1080`.
- Podio ranking: oro `#FFD700`, plata `#C0C0C0`, bronce `#CD7F32`.

---

## 3. Arquitectura de la app

```
app/
  backend/   FastAPI + pandas    (API REST, cálculo y export Excel con colores)
  frontend/  React + Vite + Tailwind + Recharts (dashboard + login)
```

### Backend (`app/backend/`)
- `core/` constantes por defecto y utilidades puras (detección gestor/tamaño/producto).
- `services/` lógica de negocio: `loader` (carga/normaliza el crudo), `ventas`,
  `productos`, `market`, `ranking`, `vendedores`, `clientes_analisis`
  (ranking de clientes × SKU en $, por vendedor y oficina), `excel_export`
  (genera los .xlsx con formato/colores de los scripts).
- `sucursales/` **(nuevo)** modelo multi-sucursal: cada sucursal tiene su config,
  gestores, metas y uploads independientes.
- `auth/` **(nuevo)** usuarios, login, roles y tokens (solo stdlib: pbkdf2 + hmac).

### Modelo de datos (todo dinámico y por sucursal)
Una **sucursal** contiene:
- `id`, `nombre` (p. ej. "Camagüey"), `supervisor_nombre`.
- **gestores**: `{clave: {nombre, sector, agencia, cuota_hl, cuota_ccc, aliases[], activo, metas_formato{}}}`
  — se pueden **agregar / editar / eliminar** (los trabajadores van y vienen).
  `metas_formato` = meta HL por SKU (`PARRANDA-1500`, `PARRANDA-330`, …), la llena la **Calculadora**.
- **metas**: `meta_hectolitros_total`, `meta_dinero_total`, `meta_ccc_total`,
  `metas_productos_ces{}`, más overrides `metas_mensuales["YYYY-MM"]`.
- **parámetros**: `size_mult`, `units_per_pallet`, `product_groups_keywords`,
  `comision_gestor_pct`, `comision_supervisor_pct`, `trabaja_sabado`, `curva_venta`,
  `frecuencia`. Todo editable desde la UI.
- **uploads**: reportes crudos subidos, aislados por sucursal.

Un **usuario** tiene: `username`, `password_hash`, `role` (`admin` | `user`),
`sucursales` asignadas. `admin` ve **todas** las sucursales; `user` solo la(s) suya(s).

> **Estado inicial**: se arranca con **una** sucursal (**Camagüey**) sembrada con los 7
> gestores y las metas reales, pero el modelo ya es multi-sucursal: agregar más
> sucursales no requiere reescribir nada.

---

## 4. Plan de trabajo

1. **Config dinámica por sucursal** — reemplazar constantes hardcodeadas por config
   editable (gestores CRUD, metas, factores, grupos).
2. **Multi-sucursal** — `sucursal_id` en uploads y en todos los endpoints; store de
   sucursales.
3. **Autenticación** — login, roles, gestión de usuarios, tokens firmados (stdlib).
4. **Corrección de cálculos** — extracción del segmento `V-`, detección dinámica de
   gestor por alias de cada sucursal, validación contra el Excel.
5. **Exports Excel** — módulos que reproducen Ventas/Productos/Market/Parranda/Ranking
   con el formato y los colores exactos de los scripts.
6. **Frontend** — pantalla de login, selector de sucursal, panel de administración
   (usuarios, gestores, metas, parámetros) y las vistas/descargas de reportes.
7. **Pruebas** — end-to-end con `RV JULIO 1-3.xls`, comparando contra
   `VENTAS-01-03-JULIO-2026.xlsx`.

---

## 5. Cómo correr (desarrollo)

```bash
# Backend
cd app/backend
python3 -m venv .venv --without-pip && source .venv/bin/activate
curl -sS https://bootstrap.pypa.io/get-pip.py | python   # si falta pip (PEP 668)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd app/frontend
npm install && npm run dev     # http://localhost:5173 (proxy /api → :8000)
```

Usuario admin por defecto: **admin / admin** (cambiar tras el primer login).

### Con Docker (producción / uso real)

```bash
cd app
# el frontend se sirve ya compilado; si tocas el frontend, primero:
#   cd frontend && npm run build
docker compose up -d --build
```

- Frontend en **http://localhost:8080** (nginx sirve `dist/` y proxya `/api` → backend:8000).
- Datos persistentes en el volumen `backend-data` (sucursales, usuarios, uploads).
- El backend siembra **admin/admin** y la sucursal **Camagüey** en el primer arranque.

---

## 6. Módulos destacados

- **Análisis de Clientes por Vendedor** — rankea los clientes por ventas ($) de mayor
  a menor; cada columna es un SKU comprado (en $), con total y nº de SKUs por cliente.
  Vista por vendedor y hoja "Oficina" (total). Identifica clientes valiosos, qué SKU
  escala más y oportunidades de venta cruzada. Exporta a Excel (una hoja por vendedor).
- **Calculadora de Metas (HL)** — por sucursal. Se ingresan **pallets por SKU** de cada
  vendedor y se calculan **blísters → hectolitros** con los factores dinámicos de la
  sucursal (`pallets × units_per_pallet × size_mult`). Al guardar, rellena la meta de HL
  de cada vendedor (`cuota_hl` + `metas_formato`) **y** el total de la sucursal
  (`meta_hectolitros_total`). Es la herramienta para el llenado de metas por vendedor y
  por sucursal.

