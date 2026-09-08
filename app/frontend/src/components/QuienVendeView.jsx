import { useState } from "react";

import GestorSkuView from "./GestorSkuView.jsx";
import RankingView from "./RankingView.jsx";
import { SubPestanas } from "./SubPestanas.jsx";
import SuDiaView from "./SuDiaView.jsx";
import VendedoresView from "./VendedoresView.jsx";

/**
 * «¿Quién vende?» — la misma gente, mirada de cuatro formas.
 *
 * Eran tres pestañas de arriba y todas son sobre las personas:
 *
 *   Carrera     el acumulado día a día. Quién va delante y cómo se movió la cosa.
 *   Cada uno    la ficha de cada gestor: sus totales, sus clientes, su comisión.
 *   Cruce       gestor × producto, en matriz. Quién vende MÁS de un producto concreto.
 *   Su día      qué hizo cada uno cada día: a quién le vendió y qué le vendió.
 *
 * Que «Cruce» fuera una pestaña propia lo explicaba su propio comentario: existe porque
 * «Cada uno» enseña los productos de cada gestor apilados y para comparar entre gestores
 * había que abrirlos uno a uno y sumar a mano. O sea que no era otro tema: era la misma
 * tabla girada. Girar una tabla es un botón, no una pestaña.
 */
/*
 * Con «Todas las sucursales» esta vista no se llega a abrir: lo corta App antes, porque
 * ninguna de las tres se combina entre sucursales. Por eso aquí no hay caso `isAll` — un
 * segundo sitio decidiendo lo mismo es un sitio donde los dos pueden dejar de coincidir.
 */
export default function QuienVendeView({ sourceId, period, user }) {
  const [activa, setActiva] = useState("carrera");

  return (
    <div className="space-y-5">
      <SubPestanas
        onCambio={setActiva}
        opciones={[
          { id: "carrera", label: "La carrera", sub: "El acumulado día a día" },
          { id: "cada", label: "Cada uno", sub: "La ficha de cada gestor" },
          { id: "cruce", label: "Cruce con productos", sub: "Quién vende más de cada producto" },
          { id: "sudia", label: "Su día", sub: "A quién le vendió y qué, día a día" },
        ]}
        valor={activa}
      />

      {activa === "carrera" && <RankingView period={period} sourceId={sourceId} user={user} />}
      {activa === "cada" && <VendedoresView period={period} sourceId={sourceId} user={user} />}
      {activa === "cruce" && <GestorSkuView period={period} sourceId={sourceId} user={user} />}
      {activa === "sudia" && <SuDiaView period={period} sourceId={sourceId} user={user} />}
    </div>
  );
}
