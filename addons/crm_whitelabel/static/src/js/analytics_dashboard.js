/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { session } from "@web/session";
import { rpc } from "@web/core/network/rpc";

export class CrmAnalyticsDashboard extends Component {
    static template = "crm_whitelabel.AnalyticsDashboard";

    setup() {
        this.action = useService("action");

        this.state = useState({
            activeTab: "leads",
            userName: user.name || "User",
            currentCompany: "",
            loadingLeads: false,
            // 4 Quadrants matching exact pipeline colors, NO random icons
            matrixData: [
                {
                    key: 'existing_existing',
                    name: 'Existing Customer – Existing Product',
                    count: 0,
                    wonValue: 0,
                    percent: 0,
                    colorClass: 'crm-quad-sky', // Pipeline #38bdf8
                },
                {
                    key: 'existing_new',
                    name: 'Existing Customer – New Product',
                    count: 0,
                    wonValue: 0,
                    percent: 0,
                    colorClass: 'crm-quad-indigo', // Pipeline #818cf8
                },
                {
                    key: 'new_existing',
                    name: 'New Customer – Existing Product',
                    count: 0,
                    wonValue: 0,
                    percent: 0,
                    colorClass: 'crm-quad-emerald', // Pipeline #22c55e
                },
                {
                    key: 'new_new',
                    name: 'New Customer – New Product',
                    count: 0,
                    wonValue: 0,
                    percent: 0,
                    colorClass: 'crm-quad-orange', // Pipeline #fb923c
                },
            ],
            totalPipelineLeads: 0,
            classifiedLeadsCount: 0,
            unclassifiedCount: 0,
            totalWonValue: 0,
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

    _getCompanyFilter() {
        const cId = session.user_companies?.current_company_id || session.user_context?.allowed_company_ids?.[0];
        if (cId) {
            return ['|', ['company_id', '=', false], ['company_id', '=', cId]];
        }
        return [];
    }

    openUnclassifiedLeads() {
        if (!this.state.unclassifiedCount) return;
        const companyDomain = this._getCompanyFilter();
        const domain = [["active", "=", true], ["x_customer_type", "=", false], ...companyDomain];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Unclassified Leads",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
        });
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
            const companyFilter = this._getCompanyFilter();

            // 1. Fetch leads filtered by Active Company & User's standard access rights
            const leadDomain = [['active', '=', true], ...companyFilter];
            const allLeads = await rpc("/web/dataset/call_kw", {
                model: "crm.lead",
                method: "search_read",
                args: [leadDomain],
                kwargs: { fields: ['id', 'x_customer_type'], limit: 1000 },
            });

            const totalPipelineLeads = allLeads.length;
            let unclassifiedCount = 0;
            const dataMap = {
                existing_existing: { count: 0, wonValue: 0 },
                existing_new: { count: 0, wonValue: 0 },
                new_existing: { count: 0, wonValue: 0 },
                new_new: { count: 0, wonValue: 0 },
            };

            const leadCustomerTypeMap = {};
            for (const lead of allLeads) {
                const cType = lead.x_customer_type;
                if (!cType) {
                    unclassifiedCount++;
                } else if (dataMap[cType] !== undefined) {
                    dataMap[cType].count++;
                    leadCustomerTypeMap[lead.id] = cType;
                }
            }

            const classifiedLeadsCount = totalPipelineLeads - unclassifiedCount;

            // 2. Fetch WON orders filtered by Active Company
            const orderDomain = [
                ['x_quote_stage', '=', 'won'],
                ['amount_total', '>', 0],
                ['state', '!=', 'cancel'],
                ...companyFilter
            ];

            const wonOrders = await rpc("/web/dataset/call_kw", {
                model: "sale.order",
                method: "search_read",
                args: [orderDomain],
                kwargs: { fields: ['id', 'amount_total', 'opportunity_id'], limit: 500 },
            });

            let totalWonValue = 0;
            for (const order of wonOrders) {
                const leadId = order.opportunity_id ? order.opportunity_id[0] : false;
                const amt = order.amount_total || 0;
                totalWonValue += amt;

                if (leadId && leadCustomerTypeMap[leadId]) {
                    const cType = leadCustomerTypeMap[leadId];
                    if (dataMap[cType]) {
                        dataMap[cType].wonValue += amt;
                    }
                }
            }

            this.state.totalPipelineLeads = totalPipelineLeads;
            this.state.classifiedLeadsCount = classifiedLeadsCount;
            this.state.unclassifiedCount = unclassifiedCount;
            this.state.totalWonValue = totalWonValue;

            // 3. Map into 4 quadrants
            this.state.matrixData = [
                {
                    key: 'existing_existing',
                    name: 'Existing Customer – Existing Product',
                    count: dataMap.existing_existing.count,
                    wonValue: dataMap.existing_existing.wonValue,
                    percent: classifiedLeadsCount > 0 ? Math.round((dataMap.existing_existing.count / classifiedLeadsCount) * 100) : 0,
                    colorClass: 'crm-quad-sky',
                },
                {
                    key: 'existing_new',
                    name: 'Existing Customer – New Product',
                    count: dataMap.existing_new.count,
                    wonValue: dataMap.existing_new.wonValue,
                    percent: classifiedLeadsCount > 0 ? Math.round((dataMap.existing_new.count / classifiedLeadsCount) * 100) : 0,
                    colorClass: 'crm-quad-indigo',
                },
                {
                    key: 'new_existing',
                    name: 'New Customer – Existing Product',
                    count: dataMap.new_existing.count,
                    wonValue: dataMap.new_existing.wonValue,
                    percent: classifiedLeadsCount > 0 ? Math.round((dataMap.new_existing.count / classifiedLeadsCount) * 100) : 0,
                    colorClass: 'crm-quad-emerald',
                },
                {
                    key: 'new_new',
                    name: 'New Customer – New Product',
                    count: dataMap.new_new.count,
                    wonValue: dataMap.new_new.wonValue,
                    percent: classifiedLeadsCount > 0 ? Math.round((dataMap.new_new.count / classifiedLeadsCount) * 100) : 0,
                    colorClass: 'crm-quad-orange',
                },
            ];
        } catch (e) {
            console.error("Failed to load customer type analytics:", e);
        } finally {
            this.state.loadingLeads = false;
        }
    }
}

registry.category("actions").add("crm_analytics_dashboard", CrmAnalyticsDashboard);
