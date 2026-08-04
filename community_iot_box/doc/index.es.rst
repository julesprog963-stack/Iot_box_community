IoT Box Community
=================

Documentación en español para Odoo 18

IoT Box Community es el centro de control en Odoo para impresoras y
periféricos locales. Guarda las cajas IoT, dispositivos, latidos y trabajos de
impresión idempotentes. El **IoT Box Community Agent 0.4.0** se instala por
separado en el equipo que puede alcanzar el hardware; este addon nunca
descarga, instala ni ejecuta código del agente.

Requisitos
----------

* Odoo 18 Community o Enterprise en Odoo.sh privado o infraestructura local.
* IoT Box Community Agent 0.4.0 en un equipo Linux o Windows.
* Acceso de red desde el agente hacia la URL de Odoo.
* Una impresora o periférico local configurado.

La ruta Linux es la ruta validada de esta versión. El agente Windows se
distribuye por separado y debe validarse contra el spooler y la impresora
física objetivo antes de usarlo en producción.

Arquitectura
------------

El addon de Odoo administra el inventario y la cola. El agente registra la
caja, envía latidos y descubrimiento de dispositivos, reclama trabajos e
informa resultados. Los trabajos de tickets, ZPL, cajón y documentos PDF se
mantienen separados para conservar reintentos e idempotencia.

Flujo de documentos PDF
-----------------------

``PDF QWeb -> community_iot_printing -> iot.job -> Agent 0.4.0 -> impresora``

Los PDF se guardan temporalmente como adjuntos ``ir.attachment`` protegidos.
El payload contiene metadatos y una ruta temporal de descarga, no los bytes
del documento. La ruta exige el token de la caja y el lock activo; el agente
valida MIME, firma PDF, tamaño y SHA-256 antes de imprimir. Tras éxito o
cancelación el documento se elimina; los fallidos se conservan siete días y
luego los elimina el cron.

Configuración
-------------

#. Abra **IoT Box Community > IoT Boxes** y cree una caja.
#. Genere el token y entréguelo únicamente al agente correspondiente.
#. Instale y configure Agent 0.4.0.
#. Espere el latido y confirme **Online**, los dispositivos y la capacidad
   ``pdf_print_v1`` cuando esté instalada la impresión PDF.
#. Abra **IoT Devices**, seleccione una impresora y pulse **Print test page**.
#. Para PDF administrativos, instale **Community IoT Printing**, asigne el
   grupo **Community IoT Print User** y use la acción independiente **IoT
   Print**.

Operación y solución de problemas
----------------------------------

* **Sin latido:** compruebe URL, base de datos y token en el portal local del
  agente y el acceso de salida hacia Odoo.
* **Caja desconectada:** confirme que el servicio está ejecutándose y que el
  token corresponde a la caja activa.
* **Falta un dispositivo:** revise el descubrimiento local y espere el próximo
  latido.
* **Trabajo pendiente:** confirme que la caja esté en línea y revise **IoT
  Jobs**.
* **PDF no disponible:** use una impresora estándar en línea que anuncie
  ``pdf_print_v1``; reintente el documento fallido o cree un trabajo nuevo si
  expiró.

Seguridad y compatibilidad
--------------------------

No incluya tokens ni secretos del agente en capturas o repositorios. El acceso
a cajas, dispositivos y trabajos respeta la compañía. El addon está pensado
para Odoo.sh privado y despliegues locales; no es compatible con Odoo
Online/SaaS porque contiene código Python.

Evidencia de publicación
------------------------

Los recursos de publicación incluyen portada, icono y pie con la marca JDA
SOLUTIONS, además de capturas funcionales del panel, cajas, dispositivos y
trabajos. Los datos de las capturas son ficticios y no contienen nombres de
máquina, tokens ni credenciales locales.
