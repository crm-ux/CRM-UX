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

// Helper to extract the actual database ID (integer) from Odoo 18 popover props or records
function extractDatabaseId(popoverComponent) {
    const props = popoverComponent.props || {};
    // 1. Direct resId on activityList or props
    let id = props.activityList?.resId || props.resId || props.record?.resId;
    if (id && Number.isInteger(Number(id)) && Number(id) > 0) {
        return Number(id);
    }

    // 2. From record object
    if (props.record) {
        if (props.record.resId && Number(props.record.resId) > 0) {
            return Number(props.record.resId);
        }
        if (props.record.data?.id && Number(props.record.data.id) > 0) {
            return Number(props.record.data.id);
        }
    }

    // 3. From activity objects if any exist in the popover
    const activities = props.activityList?.activities || props.activities || [];
    if (activities.length > 0 && activities[0].res_id) {
        return Number(activities[0].res_id);
    }

    // 4. From active row DOM element
    const activeRow = document.querySelector(".o_data_row.o_selected_row, .o_data_row:hover");
    if (activeRow) {
        // Find if any cell or link in the row contains the record ID
        const rowId = activeRow.dataset?.id;
        // Check if there is an anchor or span with record id
        const linkWithId = activeRow.querySelector("a[href*='id='], button[data-id]");
        if (linkWithId) {
            const match = linkWithId.getAttribute("href")?.match(/id=(\d+)/) || linkWithId.dataset?.id;
            if (match) {
                return Number(Array.isArray(match) ? match[1] : match);
            }
        }
        // In Odoo datapoint, find record in odooEnv
        const odooEnv = window.odoo?.__WOWL_DEBUG__?.root?.env;
        if (odooEnv?.model?.root?.records) {
            const matchedRec = odooEnv.model.root.records.find(r => r.id === rowId);
            if (matchedRec && matchedRec.resId) {
                return Number(matchedRec.resId);
            }
        }
    }

    return false;
}

// Helper to extract the model
function extractModel(popoverComponent) {
    const props = popoverComponent.props || {};
    let model = props.activityList?.resModel || props.resModel || props.record?.resModel;
    if (model && TARGET_MODELS.includes(model)) {
        return model;
    }

    const odooEnv = window.odoo?.__WOWL_DEBUG__?.root?.env;
    let envModel = odooEnv?.searchModel?.resModel || odooEnv?.model?.root?.resModel;
    if (envModel && TARGET_MODELS.includes(envModel)) {
        return envModel;
    }

    const url = window.location.href;
    for (const m of TARGET_MODELS) {
        if (url.includes(m)) {
            return m;
        }
    }
    return "crm.lead";
}

// 1. Direct Component Patch
if (ActivityListPopover && ActivityListPopover.prototype) {
    patch(ActivityListPopover.prototype, {
        onClickSchedule(ev) {
            if (ev) {
                ev.preventDefault();
                ev.stopPropagation();
            }

            if (typeof this.props.close === "function") {
                this.props.close();
            }

            const resModel = extractModel(this);
            const resId = extractDatabaseId(this);

            const context = {
                default_related_model: resModel,
                default_res_id: resId || false,
                active_model: resModel,
                active_id: resId || false,
            };

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

// 2. DOM Capture-phase listener
document.addEventListener("click", function (ev) {
    const btn = ev.target.closest(".o-mail-ActivityListPopover button");
    if (!btn) {
        return;
    }
    const txt = btn.textContent || "";
    if (!txt.includes("Schedule an activity")) {
        return;
    }

    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation();

    const popover = btn.closest(".o-mail-ActivityListPopover");
    if (popover) {
        const parent = popover.closest(".o_popover") || popover.parentElement;
        if (parent) {
            parent.remove();
        }
    }

    const odooEnv = window.odoo?.__WOWL_DEBUG__?.root?.env;
    let resModel = odooEnv?.searchModel?.resModel;
    let resId = false;

    // Detect actual database record ID from hovered row in model root records
    const row = document.querySelector(".o_data_row:hover, .o_data_row.o_selected_row");
    if (row && odooEnv?.model?.root?.records) {
        const dpId = row.dataset?.id;
        const rec = odooEnv.model.root.records.find(r => r.id === dpId);
        if (rec && rec.resId) {
            resId = rec.resId;
        }
    }

    if (!resModel) {
        const url = window.location.href;
        for (const m of TARGET_MODELS) {
            if (url.includes(m)) {
                resModel = m;
                break;
            }
        }
    }

    const context = {
        default_related_model: resModel || "crm.lead",
        default_res_id: resId ? Number(resId) : false,
        active_model: resModel || "crm.lead",
        active_id: resId ? Number(resId) : false,
    };

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
