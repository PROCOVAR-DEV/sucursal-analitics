// PM2 config para sucursal-analitics (backend FastAPI + frontend Vite)
const path = require("path");
const ROOT = __dirname;

module.exports = {
  apps: [
    {
      name: "sucursal-api",
      cwd: path.join(ROOT, "app", "backend"),
      // pythonw.exe = Python sin ventana de consola (evita el pop-up en Windows).
      // pm2 sigue capturando stdout/stderr en sus logs.
      script: path.join(ROOT, "app", "backend", ".venv", "Scripts", "pythonw.exe"),
      interpreter: "none",
      args: ["-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
      autorestart: true,
    },
    {
      name: "sucursal-frontend",
      cwd: path.join(ROOT, "app", "frontend"),
      script: path.join(ROOT, "app", "frontend", "node_modules", "vite", "bin", "vite.js"),
      args: ["--host", "--port", "5173"],
      exec_mode: "cluster",
      instances: 1,
      autorestart: true,
    },
  ],
};
