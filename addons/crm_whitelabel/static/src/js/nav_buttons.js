/** @odoo-module **/
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

class NavButtons extends Component {
    static template = "crm_whitelabel.NavButtons";
    static props = {};

    setup() {
        this.action = useService("action");
    }

    goDashboard() {
        this.action.doAction(435);
    }

    goSettings() {
        window.location.href = '/odoo/settings';
    }
}

// Only show on non-dashboard pages
const currentPath = window.location.pathname;
if (!currentPath.endsWith('/action-435') || currentPath.includes('/action-435/')) {
    registry.category("systray").add("crm_nav_buttons", {
        Component: NavButtons,
        sequence: 1,
    });
}
