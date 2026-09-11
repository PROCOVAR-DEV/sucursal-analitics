import { useState } from "react";

import ClientesAnalisisView from "./ClientesAnalisisView.jsx";
import MovimientoClientesView from "./MovimientoClientesView.jsx";
import { SubPestanas } from "./SubPestanas.jsx";

/**
 * «Clientes» — las dos preguntas que se le hacen a una cartera.
 *
 *   Qué compra cada uno   el pivote de siempre: clientes × producto.
 *   Quién entró y se fue  si la cartera crece o sólo se reordena.
 *
 * La segunda no estaba y es la que no se puede sacar de ninguna otra pantalla: un cliente
 * que deja de comprar no sale en ninguna lista de ventas, precisamente porque no vendió.
 */
export default function ClientesView({ sourceId, period, user }) {
  const [activa, setActiva] = useState("compra");

  return (
    <div className="space-y-5">
      <SubPestanas
        onCambio={setActiva}
        opciones={[
          { id: "compra", label: "Qué compra cada uno", sub: "Clientes × producto" },
          { id: "movimiento", label: "Quién entró y quién se fue", sub: "Si la cartera crece o sólo se reordena" },
        ]}
        valor={activa}
      />

      {activa === "compra" && <ClientesAnalisisView period={period} sourceId={sourceId} user={user} />}
      {activa === "movimiento" && <MovimientoClientesView period={period} sourceId={sourceId} user={user} />}
    </div>
  );
}
