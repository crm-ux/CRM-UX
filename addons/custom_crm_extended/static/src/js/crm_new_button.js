/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";

const CRM_LEAD_MODEL = "crm.lead";
const WIZARD_ACTION = "custom_crm_extended.action_crm_lead_wizard";

async function openLeadCreationWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

const CRM_TASK_MODEL = "crm.task.management";

function patchNewButton(Controller, modelName) {
    patch(Controller.prototype, {
        async openNewRecord() {
            if (
                this.model?.root?.resModel === modelName ||
                this.props?.resModel === modelName
            ) {
                await openLeadCreationWizard(this.env);
                return;
            }
            if (
                this.model?.root?.resModel === CRM_TASK_MODEL ||
                this.props?.resModel === CRM_TASK_MODEL
            ) {
                // Open dashboard with assign work modal trigger
                window.__openAssignWorkModal = true;
                await this.env.services.action.doAction("crm_whitelabel.action_crm_whitelabel_dashboard");
                return;
            }
            return super.openNewRecord(...arguments);
        },
    });
}

patch(FormController.prototype, {
    async create() {
        if (this.props.resModel === CRM_LEAD_MODEL) {
            const dirty = await this.model.root.isDirty();
            if (dirty) {
                const saved = await this.model.root.save({
                    onError: this.onSaveError.bind(this),
                });
                if (!saved) {
                    return;
                }
            }
            await openLeadCreationWizard(this.env);
            return;
        }
        if (this.props.resModel === CRM_TASK_MODEL) {
            window.__openAssignWorkModal = true;
            await this.env.services.action.doAction("crm_whitelabel.action_crm_whitelabel_dashboard");
            return;
        }
        return super.create(...arguments);
    },
});

patchNewButton(KanbanController, CRM_LEAD_MODEL);
patchNewButton(ListController, CRM_LEAD_MODEL);
