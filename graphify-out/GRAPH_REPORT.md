# Graph Report - /home/jose/procovar/sucursal-analitics  (2026-07-26)

## Corpus Check
- 66 files · ~59,295 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 681 nodes · 1412 edges · 41 communities (38 shown, 3 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 51 edges (avg confidence: 0.83)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Frontend Src Components
- Frontend Src Components
- Main
- Readme Sessionstore
- Package
- Sucursal Store
- Utils
- Auth Store
- Repository Uploadrepository
- Excel Export
- Vendedores
- Automatizar Ventas
- Por Gestor Actualizado
- Enrich
- Automatizar Parranda
- Metasgestorreport
- Clientes Analisis
- Superpowers Specs
- Requirements
- Vps Docker Compose
- Make Ranking
- Specs 2026 06
- Calendario Rationale
- Metas Gestor
- Diario
- Automatizar Productos
- Ranking
- Specs 2026 06
- Local Local
- Local
- Readme
- Automatizar Market
- Clientes Punto 1
- Proyecto Automatizar Productos
- Ecosystem Config

## God Nodes (most connected - your core abstractions)
1. `enrich_for_sucursal()` - 28 edges
2. `cn()` - 28 edges
3. `gestor_keys()` - 24 edges
4. `only_valid()` - 22 edges
5. `formatNumber()` - 20 edges
6. `AuthStore` - 19 edges
7. `ReportData` - 16 edges
8. `UploadRepository` - 16 edges
9. `SucursalStore` - 16 edges
10. `formatMoney()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `useCurrency() USD/CUP display conversion` --semantically_similar_to--> `Paleta de colores de los reportes`  [AMBIGUOUS] [semantically similar]
  HANDOFF.md → PROYECTO.md
- `sucursales table` --conceptually_related_to--> `analitics-api service (FastAPI, network alias 'backend')`  [AMBIGUOUS]
  docs/superpowers/specs/2026-06-02-auth-multisucursal-design.md → deploy/vps/docker-compose.yml
- `Migracion Parquet+JSON -> PostgreSQL (analytics pandas intacto)` --conceptually_related_to--> `ANALITICS service on VPS (systemd gunicorn, no DB, JSON + PEDIDO API)`  [AMBIGUOUS]
  docs/superpowers/specs/2026-06-02-auth-multisucursal-design.md → HANDOFF.md
- `Event-driven sin polling (colas Bull in/out)` --semantically_similar_to--> `Cola domicilios BullMQ (reemplaza el polling de SyncJob)`  [INFERRED] [semantically similar]
  HANDOFF.md → deploy/vps/DEPLOY-VPS.md
- `JWT strategy (HS256 access 30min + refresh UUID 7d)` --semantically_similar_to--> `SSE ephemeral ticket auth (EventSource sends no headers)`  [INFERRED] [semantically similar]
  docs/superpowers/specs/2026-06-02-auth-multisucursal-design.md → HANDOFF.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Redis-backed scaling architecture (colas + pub/sub + cache)** — deploy_vps_deploy_vps_redis_rationale, deploy_vps_deploy_vps_import_csv_queue, deploy_vps_deploy_vps_domicilios_queue, deploy_vps_deploy_vps_sse_pubsub, deploy_vps_deploy_vps_redis_cache, deploy_vps_docker_compose_redis, handoff_redis_rollout [EXTRACTED 1.00]
- **Analitics authentication flow (login -> JWT -> refresh -> scoped requests)** — docs_superpowers_specs_2026_06_02_auth_multisucursal_design_loginpage, docs_superpowers_specs_2026_06_02_auth_multisucursal_design_api_js_interceptors, docs_superpowers_specs_2026_06_02_auth_multisucursal_design_routers_auth, docs_superpowers_specs_2026_06_02_auth_multisucursal_design_services_auth, docs_superpowers_specs_2026_06_02_auth_multisucursal_design_schema_refresh_tokens, docs_superpowers_specs_2026_06_02_auth_multisucursal_design_jwt_strategy, docs_superpowers_specs_2026_06_02_auth_multisucursal_design_authcontext [EXTRACTED 1.00]
- **Multi-sucursal isolation model across spec, app and deployment** — docs_superpowers_specs_2026_06_02_auth_multisucursal_design_isolation_guarantee, docs_superpowers_specs_2026_06_02_auth_multisucursal_design_schema_ventas_rows, docs_superpowers_specs_2026_06_02_auth_multisucursal_design_roles_matrix, proyecto_modelo_sucursal, app_readme_api_endpoints, deploy_local_deploy_local_sucursal_codigo, deploy_vps_deploy_vps_cutover_centralizado [INFERRED 0.85]

## Communities (41 total, 3 thin omitted)

### Community 0 - "Frontend Src Components"
Cohesion: 0.06
Nodes (68): api, base(), deleteAllUploads(), deleteUpload(), downloadExport(), getClientesAnalisis(), getDashboard(), getDiario() (+60 more)

### Community 1 - "Frontend Src Components"
Cohesion: 0.06
Nodes (61): addGestor(), createSucursal(), createUser(), deleteGestor(), deleteSucursal(), deleteUser(), getSucursal(), getSucursalId() (+53 more)

### Community 2 - "Main"
Cohesion: 0.06
Nodes (36): _aggregate_dashboards(), all_dashboard(), all_periods(), _allowed_sucursales_full(), _compute_dashboard(), _eff_scoped(), export_module(), _get_source() (+28 more)

### Community 3 - "Readme Sessionstore"
Cohesion: 0.06
Nodes (39): SessionStore en memoria (TTL 2h), Orden obligatorio: backfill sucursalId antes de importar geo, Guard de configuracion (formula + punto de partida), Flujo de costo de domicilio (pull PEDIDO -> cotiza -> writeback), Prisma 7 driver adapter requerido en los scripts .mjs, Cola SyncJob DB-backed ('redis sin redis') + pagina /sync por SSE, Warehouse de pesos por VPN WireGuard (10.188.2.2:3001), Caddy sin buffering para SSE (flush_interval -1, X-Accel-Buffering) (+31 more)

### Community 4 - "Package"
Cohesion: 0.05
Nodes (36): dependencies, axios, clsx, lucide-react, react, react-dom, recharts, devDependencies (+28 more)

### Community 5 - "Sucursal Store"
Cohesion: 0.13
Nodes (19): Valores por defecto del dominio.  IMPORTANTE: estos valores son solo *semillas*, _eff(), config_accumulated(), config_for_period(), config_for_report(), default_metas(), default_parametros(), default_sucursal_config() (+11 more)

### Community 6 - "Utils"
Cohesion: 0.13
Nodes (28): build_alias_map(), detect_gestor(), detect_gestor_punto(), detect_size(), extract_vendor_segment(), find_col(), is_malta(), is_parranda() (+20 more)

### Community 7 - "Auth Store"
Cohesion: 0.14
Nodes (11): AuthStore, _b64d(), _b64e(), hash_password(), normalize_role(), Path, Autenticación y usuarios (solo librería estándar).  - Contraseñas: PBKDF2-HMAC-S, Lectura de una sucursal. (+3 more)

### Community 8 - "Repository Uploadrepository"
Cohesion: 0.19
Nodes (11): ReportData, _df_for_parquet(), _df_to_report(), OverlapError, DataFrame, Path, _ranges_overlap(), Repositorio persistente de reportes subidos, aislado por sucursal (parquet + ind (+3 more)

### Community 9 - "Excel Export"
Cohesion: 0.19
Nodes (21): export_all(), export_clientes_analisis(), export_market(), export_parranda_facturas(), export_productos(), export_ranking(), export_ventas(), _formats() (+13 more)

### Community 10 - "Vendedores"
Cohesion: 0.19
Nodes (17): _desglose_formato_general(), gestor_keys(), only_valid(), DataFrame, Claves de gestores activos de la sucursal (orden de inserción)., compute_market(), Timestamp, Servicio Market: HL y CCC semanal (S1-S5) por gestor con cuotas y semáforos. (+9 more)

### Community 11 - "Automatizar Ventas"
Cohesion: 0.12
Nodes (9): detect_gestor_from_obs(), detect_product_group(), extract_vendor_segment(), normalize_for_match(), DataFrame, Series, Clasifica una transaccion en su grupo comercial., sort_df() (+1 more)

### Community 12 - "Por Gestor Actualizado"
Cohesion: 0.16
Nodes (11): build_resumen(), build_totales_vendedor(), detect_gestor_from_obs(), extract_vendor_segment(), month_progress_factor(), normalize_for_match(), pct(), DataFrame (+3 more)

### Community 13 - "Enrich"
Cohesion: 0.17
Nodes (13): detect_product_group(), Clasifica una fila en un grupo comercial (dinámico por sucursal)., compute_clientes_punto(), Servicio Clientes Punto: clientes identificados con '!!' en la Nota., enrich_for_sucursal(), _match_gestor_from_seg(), Enriquecimiento dinámico del reporte según la config efectiva de una sucursal., Devuelve un nuevo DataFrame enriquecido con las columnas dinámicas.      `eff` = (+5 more)

### Community 14 - "Automatizar Parranda"
Cohesion: 0.14
Nodes (7): detect_gestor_from_obs(), extract_vendor_segment(), normalize_for_match(), DataFrame, Series, sort_df(), sum_hectolitros()

### Community 15 - "Metasgestorreport"
Cohesion: 0.24
Nodes (12): activeFormatos(), Bar(), barColor(), CumplTable(), Delta(), FMT_LABEL, FMT_TONE, GeneralTable() (+4 more)

### Community 16 - "Clientes Analisis"
Cohesion: 0.23
Nodes (10): _clean_text(), compute_clientes_analisis(), _pivot(), DataFrame, Series, Análisis de clientes por vendedor.  Para cada vendedor y para la oficina complet, Pivote clientes×SKU en dólares, ordenado por total de cliente (desc)., fetch_order_counts() (+2 more)

### Community 17 - "Superpowers Specs"
Cohesion: 0.23
Nodes (12): settings table (JSONB config por sucursal), services/settings_store.py backed by DB (merge logic unchanged), automatizar_market.py (reporte MARKET HL/CCC), automatizar_parranda.py (reporte PARRANDA), automatizar_ventas.py (reporte VENTAS), Calculadora de Metas (HL) por sucursal, Comision gestor 1% / supervisor 10%, Grupos comerciales (PARRANDA / IMPORTACIONES / CONSIGNACION / TECNOLOGIA Y KAPITAL / OTRO) (+4 more)

### Community 18 - "Requirements"
Cohesion: 0.27
Nodes (11): Backend dependency stack (FastAPI + pandas + openpyxl/xlrd/xlsxwriter + httpx), sucursal-backend service (dev/standalone compose), sucursal-frontend service (nginx :8080 -> backend:8000), Best-effort PEDIDO integration (PEDIDO_API_URL + SERVICE_API_KEY), SPA shell (#root + /src/main.jsx entry), analitics columna Pedidos (PEDIDO_API_URL + SERVICE_API_KEY + httpx), analitics-api service (FastAPI, network alias 'backend'), analitics-front service (Vite -> nginx, proxy /api a backend) (+3 more)

### Community 19 - "Vps Docker Compose"
Cohesion: 0.27
Nodes (10): Layout vps-deploy/ con los 3 repos como hermanos, Guia de despliegue VPS centralizado (Docker + Redis + colas), caddy service (TLS automatico, reverse proxy por subdominio), delivery service (Next standalone :3000), delivery-sync worker service (Dockerfile.worker, sync-queue.mjs), pedido-api service (Express + Prisma 7, :8400), pedido-front service (Vite -> nginx :5000), postgres service (2 bases via initdb) (+2 more)

### Community 20 - "Make Ranking"
Cohesion: 0.24
Nodes (5): detect_gestor_from_obs(), extract_vendor_segment(), normalize_for_match(), Escribe un bloque de ranking con medallas para top 3., write_ranking_block()

### Community 21 - "Specs 2026 06"
Cohesion: 0.28
Nodes (9): Acumulacion diaria y source 'accumulated', Clientes Punto (identificados por NOMBRE!! en la nota), loader.only_valid_gestores(df, gestores) parametrizado por sucursal, services/repository.py rewritten to SQL (add/get/list/delete/accumulated), uploads table, Data flow: Upload Excel (JWT -> loader -> repository.add), Deteccion de gestor por segmento V- de la columna Nota, services/loader (carga y normaliza el crudo) (+1 more)

### Community 22 - "Calendario Rationale"
Cohesion: 0.32
Nodes (7): Días LABORALES del mes (los de la calculadora de metas).  La meta de cada SKU se, Máscara de días trabajados (lun..dom). Por defecto lun-vie., Días laborales TOTALES del mes (entre los que se reparte la meta mensual)., Días laborales TRANSCURRIDOS del mes hasta `report_date` (inclusive)., weekmask(), working_days(), working_days_elapsed()

### Community 23 - "Metas Gestor"
Cohesion: 0.36
Nodes (7): compute_metas_gestor(), _fmt_code(), _meta_code(), _pct(), Cumplimiento por vendedor y general, por FORMATO (P1500/P500/P330/M1500/M330), r, PARRANDA-1500' -> 'P1500', 'MALTA-330' -> 'M330'., `dia` (YYYY-MM-DD): día "de corte" del estudio. Por defecto, el último con datos

### Community 24 - "Diario"
Cohesion: 0.48
Nodes (6): compute_diario(), _dow_es(), _pct(), Timestamp, Servicio Diario: meta diaria vs. real por día, con comparación contra el día ant, _working_days()

### Community 25 - "Automatizar Productos"
Cohesion: 0.38
Nodes (3): detect_gestor(), extract_vendor_segment(), normalize_text()

### Community 26 - "Ranking"
Cohesion: 0.60
Nodes (5): compute_ranking(), Timestamp, Servicio de Ranking: general, semanal y diario acumulado (por importe)., _week_label(), _week_start()

### Community 27 - "Specs 2026 06"
Cohesion: 0.33
Nodes (6): Login por roles admin/user con Bearer token, AdminPanel.jsx (tabs Sucursales | Usuarios), 4 roles (admin / general_analytics / analytics / supervisor), routers/admin.py (CRUD sucursales + users, admin only), sucursales table, Modelo de usuario (role admin|user, sucursales asignadas)

### Community 28 - "Local Local"
Cohesion: 0.33
Nodes (6): Next bajo PM2 no carga .env (exportar antes de pm2 start), Guia de despliegue LOCAL (Windows + PM2, un servidor por sucursal), Procesos PM2 por sucursal (api, front, delivery, delivery-sync, analitics), ANALITICS service on VPS (systemd gunicorn, no DB, JSON + PEDIDO API), BUILD_STANDALONE=1 required for delivery build, PROCOVAR three-app stack (PEDIDO / delivery / analitics)

### Community 29 - "Local"
Cohesion: 0.33
Nodes (6): SUCURSAL_CODIGO scoping (local = codigo, centralizado = vacio), Dos modos de despliegue (local por sucursal vs VPS centralizado), Cutover a centralizado (consolidar historicos, aislamiento por sucursal), Cola db-restore (upsert idempotente de backups), Isolation guarantee (WHERE sucursal_id derivado del JWT), ventas_rows table (sucursal_id = primary isolation key)

### Community 30 - "Readme"
Cohesion: 0.40
Nodes (5): API REST de analitics (auth / sucursales / sources / export), Analisis de Clientes por Vendedor (clientes x SKU en $), services/excel_export (xlsx con formato de los scripts), make_ranking.py (reporte RANKING), Ranking por importe (general / semanal / diario acumulado)

### Community 33 - "Proyecto Automatizar Productos"
Cohesion: 0.67
Nodes (3): automatizar_productos.py (reporte PRODUCTOS), Dias laborales y deberia_ir (bdate_range + weekmask), Metas de productos CES (importaciones)

## Ambiguous Edges - Review These
- `ANALITICS service on VPS (systemd gunicorn, no DB, JSON + PEDIDO API)` → `Migracion Parquet+JSON -> PostgreSQL (analytics pandas intacto)`  [AMBIGUOUS]
  docs/superpowers/specs/2026-06-02-auth-multisucursal-design.md · relation: conceptually_related_to
- `useCurrency() USD/CUP display conversion` → `Paleta de colores de los reportes`  [AMBIGUOUS]
  HANDOFF.md · relation: semantically_similar_to
- `analitics-api service (FastAPI, network alias 'backend')` → `sucursales table`  [AMBIGUOUS]
  docs/superpowers/specs/2026-06-02-auth-multisucursal-design.md · relation: conceptually_related_to

## Knowledge Gaps
- **56 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+51 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `ANALITICS service on VPS (systemd gunicorn, no DB, JSON + PEDIDO API)` and `Migracion Parquet+JSON -> PostgreSQL (analytics pandas intacto)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `useCurrency() USD/CUP display conversion` and `Paleta de colores de los reportes`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **What is the exact relationship between `analitics-api service (FastAPI, network alias 'backend')` and `sucursales table`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `dias_laborales()` connect `Enrich` to `Por Gestor Actualizado`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `ReportData` connect `Repository Uploadrepository` to `Main`, `Sucursal Store`, `Utils`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _56 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Frontend Src Components` be split into smaller, more focused modules?**
  _Cohesion score 0.06323396567299007 - nodes in this community are weakly interconnected._