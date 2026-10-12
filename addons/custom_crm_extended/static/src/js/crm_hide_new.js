/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ActionMenus } from "@web/search/action_menus/action_menus";

patch(KanbanController.prototype, {
    get canCreate() {
        if (this.props.resModel === "crm.lead") {
            return false;
        }
        return this.props.archInfo.activeActions.create;
    },
});

patch(ActionMenus.prototype, {
    get actionItems() {
        const items = super.actionItems || [];
        return items.filter(item => {
            const description = (item.description || item.name || "").toLowerCase();
            const key = (item.key || "").toLowerCase();
            if (
                description.includes("payment link") ||
                description.includes("generate a payment link") ||
                key.includes("payment.link") ||
                key.includes("payment_link")
            ) {
                return false;
            }
            return true;
        });
    },
});

