/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { AssignWorkModalDialog } from "@crm_whitelabel/js/assign_work_dialog";

const CRM_LEAD_MODEL = "crm.lead";
const CRM_TASK_MODEL = "crm.task.management";
const WIZARD_ACTION = "custom_crm_extended.action_crm_lead_wizard";

async function openLeadCreationWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

function openTaskAssignDialog(controller) {
    controller.env.services.dialog.add(AssignWorkModalDialog, {
        onSuccess: async () => {
            if (controller.model?.load) {
                await controller.model.load();
            } else if (controller.model?.root?.load) {
                await controller.model.root.load();
            }
        },
    });
}

// 1. Intercept List / Tree View "New" button
patch(ListController.prototype, {
    async createRecord() {
        if (
            this.model?.root?.resModel === CRM_TASK_MODEL ||
            this.props?.resModel === CRM_TASK_MODEL
        ) {
            openTaskAssignDialog(this);
            return;
        }
        return super.createRecord(...arguments);
    },
    async openNewRecord() {
        if (
            this.model?.root?.resModel === CRM_LEAD_MODEL ||
            this.props?.resModel === CRM_LEAD_MODEL
        ) {
            await openLeadCreationWizard(this.env);
            return;
        }
        if (
            this.model?.root?.resModel === CRM_TASK_MODEL ||
            this.props?.resModel === CRM_TASK_MODEL
        ) {
            openTaskAssignDialog(this);
            return;
        }
        return super.openNewRecord(...arguments);
    },
});

// 2. Intercept Kanban View "New" button
patch(KanbanController.prototype, {
    async openNewRecord() {
        if (
            this.model?.root?.resModel === CRM_LEAD_MODEL ||
            this.props?.resModel === CRM_LEAD_MODEL
        ) {
            await openLeadCreationWizard(this.env);
            return;
        }
        if (
            this.model?.root?.resModel === CRM_TASK_MODEL ||
            this.props?.resModel === CRM_TASK_MODEL
        ) {
            openTaskAssignDialog(this);
            return;
        }
        return super.openNewRecord(...arguments);
    },
});

// 3. Intercept Form View "New" button
patch(FormController.prototype, {
    async create() {
        if (this.props?.resModel === CRM_LEAD_MODEL || this.model?.root?.resModel === CRM_LEAD_MODEL) {
            const dirty = await this.model?.root?.isDirty?.();
            if (dirty) {
                const saved = await this.model.root.save({
                    onError: this.onSaveError?.bind(this),
                });
                if (!saved) {
                    return;
                }
            }
            await openLeadCreationWizard(this.env);
            return;
        }
        if (this.props?.resModel === CRM_TASK_MODEL || this.model?.root?.resModel === CRM_TASK_MODEL) {
            openTaskAssignDialog(this);
            return;
        }
        return super.create(...arguments);
    },
});
