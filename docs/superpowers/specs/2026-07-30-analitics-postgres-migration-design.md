# Diseño: analitics → PostgreSQL (Fase 1 de "analitics motor de reportes")

**Fecha:** 2026-07-30
**Estado:** Aprobado (diseño). Pendiente: instalar deps en el venv (root) antes de implementar.

## Objetivo

Migrar el almacenamiento de `sucursal-analitics` de **archivos JSON/parquet** a **PostgreSQL** (la DB `analitics` que ya existe pero no se usa). Es la base de la visión mayor: que analitics sea el motor central de reportes y pueda **guardar los datos y reportes en DB** (para re-consultas instantáneas) y luego alimentarse solo desde Ventra.

Esta Fase 1 es SOLO el cambio de storage. No incluye Ventra ni el cache de reportes (fases 2-3, specs aparte).

## Contexto actual

- analitics (FastAPI) corre en el VPS como `analitics.service` (systemd), gunicorn en `127.0.0.1:3010`, WorkingDir `/root/analitics/app/backend` (= `~/projects/analitics`, editable por jose).
- Ingesta hoy: subida **manual de Excel** (`POST /api/sucursales/{sid}/uploads`) → `load_report` → `repository.add` → guarda `.parquet` + `index.json` por sucursal.
- Storage actual (3 módulos en `services/`):
  - `auth_store.py` → `users.json` (usuarios: username, hash pbkdf2, role, sucursales).
  - `sucursal_store.py` → `sucursales.json` (config por sucursal: gestores, metas, parámetros, overrides mensuales).
  - `repository.py` → `uploads/{sid}/index.json` + `{uid}.parquet` (reportes subidos: metadata + filas de venta).
- Los reportes (`ventas.py`, `ranking.py`, `metas_gestor.py`, `productos.py`, etc.) computan sobre un **DataFrame** (columnas STD_COLS: Operacion, Fecha, Socio, Mercancia, Grupo, Cantidad, Importe, SumaTotal, Nota).
- DB destino ya lista: `analitics` (usuario `analitics_app`, `127.0.0.1:5432`, creds en `.env` `DATABASE_URL`). Conecta, puede CREATE TABLE, está vacía.

## Enfoque elegido (A): SQLAlchemy + JSONB para config, normalizado para ventas

Config de sucursal (anidada, cambia seguido) → columna **JSONB** (casi sin remodelar). Filas de venta → tabla normalizada (filtrables por fecha en SQL). Alternativas descartadas: todo JSONB (ventas no filtrables en SQL), todo normalizado (mucho trabajo, frágil, YAGNI).

## Modelo de datos (4 tablas en DB `analitics`)

| Tabla | Columnas | Notas |
|---|---|---|
| `analytics_user` | id, username (unique), password_hash, role, sucursales (JSONB array), created_at | hash pbkdf2 igual que hoy |
| `analytics_sucursal` | sid (PK, text), nombre, config (JSONB: gestores/metas/parametros/metas_mensuales), updated_at | config flexible intacta |
| `analytics_upload` | id (PK), sid (FK), filename, uploaded_at, rango, filas, date_min, date_max, source | metadata (bytes, NO el archivo) |
| `analytics_upload_row` | id, upload_id (FK, ON DELETE CASCADE), operacion, fecha (date, INDEX), socio, mercancia, grupo, cantidad, importe, suma, nota | las ventas; reemplaza parquet |

Índices: `analytics_upload_row(upload_id)`, `analytics_upload_row(fecha)`, `analytics_upload(sid)`.

## Componentes

**`services/db.py`** (nuevo): engine + sessionmaker SQLAlchemy desde `DATABASE_URL`; los 4 modelos; `init_db()` = `Base.metadata.create_all()` (llamado al arrancar — sin Alembic, es simple). Session por request (context manager).

**Reescritura de los 3 stores — MISMA interfaz pública** (main.py y los servicios de reporte NO cambian):
- `auth_store.py`: reemplaza lectura/escritura de `users.json` por queries a `analytics_user`. Se CONSERVA sin tocar: `hash_password`, `verify_password`, emisión/validación de tokens HMAC (son algoritmo, no storage).
- `sucursal_store.py`: reemplaza `sucursales.json` por `analytics_sucursal` (config en JSONB). La lógica sobre el dict de config queda igual; solo cambia el load/save.
- `repository.py`: reemplaza `index.json` + parquet por `analytics_upload` + `analytics_upload_row`. `add()` inserta metadata + filas y **descarta el archivo subido** (ni parquet ni original). `load_df(sid, desde, hasta)` = `pd.read_sql` (filtra por fecha en SQL, devuelve DataFrame STD_COLS). `list()`/`get()`/`remove()` = queries.

**`migrate_json_to_pg.py`** (script único, idempotente): lee `users.json` → usuarios; `sucursales.json` → configs; por cada sucursal, `index.json` + cada `.parquet` → `analytics_upload` + `analytics_upload_row`. Idempotente (upsert / skip si ya existe). NO borra los JSON/parquet.

## Requisito clave: guardar solo DATOS, nunca archivos

Al subir un reporte: leer → parsear → insertar filas en `analytics_upload_row` → **descartar el archivo**. No se guarda `.parquet` ni el original. El disco no crece por archivos; solo por datos (que es lo consultable). Requisito explícito del usuario.

## Testing

- **Migración**: correr el script → verificar conteos (usuarios, sucursales, uploads, filas) == lo que había en JSON/parquet.
- **Smoke end-to-end** (en el VPS): `sudo systemctl restart analitics` → login con usuario migrado → abrir un reporte (ventas/ranking/metas) → mismo resultado que antes de migrar.
- **Rollback**: si algo falla, `git revert` del código + restart → vuelve a JSON (los archivos siguen ahí). Los JSON/parquet se conservan ~1 semana; luego se limpian.

## Orden de ejecución

1. (root) `sudo /root/analitics/app/backend/.venv/bin/pip install sqlalchemy psycopg2-binary`.
2. `init_db()` crea las 4 tablas.
3. Correr `migrate_json_to_pg.py`.
4. Smoke test.
5. Si OK → deploy (restart). Backups JSON/parquet quedan de respaldo.

## Fuera de alcance (specs futuros)

- Fase 2: sync automático de ventas desde **Ventra** (`/branch-entries`), periódico (cron), reemplazando el Excel manual.
- Fase 3: cachear reportes computados en DB (re-consultas instantáneas).
- Fase 4: PEDIDO/delivery delegan sus reportes a analitics.
