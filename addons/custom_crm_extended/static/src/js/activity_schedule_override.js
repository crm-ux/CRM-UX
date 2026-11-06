/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityListPopover } from "@mail/core/web/activity_list_popover";

// When clicking the clock cell on the list view table, record the active row
let activeRowInfo = null;

document.addEventListener("click", function (ev) {
    const cell = ev.target.closest("td[name='activity_ids'], .o_activity_cell, [name='activity_ids']");
    if (cell) {
        const row = cell.closest("tr");
        if (row) {
            const odooEnv = window.odoo?.__WOWL_DEBUG__?.root?.env;
            const records = odooEnv?.model?.root?.records || [];
            const dpId = row.dataset?.id;
            const rec = records.find(r => r.id === dpId);
            if (rec) {
                activeRowInfo = {
                    resModel: rec.resModel,
                    resId: rec.resId,
                    data: rec.data || {},
                };
            }
        }
    }
}, true);

// 1. Direct Component Patch: Replace onClickSchedule entirely
if (ActivityListPopover && ActivityListPopover.prototype) {
    patch(ActivityListPopover.prototype, {
        async onClickSchedule(ev) {
            if (ev) {
                ev.preventDefault();
                ev.stopPropagation();
            }

            if (typeof this.props.close === "function") {
                this.props.close();
            }

            let resModel = activeRowInfo?.resModel || 
                           this.props.activityList?.resModel || 
                           this.props.resModel || 
                           this.props.record?.resModel || 
                           this.env?.searchModel?.resModel;

            let resId = activeRowInfo?.resId || 
                        this.props.activityList?.resId || 
                        this.props.resId || 
                        this.props.record?.resId;

            if (Array.isArray(resId)) {
                resId = resId[0];
            }

            const orm = this.env?.services?.orm;

            // Check if this is a Lead in quote stage (stages 6-10) or has an existing quotation
            if (resModel === "crm.lead" && resId && orm) {
                try {
                    const leads = await orm.read("crm.lead", [Number(resId)], [
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
                            resModel = "sale.order";
                            if (quoteIds.length > 0) {
                                resId = quoteIds[quoteIds.length - 1];
                            }
                        }
                    }
                } catch (err) {
                    console.error("[Assign Work Lead Check]:", err);
                }
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
                default_res_id: resId ? Number(resId) : false,
                active_model: resModel,
                active_id: resId ? Number(resId) : false,
            };

            if (resModel && modelFieldMap[resModel] && resId) {
                context[modelFieldMap[resModel]] = Number(resId);
                if (resModel === "service.ticket") context["default_ticket_id"] = Number(resId);
                if (resModel === "crm.lead") context["default_lead_id"] = Number(resId);
                if (resModel === "sale.order") context["default_order_id"] = Number(resId);
            }

            const actionService = this.env?.services?.action;
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
        },
    });
}
