/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CrmAnalyticsDashboard extends Component {
    static template = "crm_whitelabel.AnalyticsDashboard";

    setup() {
        this.action = useService("action");
        this.company = useService("company");
        this.user = useService("user");

        this.state = useState({
            activeTab: "sales", // 'sales' | 'leads' | 'amc' | 'service'
            userName: this.user.userName || "User",
            currentCompany: this.company.currentCompany ? this.company.currentCompany.name : "",
        });

        onWillStart(async () => {
            // Placeholder for data fetching if needed later
        });
    }

    setTab(tabKey) {
        this.state.activeTab = tabKey;
    }

    goToDashboard() {
        this.action.doAction("crm_dashboard", { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("crm_analytics_dashboard", CrmAnalyticsDashboard);
