IoT Box Community
=================

Odoo 19 documentation

IoT Box Community is the Odoo-side control plane for local printers and
peripherals. It stores IoT Boxes, devices, heartbeat status and idempotent
print jobs. The separately distributed IoT Box Community Agent 0.4.0 runs on
the host that can reach the local hardware; this addon never downloads,
installs or executes agent code.

Requirements
------------

* Odoo 19 Community or Enterprise on Odoo.sh/private infrastructure or
  on-premise.
* IoT Box Community Agent 0.4.0 installed on a Linux or Windows host.
* Network access from the agent host to the Odoo URL.
* A configured local printer or supported peripheral.

The Linux agent path is the validated release path. Windows is distributed as
an independent agent and must be validated against the target spooler and
physical printer before production rollout.

Architecture
------------

The Odoo addon owns the inventory and queue. The agent registers the box,
sends heartbeat and device discovery data, claims jobs and reports results.
The normal ticket, ZPL, cash-drawer and PDF document job types remain separate
so retries and idempotency are preserved.

PDF document flow
-----------------

``QWeb PDF -> community_iot_printing -> iot.job -> Agent 0.4.0 -> printer``

PDFs are stored temporarily as protected ``ir.attachment`` records. A job
payload contains metadata and a one-time download route, not the document
bytes. The document endpoint requires the box token and the active job lock;
the agent validates MIME type, the PDF signature, size and SHA-256 before
printing. Successful or cancelled documents are deleted immediately; failed
documents are retained for seven days and then removed by cron.

Configuration
-------------

#. Open **IoT Box Community > IoT Boxes** and create a box.
#. Generate the token and give it only to its matching agent host.
#. Install and configure Agent 0.4.0 on that host.
#. Wait for the heartbeat and confirm **Online**, device discovery and the
   ``pdf_print_v1`` capability when PDF printing is installed.
#. Open **IoT Devices**, select a printer and use **Print test page**.
#. For administrative PDFs, install **Community IoT Printing**, grant the
   **Community IoT Print User** group and use the independent **IoT Print**
   action.

Operations and troubleshooting
------------------------------

* **No heartbeat:** check the Odoo URL, database and token in the local agent
  portal, then verify outbound network access.
* **Box offline:** confirm the agent service is running and that the token is
  assigned to the active box.
* **Device missing:** verify local discovery and wait for the next heartbeat.
* **Job pending:** confirm the box is online and inspect **IoT Jobs** for the
  lease and result fields.
* **PDF unavailable:** use only an online Standard Printer advertising
  ``pdf_print_v1``; retry a failed document or create a new job if the file has
  expired.

Security and compatibility
---------------------------

Keep tokens and agent-local secrets out of screenshots and repositories.
Access to boxes, devices and jobs is company-aware. The addon is intended for
Odoo.sh/private projects and on-premise deployments; it is not an Odoo
Online/SaaS addon because it contains Python code.

Publication evidence
--------------------

The listing assets include a JDA SOLUTIONS branded cover, icon and footer, plus
functional dashboard, box, device and job captures. Test data used for public
captures is fictional; machine names, tokens and local credentials are not
included.
