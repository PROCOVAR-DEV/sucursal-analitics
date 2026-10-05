# Analytics · puesta en marcha de Las Tunas

Esta guía sirve para Jorge y María y también como lista de control para quien dé de alta
una sucursal. No contiene contraseñas. La clave inicial se entrega por un canal separado
y debe cambiarse al recibirla.

## Acceso y alcance

Analytics usa un **usuario**, no un correo electrónico. Cada cuenta debe tener un nombre
visible, un rol y una lista de sucursales. Para Las Tunas, el identificador interno es
`las-tunas` y la fuente automática es la base `tunas` de Ventra.

Los roles actuales relevantes son:

- `supervisor`: ve una o varias sucursales asignadas, consulta todos sus números, cambia
  las metas y puede gestionar cuentas `supervisor` y `gestor` dentro de esas sucursales.
- `admin`: administra estructura y usuarios, pero siempre ve **todas** las sucursales.
  El sistema no tiene un rol de administrador limitado a una sola sucursal.

Por eso María encaja directamente en `supervisor` con `sucursales=["las-tunas"]`. Para
Jorge hay que confirmar qué significa «administrador de Las Tunas»: si debe quedar
limitado a Las Tunas, el rol técnico disponible es también `supervisor`; si necesita
editar la estructura global, `admin` le abriría todas las sucursales.

## Primeros pasos para Jorge y María

1. Entrar a Analytics con el usuario entregado y la clave inicial recibida por separado.
2. Comprobar que en la cabecera aparece **Las Tunas** y que no aparecen sucursales que no
   correspondan a la cuenta.
3. Elegir el mes de trabajo. La frescura del dato indica cuándo Ventra terminó la última
   carga; no hace falta subir un Excel cuando la sucursal figura como conectada a Ventra.
4. En **Cómo vamos**, revisar el total de la oficina, ventas, hectolitros y CCC. El bloque
   «sin vendedor» lo ve el supervisor para poder cuadrar el total de la oficina.
5. En **Quién vende**, revisar cada gestor, sus productos, clientes y cumplimiento.
6. En **Config → Gestores**, comprobar nombres y alias tal como aparecen después de `V-`
   en la nota de las facturas. Un alias incorrecto manda ventas a «sin vendedor».
7. En **Config → Calculadora de metas**, colocar las cuotas del mes por gestor y guardar.
   Revisar después que la suma individual cuadre con la meta de la oficina.
8. Usar **Descargas** para obtener los reportes Excel del período seleccionado.

Si los totales de la oficina existen pero un gestor aparece en cero, revisar primero su
alias. Si la oficina completa está en cero, revisar la fuente Ventra y la fecha de la
última carga antes de cambiar metas o usuarios.

## Checklist técnico para una sucursal nueva

### Identidad y permisos

- [ ] Acordar `username` exacto y nombre visible de cada persona; no inventar correo ni
      apellidos. Analytics no necesita correo.
- [ ] Crear cuentas individuales; nunca compartir la cuenta de otra persona.
- [ ] Asignar sólo el `sid` de la sucursal a roles acotados y comprobar que no conservan
      el comodín `*`.
- [ ] Verificar con cada cuenta que sólo aparecen las sucursales autorizadas.
- [ ] Entregar la contraseña inicial fuera del repositorio y de esta documentación.

### Sucursal y fuente de ventas

- [ ] Crear o confirmar la fila de `analytics_sucursal` con un `sid` estable.
- [ ] Añadir una correspondencia explícita `sid → base de Ventra` en
      `app/backend/services/ventra_sucursales.py`; nunca deducirla por parecido del nombre.
- [ ] Confirmar que ninguna base de Ventra se asigna a dos sucursales.
- [ ] Verificar que la recuperación de Ventra deja filas, período mínimo/máximo y una
      fecha de actualización reciente.
- [ ] Comparar el total de un día contra Ventra antes de entregar la oficina.

### Gestores y atribución

- [ ] Cargar el roster real de gestores: clave, nombre, agencia/sector y estado activo.
- [ ] Tomar los alias del segmento `V-` de facturas reales; no usar nombres de clientes
      ni aproximaciones.
- [ ] Revisar cuántas ventas quedan «sin vendedor» y corregir alias hasta explicar el
      resultado. No esconder ese importe: forma parte del total de oficina.
- [ ] Crear cuentas `gestor` sólo cuando proceda y vincular cada una a la clave exacta del
      roster.

### Metas y reglas

- [ ] Configurar cuota de hectolitros y CCC por gestor para el mes vigente.
- [ ] Configurar metas por formato y por cantidad desde la calculadora.
- [ ] Revisar días laborables, curva/frecuencia, factores de conversión y porcentajes de
      comisión de la sucursal.
- [ ] Comprobar que la suma de metas individuales coincide con la meta de oficina.

### Validación de salida

- [ ] Oficina: importe, operaciones, hectolitros, CCC y ventas sin vendedor cuadran con
      la fuente para un período conocido.
- [ ] Gestores: al menos tres facturas reales quedan atribuidas a la persona correcta.
- [ ] Permisos: supervisor ve y configura sólo su sucursal; gestor ve sólo sus datos.
- [ ] Mes sin ventas y mes con ventas muestran estados comprensibles, sin datos de otra
      sucursal.
- [ ] Los Excel de Descargas conservan los mismos totales que el tablero.
- [ ] Registrar quién validó, qué período usó y la fecha de la comprobación.

## Estado de las cuentas solicitadas

El 05/10/2026 no se pudieron crear ni comprobar las cuentas desde este equipo porque la
conexión SSH al VPS agotó el tiempo. Tampoco hay datos locales que indiquen apellidos,
correos o nombres de usuario previos de Jorge y María. Antes del alta quedan dos datos
por confirmar: los `username` exactos y si Jorge debe ser `supervisor` limitado a Las
Tunas o `admin` global. María corresponde a `supervisor` de `las-tunas`.
