# Auth + Multi-Sucursal Design Spec
**Date:** 2026-06-02  
**Project:** Sucursal Analytics  
**Status:** Approved

---

## Overview

Add authentication, user management, and multi-branch (sucursal) support to Sucursal Analytics. Currently the app serves one branch with no auth. After this change it will serve 8+ branches, each fully isolated, with role-based access control.

**Database migration:** All data moves from Parquet files + JSON to PostgreSQL. Analytics computation logic (pandas services) stays untouched — only the data loading and persistence layers change.

**Frontend:** All new and changed UI components must be built using the `frontend-design` skill to produce production-quality, non-generic interfaces.

---

## Scope

### In scope
- PostgreSQL as the sole data store (replaces Parquet + index.json + settings.json)
- JWT authentication (access + refresh tokens)
- 4 roles: admin, general_analytics, analytics, supervisor
- Full CRUD for sucursales (admin only)
- Full CRUD for users (admin only)
- Per-sucursal data and config isolation
- Admin panel UI (sucursales + users)
- Login page UI
- Sucursal selector in header (admin/general_analytics only)
- Seed admin user on first boot

### Out of scope
- Email/password reset flows
- OAuth / SSO
- Audit logs
- Per-user notification preferences

---

## Database Schema (PostgreSQL)

### `sucursales`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | gen_random_uuid() |
| nombre | VARCHAR(120) | Display name |
| ciudad | VARCHAR(80) | City |
| activa | BOOLEAN | default true |
| created_at | TIMESTAMPTZ | default now() |

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| username | VARCHAR(60) UNIQUE | Login credential |
| password_hash | VARCHAR(256) | bcrypt |
| role | ENUM | admin, general_analytics, analytics, supervisor |
| sucursal_id | UUID FK → sucursales | NULL for admin and general_analytics |
| activo | BOOLEAN | default true |
| created_at | TIMESTAMPTZ | |

### `uploads`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| sucursal_id | UUID FK → sucursales | NOT NULL |
| filename | VARCHAR(200) | Original Excel filename |
| date_min | DATE | First sale date in file |
| date_max | DATE | Last sale date in file |
| filas | INTEGER | Row count |
| uploaded_at | TIMESTAMPTZ | |
| uploaded_by | UUID FK → users | |

### `ventas_rows`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGSERIAL PK | |
| sucursal_id | UUID FK → sucursales | NOT NULL — primary isolation key |
| upload_id | UUID FK → uploads | NOT NULL |
| fecha | DATE | |
| operacion | VARCHAR(40) | |
| socio | VARCHAR(120) | |
| mercancia | VARCHAR(200) | |
| grupo | VARCHAR(100) | |
| cantidad | NUMERIC | |
| importe | NUMERIC | |
| nota | TEXT | |
| gestor | VARCHAR(60) | GestorDetectado (enriched by loader.py) |
| gestor_punto | VARCHAR(60) | GestorPunto (enriched by loader.py) |
| size_ml | SMALLINT | 330, 500, 1500 or NULL |
| is_malta | BOOLEAN | |
| is_parranda | BOOLEAN | |
| hectolitros | NUMERIC | Pre-computed by loader.py |

**Index:** `CREATE INDEX ON ventas_rows (sucursal_id, fecha)` — fast period filtering per branch.

**Deduplication:** on upload, rows are deduplicated on (operacion, fecha, socio, mercancia, cantidad, importe) within the same sucursal before insert, matching current Parquet behavior.

### `settings`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| sucursal_id | UUID FK → sucursales UNIQUE | One row per branch |
| config | JSONB | Same structure as current settings.json |
| updated_at | TIMESTAMPTZ | |

The JSONB structure is identical to the current `settings.json` format: `meta_hectolitros_total`, `meta_dinero_total`, `metas_productos_ces`, `gestores`, `trabaja_sabado`, `metas_mensuales`. This means `settings_store.py` logic for merging monthly overrides reuses unchanged.

### `refresh_tokens`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → users | |
| token_hash | VARCHAR(256) | bcrypt of the raw token |
| expires_at | TIMESTAMPTZ | now() + 7 days |
| created_at | TIMESTAMPTZ | |

---

## Roles & Permissions

| Capability | admin | general_analytics | analytics | supervisor |
|-----------|-------|-------------------|-----------|------------|
| View analytics — own sucursal | ✅ | ✅ | ✅ | ✅ |
| View analytics — all sucursales | ✅ | ✅ | ❌ | ❌ |
| Upload Excel — own sucursal | ✅ | ✅ | ✅ | ✅ |
| Upload Excel — any sucursal | ✅ | ✅ | ❌ | ❌ |
| Edit settings — own sucursal | ✅ | ✅ | ✅ | ✅ |
| Edit settings — any sucursal | ✅ | ✅ | ❌ | ❌ |
| CRUD sucursales | ✅ | ❌ | ❌ | ❌ |
| CRUD users | ✅ | ❌ | ❌ | ❌ |

`analytics` and `supervisor` have identical permissions. Both are scoped to one sucursal.

`sucursal_id` in the JWT payload is `null` for admin and general_analytics (they select a sucursal at runtime via query param or header). For analytics/supervisor it is their fixed branch UUID.

---

## Authentication

### JWT Strategy
- **Access token:** HS256, expires 30 minutes. Payload: `{sub: user_id, role, sucursal_id, exp}`.
- **Refresh token:** random UUID stored hashed in `refresh_tokens`, expires 7 days.
- **Storage:** both tokens in `localStorage` on the frontend.
- **Interceptor:** axios request interceptor adds `Authorization: Bearer <access_token>` to every API call. On 401 response, attempts one silent refresh before redirecting to login.

### Seed admin
On backend startup, if no users exist in the database, create one:
- username: `admin`
- password: value of env var `ADMIN_INIT_PASSWORD`
- role: `admin`
- sucursal_id: NULL

### Password policy
- Minimum 8 characters enforced on the backend.
- bcrypt with cost factor 12.

---

## Backend Changes

### New modules

**`app/backend/db/`**
- `models.py` — SQLAlchemy ORM models for all 6 tables above.
- `session.py` — `engine`, `SessionLocal`, `get_db` FastAPI dependency.
- `init_db.py` — `create_all()` called at app startup + seed admin logic.

**`app/backend/services/auth.py`**
- `create_access_token(user)` → signed JWT string
- `create_refresh_token(db, user_id)` → stores hash in DB, returns raw token
- `verify_access_token(token)` → returns payload dict or raises 401
- `hash_password(plain)` / `verify_password(plain, hashed)`
- `get_current_user(token, db)` → FastAPI dependency returning User ORM object

**`app/backend/routers/auth.py`**
```
POST /api/auth/login     body: {username, password} → {access_token, refresh_token, user}
POST /api/auth/refresh   body: {refresh_token}       → {access_token}
POST /api/auth/logout    body: {refresh_token}        → deletes token from DB
GET  /api/auth/me        header: Bearer token         → current user info
```

**`app/backend/routers/admin.py`** — requires `role == admin`
```
GET    /api/admin/sucursales
POST   /api/admin/sucursales        body: {nombre, ciudad}
PUT    /api/admin/sucursales/{id}   body: {nombre?, ciudad?, activa?}
DELETE /api/admin/sucursales/{id}

GET    /api/admin/users
POST   /api/admin/users             body: {username, password, role, sucursal_id?}
PUT    /api/admin/users/{id}        body: {username?, password?, role?, sucursal_id?, activo?}
DELETE /api/admin/users/{id}
```

### Changed modules

**`services/repository.py`**  
Replace Parquet + index.json with SQL.  
- `add(report, sucursal_id, user_id, force)` → INSERT into `uploads` + bulk INSERT into `ventas_rows`. Overlap check via SQL date range query scoped to `sucursal_id`.  
- `get(upload_id, sucursal_id)` → SELECT from `ventas_rows` WHERE upload_id AND sucursal_id → return DataFrame → wrap in `ReportData`.  
- `list(sucursal_id)` → SELECT from `uploads` WHERE sucursal_id.  
- `delete(upload_id, sucursal_id)` → DELETE ventas_rows + uploads row.  
- `accumulated(sucursal_id)` → SELECT * FROM ventas_rows WHERE sucursal_id → deduplicate → return ReportData. When `sucursal_id` is `None` (admin/general_analytics with "Todas las sucursales" selected), selects ALL rows across all branches — this is the cross-sucursal global accumulated view.  
- The `ReportData` dataclass and all analytics services that consume it are **unchanged**.

**`services/settings_store.py`**  
Replace JSON file with DB.  
- `load(sucursal_id, db)` → SELECT config FROM settings WHERE sucursal_id. If no row, return `default_config()`.  
- `save(sucursal_id, cfg, db)` → UPSERT settings row.  
- `reset(sucursal_id, db)` → write `default_config()` back.  
- Merge logic (`_merge_with_defaults`, `config_for_period`, `config_for_report`) is **unchanged**.

**`core/constants.py`**  
- `GESTORES_PERMITIDOS` and `GESTORES_CONFIG` remain as seed/default values used when creating a new sucursal.  
- Services that currently iterate `GESTORES_PERMITIDOS` (`ventas.py`, `productos.py`) will receive the gestores list from `config["gestores"]` instead of the constant, so each sucursal's gestores are independent.

**`services/loader.py`** — small change  
- `only_valid_gestores(df)` currently filters using `GESTORES_PERMITIDOS` (the global constant). It must accept an optional `gestores` list parameter so each sucursal's gestor list is used instead. Callers (`ventas.py`, `productos.py`) pass `config["gestores"].keys()`. Default remains `GESTORES_PERMITIDOS` for backwards compatibility during transition.

**`main.py`**  
- Register new routers: `auth`, `admin`.  
- Add `get_current_user` dependency to all existing endpoints.  
- All `/api/uploads` and `/api/sources/` endpoints receive `sucursal_id` from the JWT (for analytics/supervisor) or from a `?sucursal_id=` query param (for admin/general_analytics).  
- The `source_id` duality (UUID | "accumulated") is preserved — only scoped per sucursal now.

**`requirements.txt`** — add:
```
sqlalchemy==2.0.x
psycopg2-binary==2.9.x
python-jose[cryptography]==3.3.x
passlib[bcrypt]==1.7.x
python-dotenv==1.0.x
```

**`docker-compose.yml`** — add `db` service:
```yaml
db:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: sucursal_analytics
    POSTGRES_USER: app
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  restart: unless-stopped

backend:
  environment:
    DATABASE_URL: postgresql://app:${POSTGRES_PASSWORD}@db:5432/sucursal_analytics
    JWT_SECRET: ${JWT_SECRET}
    ADMIN_INIT_PASSWORD: ${ADMIN_INIT_PASSWORD}
```

Add `.env` file (git-ignored) with `POSTGRES_PASSWORD`, `JWT_SECRET`, `ADMIN_INIT_PASSWORD`.

---

## Frontend Changes

> **All new and changed UI components must be built using the `frontend-design` skill** to produce production-quality, distinctive interfaces.

### New components

**`LoginPage.jsx`**  
Standalone full-screen page. Username + password form. Calls `api.login()`, stores tokens in localStorage, redirects to dashboard. Shown when no valid token exists.

**`AuthContext.jsx`**  
React context providing: `user` (current user object), `logout()`, `sucursalId` (active sucursal — from JWT for analytics/supervisor; from selector state for admin/general_analytics).

**`AdminPanel.jsx`**  
Tab-based panel (Sucursales | Usuarios) visible only to admin role.  
- Sucursales tab: table with nombre, ciudad, activa, user count. Create/edit modal, delete with confirmation.  
- Usuarios tab: table with username, role, sucursal, activo. Create/edit modal (includes role + sucursal assignment), delete with confirmation.

### Changed components

**`App.jsx`**  
- Wrap with `<AuthContext>`. If no token → render `<LoginPage>`. Otherwise render existing layout.  
- Add sucursal selector in header (dropdown) — visible only for admin and general_analytics. Value stored in `AuthContext.sucursalId`.  
- Add "Admin" tab/button in header — visible only for admin.  
- All existing tab content is unchanged.

**`api.js`**  
- Add axios request interceptor: attach `Authorization: Bearer <access_token>` header.  
- Add axios response interceptor: on 401, attempt token refresh via `POST /api/auth/refresh`. On refresh failure, clear tokens and redirect to login.  
- New functions: `login({username, password})`, `logout()`, `getMe()`, `getToken()`, `setTokens()`, `clearTokens()`.  
- Existing functions (uploadFile, getDashboard, etc.) are **unchanged** — they just gain the auth header automatically.  
- All requests for analytics/supervisor are scoped by the server using their JWT. For admin/general_analytics, a `sucursal_id` query param is added when a specific sucursal is selected.

**`UploadPanel.jsx`**  
No logic change. If the user is admin/general_analytics and has a sucursal selected, uploads go to that sucursal. The sucursal context is injected via `AuthContext`.

**`SettingsPanel.jsx`**  
No logic change. Settings are now loaded/saved scoped to the active sucursal via `AuthContext.sucursalId`.

---

## Data Flow: Upload Excel

```
1. User uploads Excel via UploadPanel
2. Frontend sends POST /api/uploads (multipart) with Bearer token
3. Backend: get_current_user() → extracts user + sucursal_id from JWT
4. loader.py parses Excel → ReportData (DataFrame) [unchanged]
5. repository.add(report, sucursal_id, user_id) checks for date overlaps in DB
6.   → INSERT uploads row
7.   → Bulk INSERT ventas_rows (all DataFrame rows with sucursal_id tagged)
8. Return upload metadata to frontend
```

## Data Flow: View Analytics

```
1. Frontend sends GET /api/sources/{id}/ventas?mes=2026-05 with Bearer token
2. Backend: get_current_user() → sucursal_id from JWT (or query param for admin)
3. repository.get(id, sucursal_id) → SELECT ventas_rows → DataFrame → ReportData
4. compute_ventas(report, config) [unchanged pandas logic]
5. Return JSON
```

---

## Isolation Guarantee

All DB queries that touch `uploads`, `ventas_rows`, or `settings` include a `WHERE sucursal_id = ?` clause derived from the authenticated user's JWT. The server never trusts a client-provided sucursal_id for scoped roles — it always comes from the token. Only admin and general_analytics may pass a `sucursal_id` override.

---

## Implementation Notes

- **No migration needed** for existing data: since this is a new Postgres instance, the single existing branch (Camaguey) must be seeded: one sucursal row + its settings + re-upload any existing Parquet data through the new import flow, or provide a one-time migration script that reads the old `data/` directory and imports into Postgres.
- **`core/constants.py`** gestores/targets remain as the default values used when creating a sucursal with no custom settings.
- **Thread safety**: the `threading.Lock()` in the old repository and settings_store is replaced by PostgreSQL transactions.
- **Dev workflow** (no Docker): `DATABASE_URL=postgresql://...` in a local `.env`. Run `uvicorn main:app --reload` as before.
