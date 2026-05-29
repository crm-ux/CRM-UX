/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";

patch(KanbanController.prototype, {
    get canCreate() {
        if (this.props.resModel === "crm.lead") {
            return false;
        }
        return this.props.archInfo.activeActions.create;
    },
});
