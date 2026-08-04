/** @odoo-module **/

import { loadAllImages } from "@point_of_sale/utils";
import { htmlToCanvas } from "@point_of_sale/app/printer/render_service";

function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error || new Error("Unable to read blob as data URL."));
        reader.readAsDataURL(blob);
    });
}

export function shouldUseCommunityIotReceipt(config) {
    return Boolean(
        config?.community_iot_enabled &&
            config?.community_iot_auto_receipt &&
            config?.community_iot_receipt_device_id
    );
}

export function communityIotReceiptRenderClass(config) {
    // Keep POS receipt rendering pinned to the stable 80mm layout.
    // The agent can still scale the final image down for the target printer.
    return "ciot-receipt-80mm";
}

export async function fetchUrlAsDataUrl(url) {
    const response = await fetch(url, { credentials: "include" });
    if (!response.ok) {
        throw new Error(`Unable to fetch image: ${url}`);
    }
    return await blobToDataUrl(await response.blob());
}

export async function renderComponentToJpeg({ renderer, component, props, addClass }) {
    if (!renderer?.toHtml) {
        throw new Error("POS renderer service is not available.");
    }

    const element = await renderer.toHtml(component, props);
    try {
        await loadAllImages(element);
    } catch (error) {
        console.warn("Community IoT could not preload one or more receipt images.", error);
    }
    const canvas = await htmlToCanvas(element, { addClass });
    return canvas.toDataURL("image/jpeg").replace("data:image/jpeg;base64,", "");
}

export async function printReceiptViaCommunityIot({ pos, renderer, component, props }) {
    const config = pos?.config;
    const currentOrder = props?.order || pos?.get_order?.() || pos?.getOrder?.();
    const receiptData = props?.data || { name: currentOrder?.name || currentOrder?.get_name?.() };
    const orderRef = receiptData.name || currentOrder?.name || currentOrder?.get_name?.();
    const orderServerId =
        pos?.validated_orders_name_server_id_map?.[orderRef] ||
        currentOrder?.backendId ||
        currentOrder?.server_id ||
        (typeof currentOrder?.id === "number" ? currentOrder.id : false) ||
        false;

    if (!config?.id || !orderRef || !renderer?.toHtml) {
        return false;
    }

    const receiptImageBase64 = await renderComponentToJpeg({
        renderer,
        component,
        props,
        addClass: communityIotReceiptRenderClass(config),
    });
    const args = [[config.id], {
        order_ref: orderRef,
        order_server_id: orderServerId,
        receipt_data: receiptData,
        receipt_image_base64: receiptImageBase64,
        render_mode: "image",
        image_format: "jpeg",
        copies: config.community_iot_receipt_copies || 1,
    }];
    const result = pos.orm?.call
        ? await pos.orm.call("pos.config", "action_pos_community_iot_print_receipt", args)
        : await pos.data.call("pos.config", "action_pos_community_iot_print_receipt", args);
    return Boolean(result?.success);
}
