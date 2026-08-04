{
    "name": "Community IoT Printing",
    "summary": "Print any Odoo PDF report through IoT Box Community.",
    "version": "17.0.1.0.0",
    "category": "Technical/IoT",
    "author": "JDA SOLUTIONS",
    "maintainer": "JDA SOLUTIONS",
    "website": "https://github.com/julesprog963-stack/Iot_box_community",
    "support": "julesprog963@gmail.com",
    "license": "LGPL-3",
    "images": ["static/description/main_screenshot.gif", "static/description/main_screenshot.png"],
    "depends": ["base", "web", "community_iot_box"],
    "data": [
        "security/community_iot_printing_security.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "wizard/community_iot_print_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "community_iot_printing/static/src/js/iot_action_menus.js",
            "community_iot_printing/static/src/xml/iot_action_menus.xml",
        ],
    },
    "application": False,
    "installable": True,
}
