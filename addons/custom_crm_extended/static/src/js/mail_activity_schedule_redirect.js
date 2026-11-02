/** @odoo-module **/

import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";

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

class MailActivityScheduleRedirectController extends FormController {
    setup() {
        super.setup();
        const resModel = this.props.context?.active_model || this.props.context?.default_res_model;
        const resId = this.props.context?.active_id || this.props.context?.default_res_id;

        // If native schedule activity dialog opens for any of our 6 entities:
        // Instantly replace it with our custom Assign Work wizard!
        if (resModel && TARGET_MODELS.includes(resModel)) {
            Promise.resolve().then(async () => {
                let finalModel = resModel;
                let finalId = resId;

                if (resModel === "crm.lead" && resId && this.env.services.orm) {
                    try {
                        const leads = await this.env.services.orm.read("crm.lead", [Number(resId)], [
                            "x_stage_sequence",
                            "stage_id",
                            "sale_order_ids",
                            "order_ids",
                            "sale_order_id"
                        ]);
                        if (leads && leads.length > 0) {
                            const lead = leads[0];
                            const seq = lead.x_stage_sequence || (Array.isArray(lead.stage_id) ? lead.stage_id[0] : 0);
                            const quoteIds = lead.order_ids || lead.sale_order_ids || (lead.sale_order_id ? [lead.sale_order_id[0]] : []);
                            if (seq > 5 || seq >= 50 || quoteIds.length > 0) {
                                finalModel = "sale.order";
                                if (quoteIds.length > 0) {
                                    finalId = quoteIds[quoteIds.length - 1];
                                }
                            }
                        }
                    } catch (e) {
                        console.error(e);
                    }
                }

                const ctx = {
                    default_related_model: finalModel,
                    default_res_id: finalId ? Number(finalId) : false,
                    active_model: finalModel,
                    active_id: finalId ? Number(finalId) : false,
                };

                if (finalModel && MODEL_FIELD_MAP[finalModel] && finalId) {
                    ctx[MODEL_FIELD_MAP[finalModel]] = Number(finalId);
                }

                // Close the native wizard dialog
                if (this.env.dialogData && this.env.dialogData.close) {
                    this.env.dialogData.close();
                }

                // Open our custom Assign Work wizard
                this.env.services.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Assign Work",
                    res_model: "crm.task.assign.wizard",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context: ctx,
                });
            });
        }
    }
}

registry.category("views").add("mail_activity_schedule_redirect", {
    ...formView,
    Controller: MailActivityScheduleRedirectController,
});

