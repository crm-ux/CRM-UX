/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// Wait for crm_kanban view to be registered then patch it
const viewRegistry = registry.category("views");

function patchCrmKanban() {
    const crmKanbanView = viewRegistry.get("crm_kanban");
    if (!crmKanbanView) return;

    const OriginalController = crmKanbanView.Controller;

    class PatchedCrmKanbanController extends OriginalController {
        setup() {
            super.setup(...arguments);
            this.actionService = useService("action");
        }
        async openNewRecord() {
            await this.env.services.action.doAction(
                "custom_crm_extended.action_crm_lead_wizard"
            );
        }
    }

    viewRegistry.add("crm_kanban", {
        ...crmKanbanView,
        Controller: PatchedCrmKanbanController,
    }, { force: true });
}

patchCrmKanban();
