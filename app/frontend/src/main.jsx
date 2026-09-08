import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import AvisoVersionNueva from "./components/AvisoVersionNueva.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
    {/* Fuera de <App/>: el aviso de version vieja sale tambien en la pantalla de entrar. */}
    <AvisoVersionNueva />
  </React.StrictMode>
);
