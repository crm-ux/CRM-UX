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

const MODEL_FIELD_MAP = {
    "crm.lead": "default_lead_id",
    "sale.order": "default_order_id",
    "res.partner": "default_partner_id",
    "equipment.master": "default_equipment_id",
    "service.ticket": "default_ticket_id",
    "amc.contract": "default_amc_id",
};

patch(ActivityListPopover.prototype, {
    onClickSchedule(ev) {
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }

        // 1. Resolve resModel and resId across all Odoo 18 prop structures
        let resModel = 
            this.props?.activityList?.resModel || 
            this.props?.activitylist?.resModel || 
            this.props?.resModel || 
            this.props?.record?.resModel ||
            this.env?.model?.root?.resModel ||
            (this.env?.searchModel && this.env.searchModel.resModel);

        let resId = 
            this.props?.activityList?.resId || 
            this.props?.activitylist?.resId || 
            this.props?.resId || 
            this.props?.record?.resId ||
            (this.props?.record && this.props.record.id);

        // Fallback: Check if resId was passed as an array or object
        if (Array.isArray(resId)) {
            resId = resId[0];
        }

        // 2. If it belongs to any of our 6 entities, redirect to Assign Work Wizard
        if (resModel && TARGET_MODELS.includes(resModel)) {
            if (typeof this.props.close === "function") {
                this.props.close();
            }

            const context = {
                default_related_model: resModel,
                default_res_id: resId ? Number(resId) : false,
                active_model: resModel,
                active_id: resId ? Number(resId) : false,
            };

            if (MODEL_FIELD_MAP[resModel] && resId) {
                context[MODEL_FIELD_MAP[resModel]] = Number(resId);
            }

            const actionService = this.env?.services?.action || this.action;
            if (actionService) {
                return actionService.doAction({
                    type: "ir.actions.act_window",
                    name: "Assign Work",
                    res_model: "crm.task.assign.wizard",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context: context,
                });
            }
        }

        // Standard fallback for any other non-target models
        return super.onClickSchedule ? super.onClickSchedule(...arguments) : null;
    },
});
