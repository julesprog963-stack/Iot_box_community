/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


export class CommunityIotDashboard extends Component {
    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = useState({
            data: {
                metrics: {},
                boxes: [],
                jobs: [],
                alerts: [],
            },
            loading: true,
            error: false,
        });

        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.error = false;
        try {
            this.state.data = await this.orm.call(
                "community_iot_box.iot_box",
                "get_dashboard_data",
                []
            );
        } catch (error) {
            this.state.error = true;
            this.notification.add(
                "No fue posible cargar el panel de IoT Box Community.",
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    openBoxes() {
        return this.actionService.doAction(
            "community_iot_box.action_community_iot_boxes"
        );
    }

    openDevices() {
        return this.actionService.doAction(
            "community_iot_box.action_community_iot_devices"
        );
    }

    openJobs() {
        return this.actionService.doAction(
            "community_iot_box.action_community_iot_jobs"
        );
    }

    openBox(boxId) {
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "community_iot_box.iot_box",
            res_id: boxId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    createBox() {
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Nueva IoT Box",
            res_model: "community_iot_box.iot_box",
            views: [[false, "form"]],
            target: "current",
        });
    }

    boxStateClass(state) {
        return `o_ciot_status_${state || "draft"}`;
    }

    jobStateClass(state) {
        return `o_ciot_job_status_${state || "pending"}`;
    }
}

CommunityIotDashboard.template = "community_iot_box.Dashboard";

registry
    .category("actions")
    .add("community_iot_box.dashboard", CommunityIotDashboard);
