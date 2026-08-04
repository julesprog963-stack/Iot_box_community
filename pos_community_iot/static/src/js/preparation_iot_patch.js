/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    async printReceipts(order, printer, title, lines, fullReceipt = false, diningModeUpdate) {
        if (printer.config.community_iot_enabled && printer.config.community_iot_device_id) {
            const now = new Date();
            const isCancellation = /cancel|remove/i.test(title || "");
            const printingChanges = {
                new: isCancellation ? [] : lines,
                cancelled: isCancellation ? lines : [],
                name: order.name || "unknown order",
                table_name: order.table_id?.table_number || "",
                floor_name: order.table_id?.floor_id?.name || "",
                time: {
                    hours: String(now.getHours()).padStart(2, "0"),
                    minutes: String(now.getMinutes()).padStart(2, "0"),
                },
                operational_title: title,
                full_receipt: fullReceipt,
                dining_mode_update: diningModeUpdate,
            };
            try {
                const result = await this.data.call(
                    "pos.printer",
                    "action_pos_community_iot_print_preparation",
                    [[printer.config.id], {
                        order_ref: order.name || "unknown order",
                        order_server_id: typeof order.id === "number" ? order.id : false,
                        printing_changes: printingChanges,
                    }]
                );
                if (result?.success) {
                    return true;
                }
            } catch (error) {
                console.warn(
                    "Community IoT preparation print failed, falling back to the configured printer.",
                    error
                );
            }
        }
        return super.printReceipts(...arguments);
    },
});
