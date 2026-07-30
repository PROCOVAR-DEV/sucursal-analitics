"""Autenticación y usuarios.

Storage en PostgreSQL (tabla analytics_user) vía SQLAlchemy. La INTERFAZ pública se
conserva idéntica a la versión JSON: mismos métodos, mismas firmas y el mismo "dict de
usuario" ({username, nombre, role, sucursales, gestor}).

- Contraseñas: PBKDF2-HMAC-SHA256 con salt aleatorio por usuario.
- Tokens: JSON firmado con HMAC-SHA256 y expiración (solo librería estándar).
- Roles: 'admin'/'analitico' ven TODAS las sucursales; el resto solo las asignadas.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from services.db import session_scope, User

_PBKDF2_ROUNDS = 120_000
_TOKEN_TTL = 60 * 60 * 12  # 12 horas
ALL_SUCURSALES = "*"

# Roles:
#   admin      -> todo, todas las sucursales, gestión de usuarios
#   analitico  -> ve TODAS las sucursales (solo lectura, no cambia nada)
#   supervisor -> su(s) sucursal(es): ve todo y configura sus metas (por gestor)
#   usuario    -> solo ve su(s) sucursal(es) (lectura)
#   gestor     -> solo ve SUS datos (vinculado a un gestor de su sucursal)
VALID_ROLES = ("admin", "analitico", "supervisor", "usuario", "gestor")
_ALL_ROLES = ("admin", "analitico")            # acceso a todas las sucursales
_LEGACY = {"user": "usuario"}


def normalize_role(role: str) -> str:
    role = _LEGACY.get(role, role)
    return role if role in VALID_ROLES else "usuario"


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2$sha256${_PBKDF2_ROUNDS}${_b64e(salt)}${_b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, _algo, rounds, salt_b64, hash_b64 = stored.split("$")
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


class AuthStore:
    def __init__(self, base_dir: Path | str | None = None):
        # base_dir se conserva por compat: ya NO guarda los usuarios (van a postgres),
        # pero SÍ sigue guardando el `secret.key` de los tokens en disco para no
        # invalidar sesiones al reiniciar. En scripts/migración base_dir=None.
        self._base = Path(base_dir) if base_dir else None
        self._secret = self._load_secret()
        self._ensure_seed()

    def _load_secret(self) -> bytes:
        if self._base is not None:
            try:
                self._base.mkdir(parents=True, exist_ok=True)
                p = self._base / "secret.key"
                if p.exists():
                    return p.read_bytes()
                secret = os.urandom(32)
                p.write_bytes(secret)
                try:
                    os.chmod(p, 0o600)
                except OSError:
                    pass
                return secret
            except OSError:
                # No se pudo leer/escribir el secret en disco (p.ej. tests corriendo como
                # otro usuario, el archivo es 0600 de root). Se cae a env/efímero. En
                # PRODUCCIÓN el servicio corre como root y sí lee el secret real.
                pass
        env = os.environ.get("AUTH_SECRET")
        return env.encode() if env else os.urandom(32)

    @staticmethod
    def _to_dict(u: User) -> dict:
        data = u.data or {}
        return {
            "username": u.username,
            "nombre": data.get("nombre", u.username),
            "role": normalize_role(u.role),
            "sucursales": data.get("sucursales", []),
            "gestor": data.get("gestor"),
        }

    def _ensure_seed(self) -> None:
        with session_scope() as s:
            if s.query(User).count() == 0:
                s.add(
                    User(
                        username="admin",
                        password_hash=hash_password("admin"),
                        role="admin",
                        data={"nombre": "Administrador", "sucursales": [ALL_SUCURSALES], "gestor": None},
                    )
                )

    # ---------- usuarios ----------
    def list(self) -> list[dict]:
        with session_scope() as s:
            return [self._to_dict(u) for u in s.query(User).order_by(User.username).all()]

    def get_raw(self, username: str) -> dict | None:
        username = str(username).strip().lower()
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).one_or_none()
            return self._to_dict(u) if u else None

    def create(self, username: str, password: str, role: str, sucursales: list[str], nombre: str = "", gestor: str | None = None) -> dict:
        username = str(username).strip().lower()
        if not username:
            raise ValueError("Usuario vacío")
        role = normalize_role(role)
        sucs = [ALL_SUCURSALES] if role in _ALL_ROLES else list(sucursales or [])
        g = str(gestor).strip().upper() if role == "gestor" and gestor else None
        with session_scope() as s:
            if s.query(User).filter_by(username=username).first():
                raise ValueError("El usuario ya existe")
            u = User(
                username=username,
                password_hash=hash_password(password),
                role=role,
                data={"nombre": nombre or username, "sucursales": sucs, "gestor": g},
            )
            s.add(u)
            s.flush()
            return self._to_dict(u)

    def update(self, username: str, patch: dict) -> dict | None:
        username = str(username).strip().lower()
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).one_or_none()
            if u is None:
                return None
            data = dict(u.data or {})
            if patch.get("nombre"):
                data["nombre"] = patch["nombre"]
            if "role" in patch:
                u.role = normalize_role(patch["role"])
                if u.role in _ALL_ROLES:
                    data["sucursales"] = [ALL_SUCURSALES]
                if u.role != "gestor":
                    data["gestor"] = None
            if "sucursales" in patch and u.role not in _ALL_ROLES:
                data["sucursales"] = list(patch["sucursales"] or [])
            if "gestor" in patch and u.role == "gestor":
                data["gestor"] = str(patch["gestor"]).strip().upper() if patch["gestor"] else None
            if patch.get("password"):
                u.password_hash = hash_password(patch["password"])
            u.data = data
            s.flush()
            return self._to_dict(u)

    def delete(self, username: str) -> bool:
        username = str(username).strip().lower()
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).one_or_none()
            if u is None:
                return False
            # No borrar el último admin.
            if u.role == "admin" and s.query(User).filter_by(role="admin").count() <= 1:
                return False
            s.delete(u)
            return True

    # ---------- login / tokens ----------
    def authenticate(self, username: str, password: str) -> dict | None:
        username = str(username).strip().lower()
        with session_scope() as s:
            u = s.query(User).filter_by(username=username).one_or_none()
            if u and verify_password(password, u.password_hash or ""):
                return self._to_dict(u)
        return None

    def make_token(self, username: str) -> str:
        payload = {"u": username, "exp": int(time.time()) + _TOKEN_TTL}
        body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
        sig = _b64e(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def verify_token(self, token: str) -> dict | None:
        try:
            body, sig = token.split(".")
            expected = _b64e(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(sig, expected):
                return None
            payload = json.loads(_b64d(body))
            if payload.get("exp", 0) < int(time.time()):
                return None
            return self.get_raw(payload["u"])
        except Exception:
            return None

    @staticmethod
    def can_access(user: dict, sucursal_id: str) -> bool:
        """Lectura de una sucursal."""
        if user.get("role") in _ALL_ROLES or ALL_SUCURSALES in (user.get("sucursales") or []):
            return True
        return sucursal_id in (user.get("sucursales") or [])

    @staticmethod
    def can_write_metas(user: dict, sucursal_id: str) -> bool:
        """Configurar metas / subir reportes: admin (todas) o supervisor (su sucursal)."""
        role = user.get("role")
        if role == "admin":
            return True
        if role == "supervisor":
            return AuthStore.can_access(user, sucursal_id)
        return False

    @staticmethod
    def can_manage(user: dict) -> bool:
        """Config estructural (gestores, parámetros, grupos, sucursales, usuarios): solo admin."""
        return user.get("role") == "admin"

    @staticmethod
    def allowed_sucursales(user: dict, all_ids: list[str]) -> list[str]:
        if user.get("role") in _ALL_ROLES or ALL_SUCURSALES in (user.get("sucursales") or []):
            return list(all_ids)
        return [s for s in all_ids if s in (user.get("sucursales") or [])]


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
auth_store = AuthStore(DATA_DIR)
