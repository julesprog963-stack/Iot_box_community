Community IoT Printing
======================

Community IoT Printing adds a separate **IoT Print** action for QWeb PDF
reports. It renders the report with the current Odoo user and sends the PDF to
an online Standard Printer through **community_iot_box** and Agent 0.4.0.

Scope and dependencies
----------------------

This addon depends only on ``base``, ``web`` and ``community_iot_box``. It does
not depend on Sales, Inventory, Accounting or Point of Sale. It is compatible
with Odoo 17, 18 and 19 branches; install the matching branch together with
the matching core addon.

Current core dependency release
--------------------------------

For Odoo 17, download **IoT Box Community 17.0.5.0.0** before installing this
addon: https://apps.odoo.com/apps/modules/17.0/community_iot_box

Quick start
-----------

#. Install **community_iot_box**, **community_iot_printing** and Agent 0.4.0.
#. Register an IoT Box and wait for an online Standard Printer advertising
   ``pdf_print_v1``.
#. Add the user to **Community IoT Print User**.
#. An administrator may set the company's default printer and copy count in
   the IoT settings.
#. Open a quotation, invoice, delivery or any model with a QWeb PDF report.
#. Select **IoT Print**, choose the report, printer and copies, then queue the
   PDF.

Supported behavior
------------------

* Only ``qweb-pdf`` reports applicable to the current model are shown.
* Form and list selection are supported, with a maximum of 100 records.
* The assistant is opened for every operation and permits 1 to 10 copies.
* Report rendering uses the current user's groups, ACLs, record rules,
  language, company and context.
* The standard Odoo **Print** menu remains untouched.
* Each copy is an independent IoT job with its own retry and idempotency
  state.

Security
--------

The dedicated group controls access to the action and assistant. Printer
configuration is restricted to administrators. PDF bytes are stored in a
temporary protected attachment by the core addon; the job payload contains
metadata and a lock-protected download route. No token or PDF content is
written to logs.

Troubleshooting
---------------

* If no action appears, verify the user group, report type and report access
  groups.
* If no printer appears, confirm the box is online, the device is a Standard
  Printer and ``pdf_print_v1`` is present in the heartbeat capabilities.
* If a job fails, inspect **IoT Box Community > IoT Jobs** and retry only after
  checking the agent and printer.
* The addon is for Odoo.sh/private and on-premise deployments, not Odoo
  Online/SaaS, because it depends on Python server code.

Publication evidence
--------------------

The listing includes a JDA SOLUTIONS cover, icon and footer. Functional UI
captures are kept fictional and exclude machine names, tokens and credentials.
