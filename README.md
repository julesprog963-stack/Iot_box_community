# IoT Box Community

`community_iot_box` is an Odoo 17 Community module developed by JDA Solutions.

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

## Requirements

- Odoo 17 Community
- Python-based external IoT agent deployed separately

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
5. Configure your external IoT agent with:
   - Odoo URL
   - optional database name
   - IoT token

## License

LGPL-3
