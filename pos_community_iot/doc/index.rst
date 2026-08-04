POS Community IoT
=================

POS Community IoT routes Point of Sale receipts, manual reprints, folios and
preparation changes through the Community IoT queue while preserving the
standard POS printer as a controlled fallback.

Scope and dependencies
----------------------

The addon depends on ``point_of_sale`` and ``community_iot_box``. It is
available in the Odoo 17, 18 and 19 branches and must be installed with the
matching branch of the core addon. Administrative PDF reports belong to the
separate **community_iot_printing** addon.

Configuration
-------------

#. Install the matching POS and core addons and register an online IoT Box.
#. In POS settings enable **Community IoT Printing**.
#. Select the IoT Box, receipt printer, automatic receipt option and receipt
   copies.
#. Configure a folio printer and folio copies when folio output is required.
#. For kitchen/preparation printers, enable **Use Community IoT** on each POS
   printer and choose its IoT device and copies.
#. Use **Print test page** before opening a live session.

Supported flows
---------------

* Automatic receipt printing after payment.
* Manual receipt printing and reprinting.
* Folio output with configurable copies.
* New, changed and cancelled preparation tickets by preparation category.
* Bounded payloads, company/device validation and 1 to 10 copies.
* Controlled fallback to the standard POS printer after an RPC failure or an
  unavailable IoT path.
* Existing ticket, ZPL and cash-drawer jobs remain in the core queue.

Operational notes
-----------------

The POS addon creates ticket jobs only for a selected device belonging to the
selected IoT Box. It does not send PDF document jobs; those are handled by
Community IoT Printing. Inspect **IoT Box Community > IoT Jobs** when testing
retries, offline boxes or duplicate prevention.

Troubleshooting
---------------

* Confirm the POS configuration is enabled and its devices belong to the same
  box.
* Confirm the agent heartbeat and the device type before testing.
* If IoT printing fails, verify that the standard POS printer is configured so
  fallback has a valid target.
* Check the browser console and the job result only in a private test database;
  never include tokens or receipt content in support screenshots.

Publication evidence
--------------------

The listing includes a JDA SOLUTIONS cover, icon and footer. POS captures use
fictional products and customers and do not expose local credentials.
