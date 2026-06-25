/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onMounted, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class NavButtons extends Component {
    static template = "crm_whitelabel.NavButtons";
    static props = {};

    setup() {
        this.action = useService("action");
        
        useEffect(() => {
            this._injectButtons();
            // Re-inject on route change
            const observer = new MutationObserver(() => this._injectButtons());
            observer.observe(document.body, { childList: true, subtree: true });
            return () => observer.disconnect();
        });
    }

    _injectButtons() {
        const container = document.querySelector('.o_control_panel_main_buttons');
        if (!container) return;
        if (container.querySelector('.crm-nav-btn')) return;

        const dashBtn = document.createElement('button');
        dashBtn.className = 'btn btn-secondary crm-nav-btn';
        dashBtn.textContent = 'Dashboard';
        dashBtn.onclick = () => this.action.doAction(435);

        const settBtn = document.createElement('button');
        settBtn.className = 'btn btn-secondary crm-nav-btn';
        settBtn.textContent = 'Settings';
        settBtn.onclick = () => { window.location.href = '/odoo/settings'; };

        container.appendChild(dashBtn);
        container.appendChild(settBtn);
    }
}

registry.category("systray").add("crm_nav_buttons", {
    Component: NavButtons,
    sequence: 999,
});
