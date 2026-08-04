/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { renderToElement } from "@web/core/utils/render";
import { Order } from "@point_of_sale/app/store/models";

patch(Order.prototype, {
    async printChanges(cancelled) {
        const orderChange = this.changesToOrder(cancelled);
        let isPrintSuccessful = true;
        const currentDate = new Date();
        let hours = `${currentDate.getHours()}`;
        let minutes = `${currentDate.getMinutes()}`;
        hours = hours.length < 2 ? `0${hours}` : hours;
        minutes = minutes.length < 2 ? `0${minutes}` : minutes;

        for (const printer of this.pos.unwatched.printers) {
            const changes = this._getPrintingCategoriesChanges(
                printer.config.product_categories_ids,
                orderChange
            );
            if (changes.new.length === 0 && changes.cancelled.length === 0) {
                continue;
            }

            const printingChanges = {
                new: changes.new,
                cancelled: changes.cancelled,
                table_name: this.pos.config.module_pos_restaurant ? this.getTable().name : false,
                floor_name: this.pos.config.module_pos_restaurant ? this.getTable().floor.name : false,
                name: this.name || "unknown order",
                time: { hours, minutes },
            };

            if (printer.config.community_iot_enabled && printer.config.community_iot_device_id) {
                try {
                    const result = await this.pos.orm.call(
                        "pos.printer",
                        "action_pos_community_iot_print_preparation",
                        [
                            [printer.config.id],
                            {
                                order_ref: this.name || "unknown order",
                                order_server_id: this.backendId || false,
                                printing_changes: printingChanges,
                            },
                        ]
                    );
                    if (!result?.success) {
                        isPrintSuccessful = false;
                    } else {
                        continue;
                    }
                } catch (error) {
                    console.warn("Community IoT preparation print failed.", error);
                    isPrintSuccessful = false;
                }
            }

            const receipt = renderToElement("point_of_sale.OrderChangeReceipt", {
                changes: printingChanges,
            });
            const result = await printer.printReceipt(receipt);
            if (!result.successful) {
                isPrintSuccessful = false;
            }
        }

        return isPrintSuccessful;
    },
});
