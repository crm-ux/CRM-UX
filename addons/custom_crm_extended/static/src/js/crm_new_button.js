/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";

const CRM_LEAD_MODEL = "crm.lead";
const CRM_TASK_MODEL = "crm.task.management";
const WIZARD_ACTION = "custom_crm_extended.action_crm_lead_wizard";

async function openLeadCreationWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

async function openTaskAssignWizard(env) {
    sessionStorage.setItem("crm_open_assign_work_modal", "true");
    window.__openAssignWorkModal = true;
    await env.services.action.doAction("crm_whitelabel.action_crm_dashboard", {
        clearBreadcrumbs: true,
    });
}

// 1. Intercept List / Tree View "New" button
patch(ListController.prototype, {
    async createRecord() {
        if (
            this.model?.root?.resModel === CRM_TASK_MODEL ||
            this.props?.resModel === CRM_TASK_MODEL
        ) {
            await openTaskAssignWizard(this.env);
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
            await openTaskAssignWizard(this.env);
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
            await openTaskAssignWizard(this.env);
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
            await openTaskAssignWizard(this.env);
            return;
        }
        return super.create(...arguments);
    },
});
