import { Component } from "react";

/**
 * Cuando una pantalla se rompe, que se rompa SOLO ella.
 *
 * Sin esto, cualquier error dentro de un panel desmonta la aplicación entera y lo que
 * queda es una página en blanco, sin un texto, sin un botón y sin nada que se pueda
 * contar por teléfono. Pasó de verdad: el 17/09/2026 un hook mal puesto en «Metas» dejó
 * a los supervisores sin poder entrar, y desde fuera era imposible distinguirlo de un
 * servidor caído, una sesión caducada o el internet.
 *
 * Ahora se queda la cabecera, las pestañas y este cartel, así que se puede salir a otra
 * vista sin recargar — y quien llame dice QUÉ pantalla es la que falla.
 */
export default class Rescate extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // A la consola del navegador, que es donde lo va a buscar quien lo arregle.
    console.error("Pantalla rota:", this.props.donde || "", error, info?.componentStack);
  }

  componentDidUpdate(prev) {
    // Al cambiar de pantalla se vuelve a intentar: si no, el cartel se queda puesto
    // para siempre y hay que recargar a mano.
    if (this.state.error && prev.donde !== this.props.donde) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="p-6 rounded-xl border border-amber-200 bg-amber-50 text-amber-900">
        <p className="font-semibold">Esta pantalla no se pudo dibujar.</p>
        <p className="text-sm mt-1">
          El resto de la aplicación sigue funcionando: elige otra pestaña arriba. Si hace falta
          avisar, di cuál es —<b>{this.props.donde || "sin nombre"}</b>— y con qué sucursal y mes.
        </p>
        <p className="text-xs mt-3 font-mono opacity-70 break-all">{String(this.state.error?.message || this.state.error)}</p>
      </div>
    );
  }
}
