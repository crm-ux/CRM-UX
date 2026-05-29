/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

function patchNewButton(Controller, modelName) {
    patch(Controller.prototype, {
        setup() {
            super.setup(...arguments);
            this.actionService = useService("action");
        },
        async openNewRecord() {
            if (this.model?.root?.resModel === modelName || 
                this.props?.resModel === modelName) {
                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: "Lead Creation",
                    res_model: "crm.lead.wizard",
                    view_mode: "form",
                    target: "new",
                    context: { default_step: 1 },
                });
                return;
            }
            return super.openNewRecord(...arguments);
        },
    });
}

patchNewButton(KanbanController, "crm.lead");
patchNewButton(ListController, "crm.lead");
