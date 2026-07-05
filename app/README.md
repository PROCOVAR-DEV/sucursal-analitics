# Sucursal Analytics — Web app

Dashboard web estilo Power BI para el **Reporte de Venta** diario. Sube el
archivo `.xls/.xlsx` y obtén:

- KPIs y gráficos interactivos (hectolitros, importe, cumplimiento, ranking).
- Desglose por gestor (MALTA / PARRANDA, cuotas, blisters y pallets).
- CES vs PROCOVAR y cumplimiento de metas mensuales con cálculo de
  días laborales.
- Ranking general, semanal y acumulado diario.
- Clientes Punto (identificados por `NOMBRE!!` en la nota).
- Exportación a **Excel** para cada módulo y uno consolidado.

## Arquitectura

```
app/
  backend/   FastAPI + pandas    (API REST, procesamiento y export Excel)
  frontend/  React + Vite + Tailwind + Recharts (dashboard)
```

La API vive en `http://localhost:8000` y el frontend en
`http://localhost:5173` (en dev, con proxy a `/api`).

## Requisitos

- Python 3.10+
- Node 18+

## Backend

```bash
cd app/backend
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Si tu Linux muestra `externally-managed-environment` (PEP 668):

```bash
cd app/backend
python3 -m venv .venv --without-pip
source .venv/bin/activate
curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python /tmp/get-pip.py
pip install -r requirements.txt
```

No uses `timeout` para correr el servidor en desarrollo, porque lo apaga
automáticamente a los pocos segundos.

Documentación automática: `http://localhost:8000/docs`.

## Frontend

```bash
cd app/frontend
npm install
npm run dev
```

Abre `http://localhost:5173`, carga tu archivo `Reporte de Venta` y listo.

## Autenticación y multi-sucursal

La app tiene **login por roles**. Usuario admin por defecto: **admin / admin**
(cámbialo tras el primer acceso). El `admin` ve **todas** las sucursales y
administra usuarios; un `user` solo ve las sucursales que se le asignen.

Toda la configuración es **dinámica por sucursal**: gestores (agregar / editar /
eliminar, con sus alias), metas mensuales, factores de conversión, grupos
comerciales, comisiones, curva de venta, etc. Se arranca con una sucursal
sembrada (**Camagüey**, 7 gestores), pero se pueden crear más.

## Endpoints principales

| Método | Ruta                                                        | Descripción                          |
| ------ | ----------------------------------------------------------- | ------------------------------------ |
| POST   | `/api/auth/login`                                           | Devuelve `{token, user}`             |
| GET    | `/api/auth/me`                                              | Usuario actual                       |
| *      | `/api/users`                                                | Gestión de usuarios (admin)          |
| GET/POST | `/api/sucursales`                                         | Listar / crear sucursales            |
| GET/PUT/DELETE | `/api/sucursales/{sid}`                            | Config completa / editar / borrar    |
| *      | `/api/sucursales/{sid}/gestores[/{clave}]`                  | CRUD de gestores                     |
| POST/GET/DELETE | `/api/sucursales/{sid}/uploads[/{id}]`            | Reportes crudos (aislados)           |
| GET    | `/api/sucursales/{sid}/sources/{src}/dashboard`             | KPIs + resumen                       |
| GET    | `/api/sucursales/{sid}/sources/{src}/{ventas\|productos\|market\|ranking\|clientes-analisis\|vendedores}` | Datos por módulo |
| GET    | `/api/sucursales/{sid}/sources/{src}/export/{modulo}.xlsx`  | Excel (ventas/productos/market/ranking/clientes-analisis/all) |

`{src}` = UUID de un archivo subido o `accumulated` (histórico de la sucursal).
Todas las rutas (salvo login/health) requieren cabecera `Authorization: Bearer <token>`.

## Producción

- Frontend: `npm run build` (genera `app/frontend/dist/`).
- Sirve el `dist/` detrás de Nginx y el backend con `uvicorn` o `gunicorn -k uvicorn.workers.UvicornWorker main:app`.
- En `main.py` ajusta `allow_origins` de CORS al dominio real.
- Las sesiones viven en memoria (TTL 2h). Para escalar horizontalmente,
  reemplaza `SessionStore` por Redis.

## Acumulación diaria

- Cada `POST /api/upload` acumula por defecto el archivo subido al histórico.
- El dashboard de la sesión se calcula sobre el consolidado acumulado.
- La persistencia se guarda en `app/backend/data/`.
