# analitics → PostgreSQL (Fase 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar el storage de `sucursal-analitics` de archivos JSON/parquet a PostgreSQL (DB `analitics`), sin cambiar el comportamiento de los reportes ni la API.

**Architecture:** Capa DB nueva con SQLAlchemy (4 tablas). Los 3 stores (`auth_store`, `sucursal_store`, `repository`) se reescriben POR DENTRO manteniendo su interfaz pública exacta, así main.py y los servicios de reporte no cambian. Config de sucursal en JSONB; ventas normalizadas. Un script migra los datos actuales. Al subir un reporte se guardan SOLO las filas, nunca el archivo.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2.0, psycopg2, pandas, PostgreSQL 16, pytest.

## Global Constraints

- **DB destino:** `analitics` en `127.0.0.1:5432`, usuario `analitics_app`. Connection string en `~/projects/analitics/app/backend/.env` variable `DATABASE_URL` (`postgresql://analitics_app:...@127.0.0.1:5432/analitics`). Ya conecta y puede CREATE TABLE.
- **Interfaz pública de los stores NO cambia.** Los métodos y sus firmas se conservan exactos (ver cada task). Si cambia una firma, es un bug del plan.
- **Al subir/agregar un reporte: guardar SOLO los datos (filas). NUNCA guardar el archivo** (ni parquet ni original).
- **NO borrar** los JSON/parquet existentes (respaldo). La migración solo LEE.
- **Nombres de tabla:** `analytics_user`, `analytics_sucursal`, `analytics_upload`, `analytics_upload_row`.
- **Formato del DataFrame de ventas (STD_COLS)** que consumen los reportes, EXACTO: columnas `Operacion, Fecha, Socio, Mercancia, Grupo, Cantidad, Importe, SumaTotal, Nota`. `repository.load_df`/`get`/`accumulated` deben devolver un `ReportData` con un DataFrame de esas columnas (igual que hoy desde parquet).
- **Dónde corre:** el código vive en `~/projects/analitics/app/backend` del VPS (= `/root/analitics`, editable por jose). Los tests corren EN EL VPS con el venv: `cd ~/projects/analitics/app/backend && .venv/bin/python -m pytest tests/ -v`. Deploy: `sudo systemctl restart analitics`.
- **Dev loop:** editar en el repo local `sucursal-analitics/` → `scp` el archivo a `jose@72.60.115.124:projects/analitics/...` → correr pytest por ssh. (O editar directo en el VPS.)
- **Deps del venv (root las instala una vez, ya hecho sqlalchemy+psycopg2; falta pytest):** `sudo /root/analitics/app/backend/.venv/bin/pip install pytest`.
- **Commits:** frecuentes, uno por task. Rama `dev`.

---

## File Structure

- `app/backend/services/db.py` — **NUEVO**: engine, `SessionLocal`, `Base`, los 4 modelos ORM, `init_db()`, helper `session_scope()`.
- `app/backend/services/auth_store.py` — **MODIFICA**: `AuthStore` usa SQLAlchemy. Conserva intactas `hash_password`, `verify_password`, `make_token`, `verify_token` (algoritmo) y los métodos estáticos de permisos.
- `app/backend/services/sucursal_store.py` — **MODIFICA**: `SucursalStore` usa SQLAlchemy (config en JSONB). Conserva toda la lógica de defaults/merge sobre el dict.
- `app/backend/services/repository.py` — **MODIFICA**: `UploadRepository` usa SQLAlchemy. `add()` inserta filas y descarta el archivo. `load_df`/`get`/`accumulated` arman el DataFrame con `pd.read_sql`.
- `app/backend/migrate_json_to_pg.py` — **NUEVO**: script único idempotente JSON/parquet → postgres.
- `app/backend/main.py` — **MODIFICA**: llamar `init_db()` al arrancar; instanciar los stores sin depender de `base_dir` (o ignorarlo).
- `app/backend/requirements.txt` — **MODIFICA**: añadir `sqlalchemy>=2.0`, `psycopg2-binary`, `pytest`.
- `app/backend/tests/conftest.py` — **NUEVO**: fixture de sesión con rollback por test.
- `app/backend/tests/test_db.py`, `test_auth_store.py`, `test_sucursal_store.py`, `test_repository.py`, `test_migration.py` — **NUEVO**.

---

## Task 1: Capa DB (modelos + engine + init) y harness de tests

**Files:**
- Create: `app/backend/services/db.py`
- Create: `app/backend/tests/conftest.py`
- Create: `app/backend/tests/test_db.py`
- Modify: `app/backend/requirements.txt` (añadir sqlalchemy, psycopg2-binary, pytest)

**Interfaces:**
- Produces: `Base`, `engine`, `SessionLocal`, `session_scope()` (contextmanager → Session), `init_db()`; modelos `User`, `Sucursal`, `Upload`, `UploadRow` con las columnas del spec.

- [ ] **Step 1: Escribir el test que falla** — `app/backend/tests/test_db.py`

```python
from services.db import init_db, session_scope, Sucursal

def test_init_db_crea_tablas_y_roundtrip():
    init_db()  # idempotente
    with session_scope() as s:
        s.query(Sucursal).delete()
        s.add(Sucursal(sid="cam", nombre="Camaguey", config={"gestores": {}}))
    with session_scope() as s:
        row = s.query(Sucursal).filter_by(sid="cam").one()
        assert row.nombre == "Camaguey"
        assert row.config == {"gestores": {}}
```

- [ ] **Step 2: Correr y ver que falla**

Run (en el VPS): `cd ~/projects/analitics/app/backend && .venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: services.db` o tabla no existe).

- [ ] **Step 3: Implementar `services/db.py`**

```python
"""Capa de base de datos (PostgreSQL vía SQLAlchemy) para analitics."""
from __future__ import annotations
import os
from contextlib import contextmanager
from datetime import datetime, date

from sqlalchemy import (create_engine, String, Integer, Float, Date, DateTime,
                        Text, ForeignKey, Index)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship

DATABASE_URL = os.environ["DATABASE_URL"]  # del .env (analitics_app@127.0.0.1:5432/analitics)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "analytics_user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="usuario")
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # {sucursales, nombre, gestor}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Sucursal(Base):
    __tablename__ = "analytics_sucursal"
    sid: Mapped[str] = mapped_column(String(80), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Upload(Base):
    __tablename__ = "analytics_upload"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)  # uuid como hoy
    sid: Mapped[str] = mapped_column(String(80), ForeignKey("analytics_sucursal.sid"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[str] = mapped_column(String(40), nullable=False)
    rango: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    filas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    date_min: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_max: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="upload")
    rows: Mapped[list["UploadRow"]] = relationship(cascade="all, delete-orphan", back_populates="upload")


class UploadRow(Base):
    __tablename__ = "analytics_upload_row"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(String(60), ForeignKey("analytics_upload.id", ondelete="CASCADE"), index=True)
    operacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    socio: Mapped[str | None] = mapped_column(Text, nullable=True)
    mercancia: Mapped[str | None] = mapped_column(Text, nullable=True)
    grupo: Mapped[str | None] = mapped_column(Text, nullable=True)
    cantidad: Mapped[float | None] = mapped_column(Float, nullable=True)
    importe: Mapped[float | None] = mapped_column(Float, nullable=True)
    suma: Mapped[float | None] = mapped_column(Float, nullable=True)
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    upload: Mapped["Upload"] = relationship(back_populates="rows")


def init_db() -> None:
    """Crea las tablas si no existen. Idempotente."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope():
    """Sesión transaccional: commit al salir bien, rollback si hay excepción."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
```

- [ ] **Step 4: Escribir `tests/conftest.py`** (carga el `.env` y hace disponible `session_scope`; cada test limpia sus datos)

```python
import os
from pathlib import Path
import pytest

# Cargar DATABASE_URL del .env si no está en el entorno.
_env = Path(__file__).resolve().parents[1] / ".env"
if "DATABASE_URL" not in os.environ and _env.exists():
    for line in _env.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()

@pytest.fixture(autouse=True)
def _init():
    from services.db import init_db
    init_db()
```

- [ ] **Step 5: Añadir deps a `requirements.txt`**

Añadir líneas: `sqlalchemy>=2.0`, `psycopg2-binary`, `pytest`. (Ya instaladas en el venv salvo pytest → `sudo /root/analitics/app/backend/.venv/bin/pip install pytest`.)

- [ ] **Step 6: Correr y ver que pasa**

Run: `cd ~/projects/analitics/app/backend && .venv/bin/python -m pytest tests/test_db.py -v`
Expected: PASS. Verificar en DB: `psql "$DATABASE_URL" -c "\dt"` muestra las 4 tablas `analytics_*`.

- [ ] **Step 7: Commit**

```bash
git add app/backend/services/db.py app/backend/tests/conftest.py app/backend/tests/test_db.py app/backend/requirements.txt
git commit -m "feat(analitics): capa DB postgres (modelos + init) + harness tests"
```

---

## Task 2: `auth_store` → postgres

**Files:**
- Modify: `app/backend/services/auth_store.py`
- Create: `app/backend/tests/test_auth_store.py`

**Interfaces (se conservan EXACTAS):**
- `AuthStore(base_dir)` (acepta `base_dir` por compat pero ya no lo usa).
- `list() -> list[dict]`, `get_raw(username) -> dict|None`, `create(username, password, role, sucursales, nombre="", gestor=None) -> dict`, `update(username, patch) -> dict|None`, `delete(username) -> bool`, `authenticate(username, password) -> dict|None`, `make_token(username) -> str`, `verify_token(token) -> dict|None`.
- Se CONSERVAN sin tocar: `hash_password`, `verify_password` (módulo-nivel), y los estáticos `can_access/can_write_metas/can_manage/allowed_sucursales`.
- El "dict de usuario" que devuelven los métodos mantiene sus claves actuales: `{username, role, sucursales, nombre, gestor}` (SIN el hash).

- [ ] **Step 1: Test que falla** — `tests/test_auth_store.py`

```python
import uuid
from services.auth_store import AuthStore

def _store():
    return AuthStore(base_dir=None)

def test_create_authenticate_update_delete():
    st = _store()
    u = "t_" + uuid.uuid4().hex[:8]
    creado = st.create(u, "clave123", "supervisor", ["cam"], nombre="Tester")
    assert creado["username"] == u and creado["role"] == "supervisor"
    assert "password" not in creado and "password_hash" not in creado
    assert st.authenticate(u, "clave123")["username"] == u
    assert st.authenticate(u, "malo") is None
    st.update(u, {"role": "usuario", "sucursales": ["cam", "hab"]})
    assert st.get_raw(u)["role"] == "usuario"
    tok = st.make_token(u)
    assert st.verify_token(tok)["username"] == u
    assert st.delete(u) is True
    assert st.get_raw(u) is None
```

- [ ] **Step 2: Correr, ver fallar** — `.venv/bin/python -m pytest tests/test_auth_store.py -v` → FAIL.

- [ ] **Step 3: Reescribir `AuthStore`.** Mantener el encabezado del módulo (`hash_password`, `verify_password`, roles, `_b64e/_b64d`, secret/token helpers) TAL CUAL. Reemplazar SOLO el cuerpo de la clase (que hoy lee/escribe `users.json`) por SQLAlchemy. Patrón de cada método (aplicarlo a los 8 métodos de storage):

```python
from services.db import session_scope, User

class AuthStore:
    def __init__(self, base_dir=None):
        self._secret = self._load_secret()  # el secret de tokens sigue igual (archivo o env)

    def _to_dict(self, u: User) -> dict:
        d = {"username": u.username, "role": u.role}
        d.update(u.data or {})           # sucursales, nombre, gestor
        return d

    def list(self):
        with session_scope() as s:
            return [self._to_dict(u) for u in s.query(User).order_by(User.username).all()]

    def get_raw(self, username):
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).one_or_none()
            return self._to_dict(u) if u else None

    def create(self, username, password, role, sucursales, nombre="", gestor=None):
        role = normalize_role(role)
        with session_scope() as s:
            if s.query(User).filter_by(username=username).first():
                raise ValueError("usuario ya existe")
            u = User(username=username, password_hash=hash_password(password), role=role,
                     data={"sucursales": list(sucursales or []), "nombre": nombre, "gestor": gestor})
            s.add(u); s.flush()
            return self._to_dict(u)

    def update(self, username, patch):
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).one_or_none()
            if not u: return None
            if "password" in patch and patch["password"]:
                u.password_hash = hash_password(patch["password"])
            if "role" in patch: u.role = normalize_role(patch["role"])
            data = dict(u.data or {})
            for k in ("sucursales", "nombre", "gestor"):
                if k in patch: data[k] = patch[k]
            u.data = data
            s.flush()
            return self._to_dict(u)

    def delete(self, username):
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).one_or_none()
            if not u: return False
            s.delete(u); return True

    def authenticate(self, username, password):
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).one_or_none()
            if not u or not verify_password(password, u.password_hash):
                return None
            return self._to_dict(u)
    # make_token / verify_token: igual que hoy pero validando el username contra la DB
    # (verify_token puede seguir devolviendo el payload + get_raw(username)).
```

Mantener `make_token`/`verify_token` con su lógica HMAC actual; donde hoy leían el user del JSON, usar `get_raw(username)`.

- [ ] **Step 4: Correr, ver pasar** — `.venv/bin/python -m pytest tests/test_auth_store.py -v` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(analitics): auth_store sobre postgres (misma interfaz)"`

---

## Task 3: `sucursal_store` → postgres

**Files:**
- Modify: `app/backend/services/sucursal_store.py`
- Create: `app/backend/tests/test_sucursal_store.py`

**Interfaces (EXACTAS):** `SucursalStore(base_dir=None)`; `list()`, `list_summary()`, `get(sid)`, `exists(sid)`, `create(nombre, seed_gestores=False)`, `update(sid, patch)`, `delete(sid)`, `upsert_gestor(sid, clave, cfg)`, `rename_gestor(sid, clave, nueva_clave)`, `delete_gestor(sid, clave)`, `reset(sid)`. Devuelven los mismos dicts de config que hoy.

- [ ] **Step 1: Test que falla** — `tests/test_sucursal_store.py`

```python
from services.sucursal_store import SucursalStore, slugify

def test_crud_y_gestores():
    st = SucursalStore(base_dir=None)
    sid = slugify("Camaguey Test")
    st.delete(sid)
    cfg = st.create("Camaguey Test", seed_gestores=False)
    assert st.exists(sid)
    assert cfg["nombre"] == "Camaguey Test"
    st.update(sid, {"metas": {"meta_dinero_total": 5000.0}})
    assert st.get(sid)["metas"]["meta_dinero_total"] == 5000.0
    st.upsert_gestor(sid, "juan", {"nombre": "Juan"})
    assert "juan" in st.get(sid)["gestores"]
    st.rename_gestor(sid, "juan", "juanp")
    assert "juanp" in st.get(sid)["gestores"] and "juan" not in st.get(sid)["gestores"]
    st.delete_gestor(sid, "juanp")
    assert "juanp" not in st.get(sid)["gestores"]
    assert st.delete(sid) is True
```

- [ ] **Step 2: Correr, ver fallar.**

- [ ] **Step 3: Reescribir `SucursalStore`.** Conservar `slugify`, `default_sucursal_config`, `default_metas`, `default_parametros`, y toda la lógica de merge/overrides (operan sobre dicts). Cambiar SOLO la carga/guardado: en vez de `sucursales.json`, cada método:
  - lee la config con `s.query(Sucursal).filter_by(sid=sid)` → `row.config` (dict),
  - opera sobre el dict con la lógica actual,
  - guarda con `row.config = nuevo_dict` (o crea `Sucursal(sid, nombre, config)`).
  Patrón:

```python
from services.db import session_scope, Sucursal

class SucursalStore:
    def __init__(self, base_dir=None):
        pass

    def get(self, sid):
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            return None if not row else {"sid": row.sid, "nombre": row.nombre, **(row.config or {})}

    def create(self, nombre, seed_gestores=False):
        sid = slugify(nombre)
        cfg = default_sucursal_config(nombre, sid, seed_gestores)  # dict actual
        with session_scope() as s:
            if s.query(Sucursal).filter_by(sid=sid).first():
                raise ValueError("sucursal ya existe")
            body = {k: v for k, v in cfg.items() if k not in ("sid", "nombre")}
            s.add(Sucursal(sid=sid, nombre=nombre, config=body)); s.flush()
        return self.get(sid)

    def update(self, sid, patch):
        with session_scope() as s:
            row = s.query(Sucursal).filter_by(sid=sid).one_or_none()
            if not row: return None
            body = dict(row.config or {})
            # === MISMA lógica de merge que la versión JSON (metas/gestores/parametros/overrides) ===
            body = _merge_patch(body, patch)   # reusar la función interna existente
            if "nombre" in patch: row.nombre = patch["nombre"]
            row.config = body; s.flush()
        return self.get(sid)
    # upsert_gestor/rename_gestor/delete_gestor/reset: cargar row.config, aplicar la lógica actual
    # sobre config["gestores"], guardar row.config.
```

  `list()`/`list_summary()`: `s.query(Sucursal).all()` mapeado con la lógica de summary actual.

- [ ] **Step 4: Correr, ver pasar.**

- [ ] **Step 5: Commit** — `git commit -m "feat(analitics): sucursal_store sobre postgres (config JSONB)"`

---

## Task 4: `repository` → postgres (uploads = solo datos)

**Files:**
- Modify: `app/backend/services/repository.py`
- Create: `app/backend/tests/test_repository.py`

**Interfaces (EXACTAS):** `UploadRepository(base_dir=None)`; `find_conflicts(sid, filename, date_min, date_max)`, `add(sid, report: ReportData, force=False) -> StoredUpload`, `list(sid) -> list[StoredUpload]`, `get(sid, uid) -> ReportData|None`, `delete(sid, uid) -> bool`, `reset(sid)`, `accumulated(sid) -> ReportData|None`. `StoredUpload` (dataclass) y `ReportData` (de `loader`) se mantienen.

**Clave:** `add()` guarda las FILAS en `analytics_upload_row`, NUNCA el archivo. `get`/`accumulated`/`load_df` arman el DataFrame (columnas STD_COLS) con `pd.read_sql`.

- [ ] **Step 1: Test que falla** — `tests/test_repository.py`

```python
import pandas as pd
from services.repository import UploadRepository
from services.loader import ReportData, STD_COLS
from services.sucursal_store import SucursalStore, slugify

def _report():
    df = pd.DataFrame([
        {STD_COLS["op"]:"1", STD_COLS["fecha"]:pd.Timestamp("2026-01-05"),
         STD_COLS["socio"]:"JUAN", STD_COLS["merc"]:"CERVEZA", STD_COLS["grupo"]:"BEB",
         STD_COLS["cant"]:2, STD_COLS["importe"]:100.0},
    ])
    return ReportData(df=df, date_min=df[STD_COLS["fecha"]].min(),
                      date_max=df[STD_COLS["fecha"]].max(), filename="ventas.xlsx")

def test_add_get_accumulated_delete():
    sid = slugify("Repo Test")
    SucursalStore(base_dir=None).delete(sid); SucursalStore(base_dir=None).create("Repo Test")
    repo = UploadRepository(base_dir=None); repo.reset(sid)
    stored = repo.add(sid, _report())
    assert stored.filas == 1
    got = repo.get(sid, stored.id)
    assert list(got.df.columns)[:1] == [STD_COLS["op"]] and len(got.df) == 1
    acc = repo.accumulated(sid); assert len(acc.df) == 1
    assert repo.delete(sid, stored.id) is True
    assert repo.get(sid, stored.id) is None
```

- [ ] **Step 2: Correr, ver fallar.**

- [ ] **Step 3: Reescribir `UploadRepository`.** Conservar `_df_to_report`, `_ranges_overlap`, `StoredUpload`, `DEDUPE_KEYS`. Reemplazar el I/O de parquet/index por SQLAlchemy:

```python
import uuid, pandas as pd
from datetime import datetime
from services.db import session_scope, Upload, UploadRow
from services.loader import ReportData, STD_COLS

_COL2ATTR = {STD_COLS["op"]:"operacion", STD_COLS["fecha"]:"fecha", STD_COLS["socio"]:"socio",
             STD_COLS["merc"]:"mercancia", STD_COLS["grupo"]:"grupo", STD_COLS["cant"]:"cantidad",
             STD_COLS["importe"]:"importe", STD_COLS["suma"]:"suma", STD_COLS["nota"]:"nota"}

class UploadRepository:
    def __init__(self, base_dir=None):
        pass

    def add(self, sid, report, force=False):
        df = report.df
        uid = uuid.uuid4().hex
        dmin = str(report.date_min.date()) if report.date_min is not None else None
        dmax = str(report.date_max.date()) if report.date_max is not None else None
        with session_scope() as s:
            up = Upload(id=uid, sid=sid, filename=report.filename,
                        uploaded_at=datetime.utcnow().isoformat(timespec="seconds"),
                        rango=report.rango_str, filas=int(len(df)),
                        date_min=dmin, date_max=dmax, source="upload")
            s.add(up)
            for _, r in df.iterrows():
                kw = {attr: (r.get(col) if col in df.columns else None) for col, attr in _COL2ATTR.items()}
                if kw.get("fecha") is not None and pd.notna(kw["fecha"]):
                    kw["fecha"] = pd.to_datetime(kw["fecha"]).date()
                else:
                    kw["fecha"] = None
                s.add(UploadRow(upload_id=uid, **kw))
            s.flush()
        return StoredUpload(id=uid, filename=report.filename, uploaded_at=up.uploaded_at,
                            rango=report.rango_str, filas=int(len(df)), date_min=dmin, date_max=dmax)

    def _df_de_filas(self, upload_ids):
        # arma el DataFrame STD_COLS desde analytics_upload_row
        from services.db import engine
        if not upload_ids: return pd.DataFrame(columns=list(_COL2ATTR.keys()))
        q = "SELECT operacion,fecha,socio,mercancia,grupo,cantidad,importe,suma,nota FROM analytics_upload_row WHERE upload_id = ANY(%(ids)s)"
        raw = pd.read_sql(q, engine, params={"ids": list(upload_ids)})
        ren = {v: k for k, v in _COL2ATTR.items()}
        return raw.rename(columns=ren)

    def get(self, sid, uid):
        with session_scope() as s:
            up = s.query(Upload).filter_by(sid=sid, id=uid).one_or_none()
            if not up: return None
        df = self._df_de_filas([uid])
        return _df_to_report(df, up.filename)

    def accumulated(self, sid):
        with session_scope() as s:
            ids = [u.id for u in s.query(Upload).filter_by(sid=sid).all()]
        if not ids: return None
        df = self._df_de_filas(ids).drop_duplicates(subset=DEDUPE_KEYS) if DEDUPE_KEYS else self._df_de_filas(ids)
        return _df_to_report(df, "acumulado")

    def list(self, sid):
        with session_scope() as s:
            return [StoredUpload(id=u.id, filename=u.filename, uploaded_at=u.uploaded_at, rango=u.rango,
                                 filas=u.filas, date_min=u.date_min, date_max=u.date_max)
                    for u in s.query(Upload).filter_by(sid=sid).order_by(Upload.uploaded_at).all()]

    def delete(self, sid, uid):
        with session_scope() as s:
            up = s.query(Upload).filter_by(sid=sid, id=uid).one_or_none()
            if not up: return False
            s.delete(up); return True   # rows caen por cascade

    def reset(self, sid):
        with session_scope() as s:
            for u in s.query(Upload).filter_by(sid=sid).all(): s.delete(u)

    def find_conflicts(self, sid, filename, date_min, date_max):
        # misma lógica de solape que hoy pero sobre self.list(sid)
        out = []
        for u in self.list(sid):
            if _ranges_overlap(date_min, date_max, u.date_min, u.date_max):
                out.append({"id": u.id, "filename": u.filename, "rango": u.rango})
        return out
```

  **No se escribe ningún archivo.** El `content` del upload en `main.py` se lee, se parsea con `load_report`, y su `ReportData` va directo a `add()`.

- [ ] **Step 4: Correr, ver pasar.**

- [ ] **Step 5: Commit** — `git commit -m "feat(analitics): repository sobre postgres, guarda solo datos (sin parquet)"`

---

## Task 5: Script de migración JSON/parquet → postgres

**Files:**
- Create: `app/backend/migrate_json_to_pg.py`
- Create: `app/backend/tests/test_migration.py`

**Interfaces:** `migrar(data_dir: Path) -> dict` (devuelve conteos `{usuarios, sucursales, uploads, filas}`). Idempotente (no duplica si se re-corre).

- [ ] **Step 1: Test que falla** — `tests/test_migration.py`: crear un `data_dir` temporal con un `users.json`, `sucursales.json` y un `uploads/<sid>/index.json`+`.parquet` mínimos; correr `migrar()`; afirmar los conteos y que re-correr no duplica.

```python
import json, pandas as pd
from pathlib import Path
from migrate_json_to_pg import migrar
from services.db import session_scope, User, Sucursal, Upload

def test_migracion_idempotente(tmp_path):
    (tmp_path/"users.json").write_text(json.dumps({"admin":{"username":"admin","password":"pbkdf2$sha256$1$x$y","role":"admin","sucursales":["*"]}}))
    (tmp_path/"sucursales.json").write_text(json.dumps([{"sid":"cam","nombre":"Camaguey","gestores":{},"metas":{}}]))
    ud = tmp_path/"uploads"/"cam"; ud.mkdir(parents=True)
    df = pd.DataFrame([{"Operacion":"1","Fecha":"2026-01-05","Socio":"JUAN","Mercancia":"X","Cantidad":1,"Importe":10.0}])
    df.to_parquet(ud/"u1.parquet")
    (ud/"index.json").write_text(json.dumps([{"id":"u1","filename":"v.xlsx","uploaded_at":"2026-01-05","rango":"","filas":1,"date_min":"2026-01-05","date_max":"2026-01-05"}]))
    r1 = migrar(tmp_path); r2 = migrar(tmp_path)  # idempotente
    assert r1["usuarios"] >= 1 and r1["sucursales"] >= 1 and r1["uploads"] >= 1 and r1["filas"] >= 1
    with session_scope() as s:
        assert s.query(User).filter_by(username="admin").count() == 1
        assert s.query(Sucursal).filter_by(sid="cam").count() == 1
        assert s.query(Upload).filter_by(id="u1").count() == 1  # no duplicó
```

- [ ] **Step 2: Correr, ver fallar.**

- [ ] **Step 3: Implementar `migrate_json_to_pg.py`** — leer los JSON (usuarios/sucursales) y por cada sucursal su `index.json` + parquet, insertando con upsert por PK (`username`/`sid`/`upload.id`); las filas de cada parquet → `analytics_upload_row` (saltar el upload si su `id` ya existe). `main()` usa el `data_dir` real (donde hoy están los JSON, ver `sucursal_store`/`repository` `base_dir`). Reusar el mapeo `_COL2ATTR` del repository. Imprime los conteos.

- [ ] **Step 4: Correr, ver pasar.**

- [ ] **Step 5: Commit** — `git commit -m "feat(analitics): script migración JSON/parquet -> postgres (idempotente)"`

---

## Task 6: Wire init_db + migración real + smoke end-to-end + deploy

**Files:**
- Modify: `app/backend/main.py` (llamar `init_db()` al startup; instanciar stores sin `base_dir` efectivo)

- [ ] **Step 1:** En `main.py`, en el startup de FastAPI (o al importar), llamar `from services.db import init_db; init_db()`. Verificar que los stores globales se instancian igual (aceptan `base_dir` pero lo ignoran).

- [ ] **Step 2: Correr TODA la suite** — `.venv/bin/python -m pytest tests/ -v` → todo PASS.

- [ ] **Step 3: Migración REAL (en el VPS).** Localizar el `data_dir` real (donde están `users.json`/`sucursales.json`/`uploads`). Correr `.venv/bin/python migrate_json_to_pg.py`. Guardar la salida de conteos.

- [ ] **Step 4: Verificar conteos** contra los archivos: `#usuarios` = claves en users.json; `#sucursales` = items en sucursales.json; `#uploads` = suma de items en los index.json; `#filas` = suma de filas de los parquet. Deben coincidir.

- [ ] **Step 5: Deploy + smoke** — `sudo systemctl restart analitics` → `curl -s 127.0.0.1:3010/api/health` OK → login con un usuario real → abrir un reporte (ventas/ranking/metas) por la UI/API → mismo resultado que antes. Revisar `journalctl -u analitics` sin errores.

- [ ] **Step 6: Commit** — `git commit -m "feat(analitics): init_db en startup; analitics corre 100% sobre postgres"`

---

## Notas de rollback

Si el smoke falla: `git revert` de los commits de esta rama + `sudo systemctl restart analitics` → vuelve a JSON (los archivos JSON/parquet NO se borraron). Investigar con `journalctl -u analitics`. Los archivos JSON/parquet se conservan ~1 semana tras verificar en prod; luego se limpian en un commit aparte.
