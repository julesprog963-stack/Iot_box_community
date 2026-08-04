/** @odoo-module **/

import { makeContext } from "@web/core/context";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { onWillStart, onWillUpdateProps, useState } from "@odoo/owl";

patch(ActionMenus.prototype, {
    setup() {
        super.setup(...arguments);
        this.communityIotState = useState({ items: [] });
        onWillStart(() => this.loadCommunityIotItems(this.props));
        onWillUpdateProps((nextProps) => this.loadCommunityIotItems(nextProps));
    },

    async loadCommunityIotItems(props) {
        const printActions = props.items.print || [];
        if (!printActions.length) {
            this.communityIotState.items = [];
            return;
        }
        const actionIds = printActions.map((action) => action.id);
        const validIds = await this.orm.call(
            "ir.actions.report",
            "get_community_iot_pdf_action_ids",
            [actionIds, props.resModel]
        );
        this.communityIotState.items = printActions
            .filter((action) => validIds.includes(action.id))
            .map((action) => ({
                action,
                description: action.name,
                key: `community-iot-${action.id}`,
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
