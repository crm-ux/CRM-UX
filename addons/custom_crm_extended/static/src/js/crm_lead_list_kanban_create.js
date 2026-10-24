/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";

const WIZARD_ACTION = "custom_crm_extended.action_crm_lead_wizard";

async function openWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

export class CrmLeadListController extends ListController {
    async createRecord() {
        await openWizard(this.env);
    }

    async openNewRecord() {
        await openWizard(this.env);
    }

    async openRecord(record) {
        const leadId = record.resId;
        const orm = this.env.services.orm;
        const action = this.env.services.action;

        // Check stage sequence of the clicked lead
        const leadData = await orm.read("crm.lead", [leadId], ["stage_id"]);
        const stageId = leadData && leadData[0] && leadData[0].stage_id ? leadData[0].stage_id[0] : false;

        if (stageId) {
            const stages = await orm.read("crm.stage", [stageId], ["sequence"]);
            const seq = stages && stages[0] ? stages[0].sequence : 0;

            // If sequence is 30 or above (Quotes, Sent, Negotiation, Order Expected, Won)
            if (seq >= 30) {
                const quotes = await orm.searchRead(
                    "sale.order",
                    [["opportunity_id", "=", leadId]],
                    ["id"],
                    { order: "id desc", limit: 1 }
                );
                if (quotes && quotes.length) {
                    return action.doAction({
                        type: "ir.actions.act_window",
                        name: "Quotation",
                        res_model: "sale.order",
                        res_id: quotes[0].id,
                        views: [[false, "form"]],
                    });
                }
            }
        }
        return super.openRecord(...arguments);
    }

    async duplicateRecords() {
        const selectedResIds = await this.getSelectedResIds();
        if (selectedResIds && selectedResIds.length > 0) {
            const leadId = selectedResIds[0];
            const orm = this.env.services.orm;
            const action = this.env.services.action;

            // Check if this lead has a quotation
            const quotes = await orm.searchRead(
                "sale.order",
                [["opportunity_id", "=", leadId]],
                ["id"],
                { order: "id desc", limit: 1 }
            );

            if (quotes && quotes.length > 0) {
                return action.doAction("custom_crm_extended.action_sale_order_duplicate_wizard", {
                    additionalContext: {
                        default_order_id: quotes[0].id,
                    },
                });
            } else {
                // If lead has no quotation, duplicate the lead and open it
                const newLeadId = await orm.call("crm.lead", "copy", [leadId]);
                return action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "crm.lead",
                    res_id: newLeadId,
                    views: [[false, "form"]],
                    target: "current",
                });
            }
        }
        return super.duplicateRecords(...arguments);
    }
}

export class CrmLeadKanbanController extends KanbanController {
    async createRecord() {
        await openWizard(this.env);
    }

    async openNewRecord() {
        await openWizard(this.env);
    }
}

registry.category("views").add("crm_lead_list", {
    ...listView,
    Controller: CrmLeadListController,
});

registry.category("views").add("crm_lead_kanban", {
    ...kanbanView,
    Controller: CrmLeadKanbanController,
});
