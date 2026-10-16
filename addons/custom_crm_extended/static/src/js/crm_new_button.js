/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { CalendarController } from "@web/views/calendar/calendar_controller";

const CRM_LEAD_MODEL = "crm.lead";
const CRM_TASK_MODEL = "crm.task.management";
const WIZARD_ACTION = "custom_crm_extended.action_crm_lead_wizard";
const TASK_WIZARD_ACTION = "custom_crm_extended.action_crm_task_assign_wizard";

async function openLeadCreationWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

async function openTaskAssignWizard(env, controller, extraContext = {}) {
    await env.services.action.doAction({
        type: "ir.actions.act_window",
        res_model: "crm.task.assign.wizard",
        views: [[false, "form"]],
        target: "new",
        name: "Assign Work",
        context: {
            ...extraContext,
        },
    }, {
        onClose: async () => {
            // Smoothly reload active controller model if present, otherwise reload action
            if (controller?.model?.load) {
                await controller.model.load();
            } else if (controller?.model?.root?.load) {
                await controller.model.root.load();
            } else if (env.services.action.currentController) {
                await env.services.action.currentController.model?.load?.() ||
                      env.services.action.currentController.model?.root?.load?.();
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
            await openTaskAssignWizard(this.env, this);
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
            await openTaskAssignWizard(this.env, this);
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
            await openTaskAssignWizard(this.env, this);
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
            await openTaskAssignWizard(this.env, this);
            return;
        }
        return super.create(...arguments);
    },
});

// 4. Intercept Calendar View "New" button & date cell click to open Assign Work Wizard with deadline pre-filled
patch(CalendarController.prototype, {
    async createRecord(record) {
        if (
            this.model?.resModel === CRM_TASK_MODEL ||
            this.props?.resModel === CRM_TASK_MODEL
        ) {
            let deadline = null;
            if (record?.start) {
                deadline = typeof record.start === "string" ? record.start.slice(0, 10) : record.start.toISODate?.() || record.start.format?.("YYYY-MM-DD");
            } else if (record?.date_deadline) {
                deadline = record.date_deadline;
            } else if (record?.date_start) {
                deadline = typeof record.date_start === "string" ? record.date_start.slice(0, 10) : null;
            }
            const context = deadline ? { default_date_deadline: deadline } : {};
            await openTaskAssignWizard(this.env, this, context);
            return;
        }
        return super.createRecord?.(...arguments);
    },
});
