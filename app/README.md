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
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentación automática: `http://localhost:8000/docs`.

## Frontend

```bash
cd app/frontend
npm install
npm run dev
```

Abre `http://localhost:5173`, carga tu archivo `Reporte de Venta` y listo.

## Endpoints principales

| Método | Ruta                                              | Descripción                                |
| ------ | ------------------------------------------------- | ------------------------------------------ |
| POST   | `/api/upload`                                     | Sube el reporte y crea la sesión           |
| GET    | `/api/session/{sid}/dashboard`                    | KPIs + datos del resumen                   |
| GET    | `/api/session/{sid}/ventas`                       | Ventas/Supervisor (hectolitros)            |
| GET    | `/api/session/{sid}/productos`                    | CES/PROCOVAR + cumplimiento                |
| GET    | `/api/session/{sid}/ranking`                      | General, semanal, acumulado diario         |
| GET    | `/api/session/{sid}/clientes-punto`               | Clientes punto                             |
| GET    | `/api/session/{sid}/export/{modulo}.xlsx`         | Excel por módulo (ventas, productos, …)    |
| GET    | `/api/session/{sid}/export/all.xlsx`              | Excel consolidado con todo                 |

## Producción

- Frontend: `npm run build` (genera `app/frontend/dist/`).
- Sirve el `dist/` detrás de Nginx y el backend con `uvicorn` o `gunicorn -k uvicorn.workers.UvicornWorker main:app`.
- En `main.py` ajusta `allow_origins` de CORS al dominio real.
- Las sesiones viven en memoria (TTL 2h). Para escalar horizontalmente,
  reemplaza `SessionStore` por Redis.
