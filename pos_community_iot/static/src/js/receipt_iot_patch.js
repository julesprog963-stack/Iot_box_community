/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosPrinterService } from "@point_of_sale/app/printer/pos_printer_service";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { printReceiptViaCommunityIot, shouldUseCommunityIotReceipt } from "@pos_community_iot/js/receipt_iot_common";

patch(PosPrinterService.prototype, {
    async print(component, props, options) {
        if (this._shouldUseCommunityIotReceipt(component, props)) {
            const handled = await this._printReceiptViaCommunityIot(component, props);
            if (handled) {
                return true;
            }
        }
        return await super.print(component, props, options);
    },

    _shouldUseCommunityIotReceipt(component, props) {
        const config = this.pos?.config;
        return Boolean(
            shouldUseCommunityIotReceipt(config) &&
                (component === OrderReceipt || component?.template === OrderReceipt.template) &&
                props?.data
        );
    },

    async _printReceiptViaCommunityIot(component, props) {
        try {
            return await printReceiptViaCommunityIot({
                pos: this.pos,
                renderer: this.renderer,
                component,
                props,
            });
        } catch (error) {
            console.warn("Community IoT receipt print failed, falling back to default printer.", error);
            return false;
        }
    },
});
