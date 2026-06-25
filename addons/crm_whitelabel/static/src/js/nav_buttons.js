/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

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

registry.category("systray").add("crm_nav_buttons", {
    Component: NavButtons,
    sequence: 999,
});
