# IoT Box Community

`community_iot_box` is the free, LGPL-3 Odoo 17 Community module maintained by
JDA SOLUTIONS.

It provides the Odoo-side foundation for a Community IoT stack:

- IoT Boxes
- IoT Devices
- IoT Jobs
- token-based agent registration
- heartbeat monitoring
- job polling and result reporting
- automatic device synchronization from external agents

## Repository layout

This repository is intentionally structured as an Odoo addon repository:

- `community_iot_box/`

## Compatibility

- Odoo 17 Community
- Odoo.sh private projects
- On-premise Odoo deployments
- Not compatible with Odoo Online (SaaS), because this addon contains Python
  code.

## Requirements

- A separately deployed IoT Box Community Agent for Linux or Windows.
- The agent is configured by the administrator. This addon never downloads,
  installs or executes agent code.

## Current scope

The module includes:

- backend models and views
- REST endpoints for IoT agents
- test print job creation
- support for autodetected devices reported by the agent

The external IoT agent is not included in this repository.

## Installation

1. Copy `community_iot_box` into your Odoo custom addons path.
2. Update the apps list.
3. Install `IoT Box Community`.
4. Create an IoT Box record and generate its token.
5. Install IoT Box Community Agent on the device host and configure it with:
   - Odoo URL
   - optional database name
   - IoT token
6. Confirm the heartbeat and discovered devices in Odoo, then run a test print.

## Agent distribution

The agent is a separate product and release stream distributed by JDA SOLUTIONS.
The Odoo addon remains free and open source for users who prefer to run or
develop their own compatible agent.

## Support

For installation guidance or a reproducible defect in the advertised workflow,
use the support contact published on the Odoo Apps listing.

## License

LGPL-3
