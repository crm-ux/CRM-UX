/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { listView } from "@web/views/list/list_view";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";

const WIZARD_ACTION = "custom_crm_extended.action_crm_lead_wizard";

async function openLeadWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

export class CrmLeadFormController extends FormController {
    async create() {
        if (this.props.resModel === "crm.lead") {
            const dirty = await this.model.root.isDirty();
            if (dirty) {
                const saved = await this.model.root.save({
                    onError: this.onSaveError.bind(this),
                });
                if (!saved) {
                    return;
                }
            }
            await openLeadWizard(this.env);
            return;
        }
        return super.create(...arguments);
    }
}

export class CrmLeadListController extends ListController {
    async createRecord() {
        if (this.props.resModel === "crm.lead") {
            await openLeadWizard(this.env);
            return;
        }
        return super.createRecord(...arguments);
    }

    async openNewRecord() {
        if (this.props.resModel === "crm.lead") {
            await openLeadWizard(this.env);
            return;
        }
        return super.openNewRecord(...arguments);
    }
}

export class CrmLeadKanbanController extends KanbanController {
    async createRecord() {
        if (this.props.resModel === "crm.lead") {
            await openLeadWizard(this.env);
            return;
        }
        return super.createRecord(...arguments);
    }

    async openNewRecord() {
        if (this.props.resModel === "crm.lead") {
            await openLeadWizard(this.env);
            return;
        }
        return super.openNewRecord(...arguments);
    }
}

registry.category("views").add("crm_lead_form", {
    ...formView,
    Controller: CrmLeadFormController,
});

registry.category("views").add("crm_lead_list", {
    ...listView,
    Controller: CrmLeadListController,
});

registry.category("views").add("crm_lead_kanban", {
    ...kanbanView,
    Controller: CrmLeadKanbanController,
});
