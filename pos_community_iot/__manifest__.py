{
    "name": "POS Community IoT",
    "summary": "Bridge Point of Sale printing to Community IoT devices.",
    "description": "Send POS receipt and preparation print jobs to Community IoT devices.",
    "version": "18.0.1.0.0",
    "category": "Point of Sale",
    "author": "JDA SOLUTIONS",
    "maintainer": "JDA SOLUTIONS",
    "website": "https://github.com/julesprog963-stack/Iot_box_community",
    "support": "julesprog963@gmail.com",
    "license": "LGPL-3",
    "images": ["static/description/main_screenshot.gif", "static/description/main_screenshot.png"],
    "depends": ["point_of_sale", "community_iot_box"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/pos_printer_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_community_iot/static/src/css/receipt_iot.css",
            "pos_community_iot/static/src/js/receipt_iot_common.js",
            "pos_community_iot/static/src/js/receipt_iot_patch.js",
            "pos_community_iot/static/src/js/preparation_iot_patch.js",
        ],
    },
    "installable": True,
    "application": False,
}
