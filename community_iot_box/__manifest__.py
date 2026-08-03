{
    "name": "IoT Box Community",
    "summary": "Manage IoT Boxes, devices and print jobs in Odoo 17 Community.",
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
    "version": "17.0.4.0.1",
    "category": "Technical/IoT",
    "author": "JDA SOLUTIONS",
    "maintainer": "JDA SOLUTIONS",
    "website": "https://github.com/julesprog963-stack/Iot_box_community",
    "support": "julesprog963@gmail.com",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "images": [
        "static/description/images/main_screenshot.png",
        "static/description/images/iot_boxes.png",
        "static/description/images/iot_devices.png",
        "static/description/images/iot_jobs.png",
        "static/description/images/iot_box_configuration.png",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/iot_menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "community_iot_box/static/src/xml/iot_dashboard.xml",
            "community_iot_box/static/src/js/iot_dashboard.js",
            "community_iot_box/static/src/scss/community_iot_box.scss",
        ],
    },
    "application": True,
    "installable": True,
}
