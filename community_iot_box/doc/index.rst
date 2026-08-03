IoT Box Community
=================

IoT Box Community connects Odoo 19 Community to local printers and devices by
using the separately distributed **IoT Box Community Agent** from JDA SOLUTIONS.
The addon manages box records, device inventory, heartbeat status and print-job
queues. It never downloads, installs or executes the agent.

Requirements
------------

* Odoo 19 Community with this addon installed.
* A Linux host that can reach the local printers or devices.
* IoT Box Community Agent v0.3 installed separately on that host.
* Network access from the agent host to the Odoo URL.

Linux v0.3 has been validated. A Windows deployment requires physical
validation against its target printers and network before it is treated as
supported in production.

Architecture
------------

The Odoo addon stores the operational inventory and queue. The external agent
runs on the device host, sends heartbeat and discovered-device data to Odoo,
polls for jobs and reports their results. Printers and other peripherals remain
connected to the agent host.

The Odoo URL, optional database name, IoT token and any agent-local secrets are
stored on the agent host. Do not put those values in this addon, its repository
or support screenshots.

Configuration
-------------

#. In Odoo, open **IoT Box Community > IoT Boxes** and create an IoT Box.
#. Generate the IoT token. Give that token only to the matching agent host.
#. Install IoT Box Community Agent on the Linux device host.
#. Open the local agent portal at ``https://localhost:8443``. Its certificate is
   local/self-signed, so verify that you are on the local host before accepting
   it.
#. Configure the Odoo URL, optional database name and the token.
#. Start or restart the agent, then wait for its heartbeat in Odoo.
#. Confirm that the box becomes **Online** and that the expected devices appear.

Connection and print tests
--------------------------

Open the IoT Box record and use **Test connection**. A successful result means
Odoo has a recent heartbeat; it does not send a print job. Then open the target
IoT Device and run **Print test page**. Confirm the resulting job reaches the
agent and that the physical device produces the expected output.

Troubleshooting
---------------

* **No heartbeat:** verify the Odoo URL, optional database and token in the
  local portal, then confirm network access from the agent host to Odoo.
* **Box remains offline:** confirm the agent service is running and the token
  belongs to the same active IoT Box.
* **Device missing:** check the device connection on the agent host, then wait
  for or trigger device discovery and review the IoT Devices list.
* **Job stays pending:** verify that the target box is online and the agent can
  poll Odoo; review the IoT Jobs record for result messages.
* **Print test fails:** validate the printer path, network address or local
  printer configuration on the agent host before changing Odoo data.

Compatibility and security
--------------------------

The addon is compatible with Odoo 19 Community, private Odoo.sh projects and
on-premise deployments. It is not compatible with Odoo Online/SaaS because it
contains Python code. Keep Odoo and agent traffic on trusted networks, restrict
access to the agent host and rotate an IoT token if that host is replaced or its
configuration may have been exposed.
