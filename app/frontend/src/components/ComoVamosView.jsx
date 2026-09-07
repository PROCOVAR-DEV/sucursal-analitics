import { useState } from "react";

import DashboardView from "./DashboardView.jsx";
import MarketView from "./MarketView.jsx";
import { SubPestanas } from "./SubPestanas.jsx";
import VentasView from "./VentasView.jsx";

/**
 * «¿Cómo vamos?» — las tres profundidades de la misma pregunta.
 *
 * Eran tres pestañas de arriba —Resumen, Ventas (HL) y Market— y las tres contestan lo
 * mismo mirando desde más cerca:
 *
 *   Resumen        el panorama: cuánto llevamos contra la meta, quién tira y en qué puesto voy.
 *   Por gestor     el detalle de cada uno, con sus formatos y su cumplimiento.
 *   Semana a semana la cuota partida por semanas, con su semáforo. Es lo que dice si vamos
 *                  tarde ANTES de que se acabe el mes.
 *
 * Puestas arriba parecían tres temas distintos; puestas aquí se ve que son un tema y tres
 * niveles de zoom.
 *
 * # «Todas las sucursales»
 *
 * Sólo el panorama sabe combinar sucursales: el detalle por gestor y el semanal son de una
 * sucursal concreta. En vez de dejar que alguien entre y se encuentre un error, se apagan
 * y se dice por qué al pasar por encima.
 */
export default function ComoVamosView({ sourceId, period, user, isAll }) {
  const [donde, setDonde] = useState("panorama");
  const activa = isAll ? "panorama" : donde;

  return (
    <div className="space-y-5">
      <SubPestanas
        onCambio={setDonde}
        opciones={[
          { id: "panorama", label: "Panorama", sub: "Contra la meta, de un vistazo" },
          {
            id: "gestor",
            label: "Por gestor",
            sub: "El detalle de cada uno y sus formatos",
            desactivada: isAll,
            motivo: "Elige una sucursal: el detalle por gestor no se combina entre sucursales.",
          },
          {
            id: "semana",
            label: "Semana a semana",
            sub: "La cuota partida por semanas, con semáforo",
            desactivada: isAll,
            motivo: "Elige una sucursal: la cuota semanal es de una sucursal concreta.",
          },
        ]}
        valor={activa}
      />

      {activa === "panorama" && <DashboardView period={period} sourceId={sourceId} user={user} />}
      {activa === "gestor" && <VentasView period={period} sourceId={sourceId} user={user} />}
      {activa === "semana" && <MarketView period={period} sourceId={sourceId} user={user} />}
    </div>
  );
}
