/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async printOrderChanges(data, printer) {
        if (printer.config.community_iot_enabled && printer.config.community_iot_device_id) {
            const title = data?.changes?.title || "Changes";
            const isCancellation = /cancel|remove/i.test(title);
            const changedLines = (data?.changes?.data || []).map((line) => ({
                name: line.name || line.product_name || line.display_name || "Item",
                quantity: Math.abs(line.quantity || line.qty || 1),
                note: line.note || line.customer_note || "",
            }));
            const now = new Date();
            const printingChanges = {
                new: isCancellation ? [] : changedLines,
                cancelled: isCancellation ? changedLines : [],
                // Odoo 19 preparation data exposes the POS order reference as
                // `pos_reference`; older payloads used `name` or `order_name`.
                name: data?.pos_reference || data?.name || data?.order_name || "unknown order",
                table_name: data?.table_name || "",
                floor_name: data?.floor_name || "",
                time: {
                    hours: String(now.getHours()).padStart(2, "0"),
                    minutes: String(now.getMinutes()).padStart(2, "0"),
                },
                operational_title: title,
            };
            try {
                const result = await this.data.call(
                    "pos.printer",
                    "action_pos_community_iot_print_preparation",
                    [[printer.config.id], {
                        order_ref: printingChanges.name,
                        printing_changes: printingChanges,
                    }]
                );
                if (result?.success) {
                    return { successful: true };
                }
            } catch (error) {
                console.warn(
                    "Community IoT preparation print failed, falling back to the configured printer.",
                    error
                );
            }
        }
        return super.printOrderChanges(...arguments);
    },
});
