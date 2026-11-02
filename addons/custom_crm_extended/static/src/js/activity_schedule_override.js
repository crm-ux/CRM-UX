/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityListPopover } from "@mail/core/web/activity_list_popover";

const TARGET_MODELS = [
    "crm.lead",
    "sale.order",
    "res.partner",
    "equipment.master",
    "service.ticket",
    "amc.contract",
];

patch(ActivityListPopover.prototype, {
    onClickSchedule(ev) {
        const resModel = this.props.activitylist?.resModel || this.props.resModel;
        const resId = this.props.activitylist?.resId || this.props.resId;

        if (resModel && TARGET_MODELS.includes(resModel)) {
            if (ev) {
                ev.preventDefault();
                ev.stopPropagation();
            }
            if (this.props.close) {
                this.props.close();
            }

            const modelFieldMap = {
                "crm.lead": "default_lead_id",
                "sale.order": "default_order_id",
                "res.partner": "default_partner_id",
                "equipment.master": "default_equipment_id",
                "service.ticket": "default_ticket_id",
                "amc.contract": "default_amc_id",
            };

            const context = {
                default_related_model: resModel,
                default_res_id: resId,
                active_model: resModel,
                active_id: resId,
            };

            if (modelFieldMap[resModel] && resId) {
                context[modelFieldMap[resModel]] = resId;
            }

            return this.env.services.action.doAction({
                type: "ir.actions.act_window",
                name: "Assign Work",
                res_model: "crm.task.assign.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: context,
            });
        }

        return super.onClickSchedule(...arguments);
    },
});

