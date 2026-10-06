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
        this.companyService = useService("company");

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
            userFilterDomain: [],
            selectedCompanies: [],
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

    _getActiveCompanyIds() {
        if (this.companyService?.activeCompanyIds?.length) {
            return this.companyService.activeCompanyIds;
        }
        if (this.companyService?.currentCompany?.id) {
            return [this.companyService.currentCompany.id];
        }
        if (user.activeCompanies?.length) {
            return user.activeCompanies.map(c => c.id);
        }
        const cId = session.user_companies?.current_company_id || session.user_context?.allowed_company_ids?.[0];
        return cId ? [cId] : [];
    }

    _getViewAsContext() {
        let viewAsUid = null;
        try {
            const savedUid = sessionStorage.getItem("crm_view_as_uid");
            if (savedUid) {
                viewAsUid = parseInt(savedUid, 10);
            }
        } catch (e) {}

        const activeUserId = viewAsUid || user.userId;
        const isAdmin = !viewAsUid && Boolean(user.isAdmin);
        return { activeUserId, isAdmin, viewAsUid };
    }

    openUnclassifiedLeads() {
        if (!this.state.unclassifiedCount) return;
        const companyIds = this._getActiveCompanyIds();
        const companyDomain = companyIds.length ? ["|", ["company_id", "=", false], ["company_id", "in", companyIds]] : [];
        const domain = [["active", "=", true], ["x_customer_type", "=", false], ...companyDomain, ...this.state.userFilterDomain];
        
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Unclassified Leads",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            context: {
                allowed_company_ids: companyIds,
                search_default_assigned_to_me: 0,
                search_default_my_leads: 0,
            }
        });
    }

    openQuadrantLeads(quadrantKey, quadrantName) {
        const companyIds = this._getActiveCompanyIds();
        const companyDomain = companyIds.length ? ["|", ["company_id", "=", false], ["company_id", "in", companyIds]] : [];
        const domain = [["active", "=", true], ["x_customer_type", "=", quadrantKey], ...companyDomain, ...this.state.userFilterDomain];
        
        this.action.doAction({
            type: "ir.actions.act_window",
            name: quadrantName + " Leads",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            context: {
                allowed_company_ids: companyIds,
                search_default_assigned_to_me: 0,
                search_default_my_leads: 0,
            }
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
            const companyIds = this._getActiveCompanyIds();
            const { activeUserId, isAdmin } = this._getViewAsContext();
            this.state.selectedCompanies = companyIds;

            // Fetch statistics from backend with company, user permissions and View As
            const res = await rpc("/web/dataset/call_kw", {
                model: "crm.lead",
                method: "get_customer_classification_stats",
                args: [activeUserId, isAdmin, companyIds],
                kwargs: {},
            });

            const totalPipelineLeads = res.total_pipeline || 0;
            const classifiedLeadsCount = res.classified_count || 0;
            const unclassifiedCount = res.unclassified_count || 0;
            const totalWonValue = res.total_won_val || 0;
            const counts = res.counts || {};
            const wonVals = res.won_values || {};

            // Store user filter domain for list view clicks (e.g. rep views)
            if (res.user_filter_applied && res.allowed_uids && res.allowed_uids.length) {
                this.state.userFilterDomain = [["user_id", "in", res.allowed_uids]];
            } else {
                this.state.userFilterDomain = [];
            }

            this.state.totalPipelineLeads = totalPipelineLeads;
            this.state.classifiedLeadsCount = classifiedLeadsCount;
            this.state.unclassifiedCount = unclassifiedCount;
            this.state.totalWonValue = totalWonValue;

            // Update 4 quadrants
            this.state.matrixData = [
                {
                    key: 'existing_existing',
                    name: 'Existing Customer – Existing Product',
                    count: counts.existing_existing || 0,
                    wonValue: wonVals.existing_existing || 0,
                    percent: classifiedLeadsCount > 0 ? Math.round(((counts.existing_existing || 0) / classifiedLeadsCount) * 100) : 0,
                    colorClass: 'crm-quad-sky',
                },
                {
                    key: 'existing_new',
                    name: 'Existing Customer – New Product',
                    count: counts.existing_new || 0,
                    wonValue: wonVals.existing_new || 0,
                    percent: classifiedLeadsCount > 0 ? Math.round(((counts.existing_new || 0) / classifiedLeadsCount) * 100) : 0,
                    colorClass: 'crm-quad-indigo',
                },
                {
                    key: 'new_existing',
                    name: 'New Customer – Existing Product',
                    count: counts.new_existing || 0,
                    wonValue: wonVals.new_existing || 0,
                    percent: classifiedLeadsCount > 0 ? Math.round(((counts.new_existing || 0) / classifiedLeadsCount) * 100) : 0,
                    colorClass: 'crm-quad-emerald',
                },
                {
                    key: 'new_new',
                    name: 'New Customer – New Product',
                    count: counts.new_new || 0,
                    wonValue: wonVals.new_new || 0,
                    percent: classifiedLeadsCount > 0 ? Math.round(((counts.new_new || 0) / classifiedLeadsCount) * 100) : 0,
                    colorClass: 'crm-quad-orange',
                },
            ];
        } catch (e) {
            console.error("Failed to load customer classification analytics:", e);
        } finally {
            this.state.loadingLeads = false;
        }
    }
}

registry.category("actions").add("crm_analytics_dashboard", CrmAnalyticsDashboard);
