"""Autenticación y usuarios (solo librería estándar).

- Contraseñas: PBKDF2-HMAC-SHA256 con salt aleatorio por usuario.
- Tokens: JSON firmado con HMAC-SHA256 y expiración (no requiere dependencias).
- Roles: 'admin' ve TODAS las sucursales; 'user' solo las asignadas.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path

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
    def __init__(self, base_dir: Path):
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)
        self._path = base_dir / "users.json"
        self._secret_path = base_dir / "secret.key"
        self._lock = threading.RLock()
        self._secret = self._load_secret()
        self._ensure_seed()

    def _load_secret(self) -> bytes:
        if self._secret_path.exists():
            return self._secret_path.read_bytes()
        secret = os.urandom(32)
        self._secret_path.write_bytes(secret)
        try:
            os.chmod(self._secret_path, 0o600)
        except OSError:
            pass
        return secret

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {u["username"]: u for u in data} if isinstance(data, list) else data
        except Exception:
            return {}

    def _write(self, data: dict) -> None:
        self._path.write_text(
            json.dumps(list(data.values()), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _ensure_seed(self) -> None:
        with self._lock:
            data = self._read()
            if not data:
                admin = {
                    "username": "admin",
                    "nombre": "Administrador",
                    "password_hash": hash_password("admin"),
                    "role": "admin",
                    "sucursales": [ALL_SUCURSALES],
                }
                self._write({"admin": admin})

    # ---------- usuarios ----------
    def list(self) -> list[dict]:
        return [self._public(u) for u in self._read().values()]

    @staticmethod
    def _public(u: dict) -> dict:
        return {"username": u["username"], "nombre": u.get("nombre", u["username"]),
                "role": normalize_role(u.get("role", "usuario")),
                "sucursales": u.get("sucursales", []),
                "gestor": u.get("gestor")}

    def get_raw(self, username: str) -> dict | None:
        return self._read().get(str(username).strip().lower())

    def create(self, username: str, password: str, role: str, sucursales: list[str], nombre: str = "", gestor: str | None = None) -> dict:
        username = str(username).strip().lower()
        if not username:
            raise ValueError("Usuario vacío")
        with self._lock:
            data = self._read()
            if username in data:
                raise ValueError("El usuario ya existe")
            role = normalize_role(role)
            sucs = [ALL_SUCURSALES] if role in _ALL_ROLES else list(sucursales or [])
            u = {"username": username, "nombre": nombre or username,
                 "password_hash": hash_password(password), "role": role, "sucursales": sucs,
                 "gestor": (str(gestor).strip().upper() if role == "gestor" and gestor else None)}
            data[username] = u
            self._write(data)
            return self._public(u)

    def update(self, username: str, patch: dict) -> dict | None:
        username = str(username).strip().lower()
        with self._lock:
            data = self._read()
            u = data.get(username)
            if u is None:
                return None
            if patch.get("nombre"):
                u["nombre"] = patch["nombre"]
            if "role" in patch:
                u["role"] = normalize_role(patch["role"])
                if u["role"] in _ALL_ROLES:
                    u["sucursales"] = [ALL_SUCURSALES]
                if u["role"] != "gestor":
                    u["gestor"] = None
            if "sucursales" in patch and u.get("role") not in _ALL_ROLES:
                u["sucursales"] = list(patch["sucursales"] or [])
            if "gestor" in patch and u.get("role") == "gestor":
                u["gestor"] = str(patch["gestor"]).strip().upper() if patch["gestor"] else None
            if patch.get("password"):
                u["password_hash"] = hash_password(patch["password"])
            data[username] = u
            self._write(data)
            return self._public(u)

    def delete(self, username: str) -> bool:
        username = str(username).strip().lower()
        with self._lock:
            data = self._read()
            if username not in data or data[username].get("role") == "admin" and \
                    len([x for x in data.values() if x.get("role") == "admin"]) <= 1:
                # no borrar el último admin
                if username in data and data[username].get("role") == "admin":
                    return False
                if username not in data:
                    return False
            del data[username]
            self._write(data)
            return True

    # ---------- login / tokens ----------
    def authenticate(self, username: str, password: str) -> dict | None:
        u = self.get_raw(str(username).strip().lower())
        if u and verify_password(password, u.get("password_hash", "")):
            return u
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
