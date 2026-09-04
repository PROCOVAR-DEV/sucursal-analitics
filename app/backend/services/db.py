"""Capa de base de datos (PostgreSQL vía SQLAlchemy) para analitics."""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path

from sqlalchemy import (
    create_engine,
    String,
    Integer,
    Float,
    Date,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
    relationship,
)

# DATABASE_URL viene del entorno. El servicio (systemd) lo inyecta con EnvironmentFile=.env;
# los scripts/comandos manuales NO, así que si falta lo leemos del .env de app/backend.
if "DATABASE_URL" not in os.environ:
    _env = Path(__file__).resolve().parents[1] / ".env"
    if _env.exists():
        for _line in _env.read_text().splitlines():
            _line = _line.strip()
            if _line.startswith("DATABASE_URL="):
                os.environ["DATABASE_URL"] = _line.split("=", 1)[1].strip().strip('"').strip("'")
                break

DATABASE_URL = os.environ["DATABASE_URL"]  # analitics_app@127.0.0.1:5432/analitics


def _conectar_reintentando():
    """Abre la conexión a Postgres, reintentando si el fallo es pasajero.

    `pool_pre_ping` ya detecta conexiones MUERTAS, pero no ayuda cuando lo que
    falla es abrir una NUEVA. Y eso pasa: el 07/08/2026 a las 15:13 el
    contenedor no pudo resolver el nombre del servidor de base de datos durante
    **16 segundos** —

        could not translate host name "procovar-postgres-nlfols" to address

    — y soltó seis trazas de error seguidas, que llegaron por correo como si la
    aplicación se hubiera caído. No se había caído: el DNS interno de Docker
    parpadeó, cosa que pasa cuando un servicio se redespliega o la red del
    enjambre se reorganiza.

    Un parpadeo de segundos no es una avería, y no debe despertar a nadie. Con
    esto se espera y se vuelve a intentar; solo si de verdad no vuelve en ~8
    segundos se levanta el error, que entonces sí es real.
    """
    from sqlalchemy.engine.url import make_url
    import time

    import psycopg2

    url = make_url(DATABASE_URL)
    espera = 0.25
    ultimo: Exception | None = None

    for intento in range(5):
        try:
            return psycopg2.connect(
                host=url.host,
                port=url.port or 5432,
                dbname=url.database,
                user=url.username,
                password=url.password,
                # Sin esto, un servidor que no contesta deja la petición colgada
                # minutos: el error tarda más en llegar que el propio arreglo.
                connect_timeout=5,
            )
        except psycopg2.OperationalError as e:
            ultimo = e
            if intento == 4:
                break
            time.sleep(espera)
            espera = min(espera * 2, 4)

    raise ultimo  # type: ignore[misc]


engine = create_engine(
    DATABASE_URL,
    creator=_conectar_reintentando,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "analytics_user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="usuario")
    # {sucursales, nombre, gestor}
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Sucursal(Base):
    __tablename__ = "analytics_sucursal"
    sid: Mapped[str] = mapped_column(String(80), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Ajuste(Base):
    """Configuración GLOBAL, la que no es de ninguna sucursal en concreto.

    Nace para las reglas de comisión, que se pueden poner para todas las
    sucursales a la vez o solo en una. Es clave/valor a propósito: lo global es
    poca cosa y muy variada, y una tabla por cada ajuste que aparezca serían
    migraciones constantes para guardar cuatro campos.
    """

    __tablename__ = "analytics_ajuste"
    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Upload(Base):
    __tablename__ = "analytics_upload"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)  # uuid como hoy
    sid: Mapped[str] = mapped_column(
        String(80), ForeignKey("analytics_sucursal.sid"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[str] = mapped_column(String(40), nullable=False)
    rango: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    filas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    date_min: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_max: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="upload")
    rows: Mapped[list["UploadRow"]] = relationship(
        cascade="all, delete-orphan", back_populates="upload"
    )


class UploadRow(Base):
    __tablename__ = "analytics_upload_row"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(
        String(60), ForeignKey("analytics_upload.id", ondelete="CASCADE"), index=True
    )
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


class ResultCache(Base):
    """Resultados ya calculados (Resumen y demás payloads pesados).

    Vive en Postgres y no en memoria a propósito: sobrevive a los reinicios y
    despliegues, se comparte entre procesos/réplicas y no consume RAM del
    servidor. Es también la base del motor de reportes: aquí es donde acaban
    los valores precalculados en vez de recomputarse en cada consulta.

    `version` es la huella de la sucursal en el momento del cálculo. Si al leer
    no coincide con la huella actual, el resultado se descarta y se recalcula:
    así es imposible servir un dato viejo tras subir un archivo.
    """

    __tablename__ = "analytics_result_cache"
    cache_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    sid: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Cuándo se sirvió por última vez. Es lo que permite purgar por uso real:
    # un reporte de un mes que nadie abre desde hace semanas ocupa espacio para
    # nada, y recalcularlo cuesta segundos si alguien vuelve a pedirlo.
    last_read_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=datetime.utcnow)


class VentaVentra(Base):
    """Una LÍNEA de venta traída de Ventra. Es el crudo, sin calcular nada.

    Existe porque los informes no pueden pedirle a Ventra un año entero cada vez que
    alguien abre una pantalla: son ~50.000 líneas por sucursal, al otro lado de una VPN
    que se cae. Se trae una vez, se guarda, y las pantallas leen de aquí.

    # La clave es de Ventra, no nuestra

    `linea_id` es el `id` que da Ventra, único por línea. Con él, volver a importar el
    mismo día no duplica: reescribe lo mismo encima. Es lo que permite lanzar la
    recuperación del histórico sin miedo, y repetirla si se corta a medias.

    # Se guarda el crudo, no el resultado

    Nada de gestor, hectolitros ni grupo comercial: eso lo calcula `enrich_for_sucursal`
    con la configuración de cada sucursal, que se edita y cambia. Guardando el resultado,
    editar un alias de gestor no arreglaría el pasado — habría que reimportarlo todo.
    """

    __tablename__ = "analytics_venta_ventra"

    linea_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # La base de Ventra: `santiago`, `holguinmoa`, `tunas`… NO es nuestra sucursal, y son
    # diez para ocho: `moa` y `palmasoriano` van por su cuenta.
    database: Mapped[str] = mapped_column(String(60), primary_key=True, index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    oper_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    socio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mercancia: Mapped[str] = mapped_column(Text, nullable=False, default="")
    grupo: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    cantidad: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    importe: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # La nota entera, tal cual. De aquí sale el vendedor (`V-`) y el folio (`P-`), y se
    # guarda completa porque el día que haga falta otro segmento ya está.
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    # El objeto de Ventra y su tipo. El nombre crudo se guarda SIEMPRE: la clasificación
    # es una etiqueta al lado, y si mañana se corrige, se recalcula sin haber perdido nada.
    objeto: Mapped[str] = mapped_column(String(120), nullable=False, default="", index=True)
    tipo_punto: Mapped[str] = mapped_column(String(30), nullable=False, default="", index=True)
    traido_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    """Crea las tablas si no existen y aplica las migraciones pendientes.

    Idempotente: se puede llamar en cada arranque sin efecto si ya está todo.
    """
    Base.metadata.create_all(engine)
    _migrar()


# Columnas añadidas después de la creación original de una tabla. `create_all`
# NO las agrega a tablas que ya existen: crea solo las tablas que faltan. Sin
# esto, una columna nueva queda ausente en las instalaciones ya montadas y todo
# lo que la use falla en silencio.
_MIGRACIONES = [
    ("analytics_result_cache", "last_read_at",
     "alter table analytics_result_cache"
     " add column if not exists last_read_at timestamp not null default now()"),
    ("analytics_result_cache", "idx_last_read",
     "create index if not exists ix_analytics_result_cache_last_read_at"
     " on analytics_result_cache (last_read_at)"),
    ("analytics_result_cache", "idx_computed",
     "create index if not exists ix_analytics_result_cache_computed_at"
     " on analytics_result_cache (computed_at)"),
]


def _migrar() -> None:
    from sqlalchemy import text as _text
    import logging as _logging
    log = _logging.getLogger(__name__)
    with engine.begin() as conn:
        for tabla, que, sql in _MIGRACIONES:
            try:
                conn.execute(_text(sql))
            except Exception:
                # Una migración que falla no debe impedir que el servicio
                # arranque: se registra y se sigue.
                log.exception("migracion fallida en %s (%s)", tabla, que)


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


# Crea las tablas al importar (startup del servicio): los stores hacen _ensure_seed()
# al instanciarse (auth_store/sucursal_store son singletons de módulo), así que las
# tablas deben existir ANTES. create_all es idempotente (no toca las que ya existen).
init_db()
