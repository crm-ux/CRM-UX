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
    get printItems() {
        return [];
    },

    async getActionItems() {
        const items = await super.getActionItems ? await super.getActionItems(...arguments) : [];
        if (!Array.isArray(items)) {
            return items;
        }
        return items.filter(item => {
            const desc = (item.description || item.name || "").toLowerCase();
            return !desc.includes("payment link");
        });
    },

    async getPrintItems() {
        return [];
    },
});


