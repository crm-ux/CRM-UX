/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class NavButtons extends Component {
    static template = "crm_whitelabel.NavButtons";
    static props = {};
    
    goDashboard() {
        window.location.href = '/odoo/action-435';
    }
    
    goSettings() {
        window.location.href = '/odoo/settings';
    }
}

registry.category("systray").add("crm_nav_buttons", {
    Component: NavButtons,
    sequence: 1,
});
