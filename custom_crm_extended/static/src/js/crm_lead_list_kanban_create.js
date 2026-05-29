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
