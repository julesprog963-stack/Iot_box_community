POS Community IoT
=================

POS Community IoT envía recibos, reimpresiones manuales, folios y cambios de
preparación del Punto de Venta mediante la cola Community IoT y conserva la
impresora estándar de POS como fallback controlado.

Alcance y dependencias
----------------------

El addon depende de ``point_of_sale`` y ``community_iot_box``. Está disponible
en las ramas Odoo 17, 18 y 19 y debe instalarse junto con la rama equivalente
del addon núcleo. Los reportes PDF administrativos pertenecen al addon
separado **community_iot_printing**.

Versión actual de la dependencia núcleo
---------------------------------------

Para Odoo 17, descargue **IoT Box Community 17.0.5.0.0** antes de instalar
este addon: https://apps.odoo.com/apps/modules/17.0/community_iot_box

Configuración
-------------

#. Instale los addons POS y núcleo de la misma versión y registre una caja IoT.
#. En los ajustes de POS active **Community IoT Printing**.
#. Seleccione caja IoT, impresora de recibos, impresión automática y copias.
#. Configure impresora y copias de folio cuando sean necesarias.
#. Para cocina/preparación, active **Use Community IoT** en cada impresora POS
   y seleccione su dispositivo IoT y copias.
#. Use **Print test page** antes de abrir una sesión real.

Flujos soportados
-----------------

* Impresión automática del recibo después del pago.
* Impresión manual y reimpresión del recibo.
* Folios con copias configurables.
* Tickets de preparación nuevos, modificados y cancelados por categoría.
* Payloads acotados, validación compañía/dispositivo y de 1 a 10 copias.
* Fallback controlado a la impresora estándar de POS ante fallo RPC o ruta IoT
  no disponible.
* Los trabajos de ticket, ZPL y cajón existentes permanecen en la cola núcleo.

Notas operativas
----------------

El addon POS solo crea trabajos de ticket para un dispositivo seleccionado que
pertenece a la caja IoT seleccionada. No crea trabajos PDF; esos los gestiona
Community IoT Printing. Revise **IoT Box Community > IoT Jobs** al probar
reintentos, cajas desconectadas o prevención de duplicados.

Solución de problemas
---------------------

* Confirme que la configuración POS esté activa y que los dispositivos
  pertenezcan a la misma caja.
* Compruebe el latido del agente y el tipo de dispositivo.
* Si falla IoT, configure una impresora POS estándar válida para que funcione
  el fallback.
* Revise consola del navegador y resultado del trabajo solo en una base de
  pruebas privada; nunca incluya tokens o contenido de recibos en capturas.

Evidencia de publicación
------------------------

La ficha incluye portada, icono y pie con la marca JDA SOLUTIONS. Las capturas
usan productos y clientes ficticios y no muestran credenciales locales.
