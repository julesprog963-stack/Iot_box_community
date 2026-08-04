{
    "name": "IoT Box Community",
    "summary": "Manage IoT Boxes, devices and print jobs in Odoo 19 Community.",
    "description": """
Community IoT Box for Odoo 19 Community.

Features:
- IoT Boxes, IoT Devices and IoT Jobs.
- REST API endpoints for external IoT agents.
- Token-based agent registration and heartbeat.
- Job polling and result reporting.
- External IoT Box Community Agent on Linux hosts.
- Windows support is outside the validated scope of this release.
- Automatic device synchronization from the external agent.
    """,
    "version": "19.0.2.0.0",
    "category": "Technical/IoT",
    "author": "JDA SOLUTIONS",
    "maintainer": "JDA SOLUTIONS",
    "website": "https://github.com/julesprog963-stack/Iot_box_community",
    "support": "julesprog963@gmail.com",
    "license": "LGPL-3",
    "price": 0.0,
    "currency": "USD",
    "depends": ["base", "web"],
    "images": [
        "static/description/main_screenshot.png",
        "static/description/images/main_screenshot.gif",
        "static/description/images/dashboard_screenshot.png",
        "static/description/images/iot_boxes.png",
        "static/description/images/iot_devices.png",
        "static/description/images/iot_jobs.png",
        "static/description/images/iot_box_configuration.png",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/iot_cron.xml",
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
