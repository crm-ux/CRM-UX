/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";

export class CrmAnalyticsDashboard extends Component {
    static template = "crm_whitelabel.AnalyticsDashboard";

    setup() {
        this.action = useService("action");

        this.state = useState({
            activeTab: "leads", // default to leads to inspect the new matrix
            userName: user.name || "User",
            currentCompany: "",
            loadingLeads: false,
            // 2x2 Customer Classification Analytics Data
            matrixData: [
                {
                    key: 'existing_existing',
                    name: 'Existing Customer – Existing Product',
                    count: 0,
                    value: 0,
                    percent: 0,
                    shadeClass: 'crm-an-shade-4', // Top shade
                },
                {
                    key: 'existing_new',
                    name: 'Existing Customer – New Product',
                    count: 0,
                    value: 0,
                    percent: 0,
                    shadeClass: 'crm-an-shade-3',
                },
                {
                    key: 'new_existing',
                    name: 'New Customer – Existing Product',
                    count: 0,
                    value: 0,
                    percent: 0,
                    shadeClass: 'crm-an-shade-2',
                },
                {
                    key: 'new_new',
                    name: 'New Customer – New Product',
                    count: 0,
                    value: 0,
                    percent: 0,
                    shadeClass: 'crm-an-shade-1',
                },
            ],
            totalLeadsCount: 0,
            totalPipelineValue: 0,
        });

        onWillStart(async () => {
            await this.loadCustomerTypeAnalytics();
        });
    }

    setTab(tabKey) {
        this.state.activeTab = tabKey;
    }

    goToDashboard() {
        this.action.doAction("crm_dashboard", { clearBreadcrumbs: true });
    }

    fmt(n) {
        if (!n) return "₹0";
        if (n >= 10000000) return "₹" + (n / 10000000).toFixed(1) + "Cr";
        if (n >= 100000) return "₹" + (n / 100000).toFixed(1) + "L";
        if (n >= 1000) return "₹" + (n / 1000).toFixed(1) + "K";
        return "₹" + Math.round(n).toLocaleString('en-IN');
    }

    async loadCustomerTypeAnalytics() {
        this.state.loadingLeads = true;
        try {
            // Group by x_customer_type from crm.lead
            const res = await rpc("/web/dataset/call_kw", {
                model: "crm.lead",
                method: "read_group",
                args: [
                    [['active', '=', true], ['x_customer_type', '!=', false]],
                    ['expected_revenue:sum'],
                    ['x_customer_type'],
                ],
                kwargs: {},
            });

            let totalCount = 0;
            let totalVal = 0;
            const dataMap = {
                existing_existing: { count: 0, value: 0 },
                existing_new: { count: 0, value: 0 },
                new_existing: { count: 0, value: 0 },
                new_new: { count: 0, value: 0 },
            };

            if (res && Array.isArray(res)) {
                for (const row of res) {
                    const cType = row.x_customer_type;
                    if (dataMap[cType] !== undefined) {
                        dataMap[cType].count = row.x_customer_type_count || 0;
                        dataMap[cType].value = row.expected_revenue || 0;
                        totalCount += row.x_customer_type_count || 0;
                        totalVal += row.expected_revenue || 0;
                    }
                }
            }

            this.state.totalLeadsCount = totalCount;
            this.state.totalPipelineValue = totalVal;

            // Map and calculate percentage
            const items = [
                {
                    key: 'existing_existing',
                    name: 'Existing Customer – Existing Product',
                    count: dataMap.existing_existing.count,
                    value: dataMap.existing_existing.value,
                    percent: totalCount > 0 ? Math.round((dataMap.existing_existing.count / totalCount) * 100) : 0,
                },
                {
                    key: 'existing_new',
                    name: 'Existing Customer – New Product',
                    count: dataMap.existing_new.count,
                    value: dataMap.existing_new.value,
                    percent: totalCount > 0 ? Math.round((dataMap.existing_new.count / totalCount) * 100) : 0,
                },
                {
                    key: 'new_existing',
                    name: 'New Customer – Existing Product',
                    count: dataMap.new_existing.count,
                    value: dataMap.new_existing.value,
                    percent: totalCount > 0 ? Math.round((dataMap.new_existing.count / totalCount) * 100) : 0,
                },
                {
                    key: 'new_new',
                    name: 'New Customer – New Product',
                    count: dataMap.new_new.count,
                    value: dataMap.new_new.value,
                    percent: totalCount > 0 ? Math.round((dataMap.new_new.count / totalCount) * 100) : 0,
                },
            ];

            // Dynamically assign shade: highest count gets darkest, lowest gets lightest
            const sortedCounts = [...items].map(it => it.count).sort((a, b) => b - a);
            const shadeClasses = ['crm-an-shade-4', 'crm-an-shade-3', 'crm-an-shade-2', 'crm-an-shade-1'];

            for (const item of items) {
                const rank = sortedCounts.indexOf(item.count);
                item.shadeClass = shadeClasses[rank >= 0 && rank < 4 ? rank : 3];
            }

            this.state.matrixData = items;
        } catch (e) {
            console.error("Failed to load customer type analytics:", e);
        } finally {
            this.state.loadingLeads = false;
        }
    }
}

registry.category("actions").add("crm_analytics_dashboard", CrmAnalyticsDashboard);
