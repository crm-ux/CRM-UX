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
        let resModel = this.props.activityList?.resModel || 
                       this.props.activitylist?.resModel || 
                       this.props.resModel || 
                       (this.props.record && this.props.record.resModel);

        let resId = this.props.activityList?.resId || 
                     this.props.activitylist?.resId || 
                     this.props.resId || 
                     (this.props.record && this.props.record.resId);

        if (!resModel && this.props.record) {
            resModel = this.props.record.resModel;
            resId = this.props.record.resId;
        }

        if (resModel && TARGET_MODELS.includes(resModel)) {
            if (ev) {
                ev.preventDefault();
                ev.stopPropagation();
            }
            if (this.props.close) {
                this.props.close();
            }

            const context = {
                default_related_model: resModel,
                default_res_id: resId,
                active_model: resModel,
                active_id: resId,
            };

            if (MODEL_FIELD_MAP[resModel] && resId) {
                context[MODEL_FIELD_MAP[resModel]] = resId;
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

        return super.onClickSchedule ? super.onClickSchedule(...arguments) : null;
    },
});

// Also intercept activityService.scheduleActivity directly for global safety
import { ActivityService } from "@mail/core/web/activity_service";

if (ActivityService && ActivityService.prototype) {
    patch(ActivityService.prototype, {
        async scheduleActivity(resModel, resId, defaultActivityTypeId) {
            if (resModel && TARGET_MODELS.includes(resModel)) {
                const context = {
                    default_related_model: resModel,
                    default_res_id: resId,
                    active_model: resModel,
                    active_id: resId,
                };
                if (MODEL_FIELD_MAP[resModel] && resId) {
                    context[MODEL_FIELD_MAP[resModel]] = resId;
                }
                return this.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Assign Work",
                    res_model: "crm.task.assign.wizard",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context: context,
                });
            }
            return super.scheduleActivity(...arguments);
        },
    });
}
