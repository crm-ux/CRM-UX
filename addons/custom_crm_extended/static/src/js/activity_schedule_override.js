/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityListPopover } from "@mail/core/web/activity_list_popover";

// Intercept popover open on the clock cell so we know the clicked record with 100% certainty!
let lastClickedActivityInfo = null;

document.addEventListener("click", function (ev) {
    // When user clicks the clock icon/cell in the list view table
    const cell = ev.target.closest("td[name='activity_ids'], .o_activity_cell, [name='activity_ids']");
    if (cell) {
        const row = cell.closest("tr");
        if (row) {
            // Find record data from Odoo Owl component tree or cell dataset
            const odooEnv = window.odoo?.__WOWL_DEBUG__?.root?.env;
            const records = odooEnv?.model?.root?.records || [];
            const dpId = row.dataset?.id;
            let foundRecord = records.find(r => r.id === dpId);

            if (foundRecord) {
                lastClickedActivityInfo = {
                    resModel: foundRecord.resModel,
                    resId: foundRecord.resId,
                    data: foundRecord.data || {},
                };
            } else {
                // Read from table cell or row link
                const link = row.querySelector("a[href*='id='], button[data-id]");
                let id = link?.dataset?.id;
                if (!id && link) {
                    const m = link.getAttribute("href")?.match(/id=(\d+)/);
                    if (m) id = m[1];
                }
                lastClickedActivityInfo = {
                    resModel: odooEnv?.searchModel?.resModel || "crm.lead",
                    resId: id ? Number(id) : false,
                    data: {},
                };
            }
        }
    }
}, true);

// Component Patch for ActivityListPopover
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

            // 1. Resolve resModel and resId
            let resModel = 
                lastClickedActivityInfo?.resModel || 
                this.props.activityList?.resModel || 
                this.props.resModel || 
                this.props.record?.resModel ||
                this.env?.searchModel?.resModel;

            let resId = 
                lastClickedActivityInfo?.resId || 
                this.props.activityList?.resId || 
                this.props.resId || 
                this.props.record?.resId;

            if (Array.isArray(resId)) {
                resId = resId[0];
            }

            const actionService = this.env?.services?.action;
            const orm = this.env?.services?.orm;

            // 2. If it is crm.lead, inspect if it's in Quote stage or has a Quote
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

                        // Quote stage detection (stage 6 to 10 or quote exists)
                        if (seq > 5 || seq >= 50 || quoteIds.length > 0) {
                            resModel = "sale.order";
                            if (quoteIds.length > 0) {
                                resId = quoteIds[quoteIds.length - 1]; // Latest quote
                            }
                        }
                    }
                } catch (e) {
                    console.error("[Assign Work Detection Error]:", e);
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
            }

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
