/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { printReceiptViaCommunityIot, shouldUseCommunityIotReceipt } from "@pos_community_iot/js/receipt_iot_common";

patch(PosStore.prototype, {
    async printReceipt(options = {}) {
        const order = options.order || this.get_order();
        if (shouldUseCommunityIotReceipt(this.config) && order) {
            const props = {
                data: this.orderExportForPrinting(order),
                formatCurrency: this.env.utils.formatCurrency,
                basic_receipt: options.basic || false,
            };
            try {
                const handled = await printReceiptViaCommunityIot({
                    pos: this,
                    renderer: this.printer.renderer,
                    component: OrderReceipt,
                    props,
                });
                if (handled) {
                    if (!options.printBillActionTriggered) {
                        order.nb_print += 1;
                        if (typeof order.id === "number") {
                            await this.data.write("pos.order", [order.id], {
                                nb_print: order.nb_print,
                            });
                        }
                    }
                    return true;
                }
            } catch (error) {
                console.warn(
                    "Community IoT receipt print failed, falling back to default printer.",
                    error
                );
            }
        }
        return super.printReceipt(...arguments);
    },
});
