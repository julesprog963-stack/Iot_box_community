/** @odoo-module **/

import { makeContext } from "@web/core/context";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { onWillStart, useState } from "@odoo/owl";

patch(ActionMenus.prototype, {
    setup() {
        super.setup(...arguments);
        this.communityIotState = useState({ items: [], allowed: false });
        onWillStart(async () => {
            this.communityIotState.allowed = await user.hasGroup(
                "community_iot_printing.group_community_iot_print_user"
            );
        });
    },

    async loadCommunityIotItems() {
        // Reuse Odoo's lazy domain filtering before applying the IoT PDF filter.
        const availableItems = await this.loadAvailablePrintItems();
        const actionIds = availableItems
            .filter((item) => item.action?.id)
            .map((item) => item.action.id);
        if (!actionIds.length) {
            this.communityIotState.items = [];
            return;
        }
        const validIds = await this.orm.call(
            "ir.actions.report",
            "get_community_iot_pdf_action_ids",
            [actionIds, this.props.resModel]
        );
        this.communityIotState.items = availableItems
            .filter((item) => validIds.includes(item.action?.id))
            .map((item) => ({
                action: item.action,
                description: item.description,
                key: `community-iot-${item.action.id}`,
            }));
    },

    async onCommunityIotItemSelected(item) {
        if (!(await this.props.shouldExecuteAction(item))) {
            return;
        }
        let activeIds = this.props.getActiveIds();
        if (this.props.isDomainSelected) {
            activeIds = await this.orm.search(this.props.resModel, this.props.domain, {
                limit: Math.min(session.active_ids_limit, 101),
                context: this.props.context,
            });
        }
        const activeContext = {
            active_id: activeIds[0],
            active_ids: activeIds,
            active_model: this.props.resModel,
        };
        const context = makeContext([this.props.context, activeContext]);
        const wizardAction = await this.orm.call(
            "ir.actions.report",
            "action_open_community_iot_print_wizard",
            [item.action.id, this.props.resModel, activeIds],
            { context }
        );
        return this.actionService.doAction(wizardAction, {
            onClose: this.props.onActionExecuted,
        });
    },
});
