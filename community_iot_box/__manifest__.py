{
    "name": "IoT Box Community",
    "summary": "Gestión de IoT Boxes y trabajos de impresión para Odoo 17 Community.",
    "description": """
Community IoT Box for Odoo 17 Community.

Features:
- IoT Boxes, IoT Devices and IoT Jobs.
- REST API endpoints for external IoT agents.
- Token-based agent registration and heartbeat.
- Job polling and result reporting.
- Support for virtual IoT agents on Windows/Linux.
- Automatic device synchronization from the external agent.
    """,
    "version": "17.0.2.0.0",
    "category": "Technical/IoT",
    "author": "JDA Solutions",
    "website": "https://github.com/julesprog963-stack/Iot_box_community",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/iot_menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "community_iot_box/static/src/scss/community_iot_box.scss",
        ],
    },
    "application": True,
    "installable": True,
}
