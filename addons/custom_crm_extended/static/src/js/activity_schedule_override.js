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

// 1. Patch the component directly
if (ActivityListPopover && ActivityListPopover.prototype) {
    patch(ActivityListPopover.prototype, {
        onClickSchedule(ev) {
            if (ev) {
                ev.preventDefault();
                ev.stopPropagation();
            }

            // Close the popover
            if (typeof this.props.close === "function") {
                this.props.close();
            }

            const record = this.props.record || this.props.activityList?.record || {};
            const resModel = this.props.activityList?.resModel || 
                             this.props.resModel || 
                             record.resModel || 
                             this.env?.searchModel?.resModel;

            const resId = this.props.activityList?.resId || 
                          this.props.resId || 
                          record.resId || 
                          record.id;

            const finalResId = Array.isArray(resId) ? resId[0] : resId;

            const context = {
                default_related_model: resModel || false,
                default_res_id: finalResId ? Number(finalResId) : false,
                active_model: resModel || false,
                active_id: finalResId ? Number(finalResId) : false,
            };

            if (resModel && MODEL_FIELD_MAP[resModel] && finalResId) {
                context[MODEL_FIELD_MAP[resModel]] = Number(finalResId);
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

// 2. DOM Capture-phase safeguard: Catch click before native Owl handlers can fire
document.addEventListener("click", function (ev) {
    const btn = ev.target.closest(".o-mail-ActivityListPopover button");
    if (!btn) {
        return;
    }
    const txt = btn.textContent || "";
    if (!txt.includes("Schedule an activity")) {
        return;
    }

    // Stop native Odoo wizard
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();

    // Close the popover DOM
    const popover = btn.closest(".o-mail-ActivityListPopover");
    if (popover) {
        const parent = popover.closest(".o_popover") || popover.parentElement;
        if (parent) {
            parent.remove();
        }
    }

    // Read active view context
    const odooEnv = window.odoo?.__WOWL_DEBUG__?.root?.env;
    let resModel = odooEnv?.searchModel?.resModel;
    let resId = false;

    // Detect row
    const row = document.querySelector(".o_data_row:hover, .o_data_row.o_selected_row");
    if (row) {
        resId = row.dataset?.id || row.getAttribute("data-id");
    }

    // URL fallback for model
    const href = window.location.href;
    if (!resModel) {
        for (const m of TARGET_MODELS) {
            if (href.includes(m)) {
                resModel = m;
                break;
            }
        }
    }

    const context = {
        default_related_model: resModel || false,
        default_res_id: resId ? Number(resId) : false,
        active_model: resModel || false,
        active_id: resId ? Number(resId) : false,
    };

    if (resModel && MODEL_FIELD_MAP[resModel] && resId) {
        context[MODEL_FIELD_MAP[resModel]] = Number(resId);
    }

    const actionService = odooEnv?.services?.action;
    if (actionService) {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Assign Work",
            res_model: "crm.task.assign.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: context,
        });
    }
}, true);
