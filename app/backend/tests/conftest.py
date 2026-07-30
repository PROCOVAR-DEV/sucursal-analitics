import os
from pathlib import Path

import pytest

# Cargar DATABASE_URL del .env si no está en el entorno (los tests corren fuera de
# systemd, que normalmente inyecta el EnvironmentFile).
_env = Path(__file__).resolve().parents[1] / ".env"
if "DATABASE_URL" not in os.environ and _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            os.environ["DATABASE_URL"] = val
            break


@pytest.fixture(autouse=True)
def _init():
    from services.db import init_db

    init_db()
