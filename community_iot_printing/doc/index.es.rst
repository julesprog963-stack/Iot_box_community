Community IoT Printing
======================

Community IoT Printing añade una acción independiente **IoT Print** para
reportes PDF QWeb. Renderiza el reporte con el usuario actual de Odoo y envía
el PDF a una impresora estándar en línea mediante **community_iot_box** y
Agent 0.4.0.

Alcance y dependencias
----------------------

Este addon solo depende de ``base``, ``web`` y ``community_iot_box``. No
depende de Ventas, Inventario, Contabilidad ni Punto de Venta. Es compatible
con las ramas Odoo 17, 18 y 19; instale la rama correspondiente junto con el
addon núcleo correspondiente.

Versión actual de la dependencia núcleo
---------------------------------------

Para Odoo 18, descargue **IoT Box Community 18.0.2.0.0** antes de instalar
este addon: https://apps.odoo.com/apps/modules/18.0/community_iot_box

Inicio rápido
-------------

#. Instale **community_iot_box**, **community_iot_printing** y Agent 0.4.0.
#. Registre una caja IoT y espere una impresora estándar en línea que anuncie
   ``pdf_print_v1``.
#. Agregue al usuario al grupo **Community IoT Print User**.
#. Un administrador puede definir la impresora y cantidad de copias
   predeterminadas en los ajustes IoT.
#. Abra una cotización, factura, albarán o cualquier modelo con reporte PDF
   QWeb.
#. Seleccione **IoT Print**, elija reporte, impresora y copias, y encole el
   PDF.

Comportamiento
--------------

* Solo se muestran reportes ``qweb-pdf`` aplicables al modelo actual.
* Funciona desde formulario y selección de lista, con máximo de 100 registros.
* El asistente se abre en cada operación y permite de 1 a 10 copias.
* El reporte respeta grupos, ACL, reglas de registro, idioma, compañía y
  contexto del usuario actual.
* El menú estándar **Print** de Odoo permanece intacto.
* Cada copia es un trabajo IoT independiente con reintento e idempotencia.

Seguridad
---------

El grupo dedicado controla el acceso a la acción y al asistente. La
configuración de impresora queda limitada a administradores. Los bytes del PDF
se guardan en un adjunto temporal protegido por el addon núcleo; el payload
solo contiene metadatos y una ruta de descarga protegida por lock. No se
registran tokens ni contenido PDF en los logs.

Solución de problemas
---------------------

* Si no aparece la acción, revise el grupo del usuario, el tipo del reporte y
  sus grupos de acceso.
* Si no aparece la impresora, confirme que la caja esté en línea, sea una
  impresora estándar y anuncie ``pdf_print_v1``.
* Si falla un trabajo, revise **IoT Box Community > IoT Jobs** y reintente
  después de comprobar agente e impresora.
* El addon está destinado a Odoo.sh privado y despliegues locales, no a Odoo
  Online/SaaS, porque depende de código Python del servidor.

Evidencia de publicación
------------------------

La ficha incluye portada, icono y pie con la marca JDA SOLUTIONS. Las capturas
funcionales usan datos ficticios y excluyen nombres de máquina, tokens y
credenciales.
