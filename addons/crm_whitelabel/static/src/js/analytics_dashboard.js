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
            userFilterDomain: [],
            selectedCompanies: [],

            // Quote Pricing & Discount Impact
            quoteDiscount: {
                totalQuotes: 0,
                totalQuoteValue: 0,
                totalDiscountAmount: 0,
                discountedQuotesCount: 0,
                tiers: {
                    full_price: { count: 0, value: 0, discount: 0, pct: 0 },
                    small_disc: { count: 0, value: 0, discount: 0, pct: 0 },
                    med_disc:   { count: 0, value: 0, discount: 0, pct: 0 },
                    heavy_disc: { count: 0, value: 0, discount: 0, pct: 0 },
                }
            },
            loadingQuoteDiscount: false,
        });

        onWillStart(async () => {
            await Promise.all([
                this.loadCustomerTypeAnalytics(),
                this.loadQuoteDiscountAnalytics(),
            ]);
        });
    }

    setTab(tabKey) {
        this.state.activeTab = tabKey;
    }

    goToDashboard() {
        this.action.doAction("crm_dashboard", { clearBreadcrumbs: true });
    }

    _getActiveCompanyIds() {
        if (user.activeCompanies && user.activeCompanies.length) {
            return user.activeCompanies.map(c => c.id);
        }
        if (user.currentCompany?.id) {
            return [user.currentCompany.id];
        }
        const curCid = session.user_companies?.current_company_id;
        if (curCid) {
            return [curCid];
        }
        const allowed = session.user_context?.allowed_company_ids;
        if (allowed && allowed.length) {
            return allowed;
        }
        // Fallback to cids in cookie
        try {
            const match = document.cookie.match(/(?:^|;\s*)cids=([^;]+)/);
            if (match) {
                const ids = decodeURIComponent(match[1]).split(',').map(Number).filter(Boolean);
                if (ids.length) return ids;
            }
        } catch (e) {}
        return [];
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

    openDiscountQuotes(tierKey, tierTitle) {
        const companyIds = this._getActiveCompanyIds();
        const companyDomain = companyIds.length ? ["|", ["company_id", "=", false], ["company_id", "in", companyIds]] : [];
        const tierData = this.state.quoteDiscount?.tiers?.[tierKey];
        let idDomain = [];
        if (tierKey === 'all_discounted') {
            const allDiscIds = [
                ...(this.state.quoteDiscount?.tiers?.small_disc?.ids || []),
                ...(this.state.quoteDiscount?.tiers?.med_disc?.ids || []),
                ...(this.state.quoteDiscount?.tiers?.heavy_disc?.ids || []),
            ];
            idDomain = [["id", "in", allDiscIds.length ? allDiscIds : [0]]];
        } else if (tierData && tierData.ids) {
            idDomain = [["id", "in", tierData.ids.length ? tierData.ids : [0]]];
        }

        const domain = [
            ["state", "!=", "cancel"],
            ...idDomain,
            ...companyDomain,
            ...this.state.userFilterDomain
        ];

        this.action.doAction({
            type: "ir.actions.act_window",
            name: (tierTitle || "Quotes") + " Deals",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            context: {
                allowed_company_ids: companyIds,
                search_default_assigned_to_me: 0,
                search_default_my_leads: 0,
            }
        });
    }

    async loadQuoteDiscountAnalytics() {
        this.state.loadingQuoteDiscount = true;
        try {
            const companyIds = this._getActiveCompanyIds();
            const { activeUserId, isAdmin } = this._getViewAsContext();

            const res = await rpc("/web/dataset/call_kw", {
                model: "crm.lead",
                method: "get_quote_discount_analytics",
                args: [activeUserId, isAdmin, companyIds],
                kwargs: {},
            });

            this.state.quoteDiscount = {
                totalQuotes: res.total_quotes || 0,
                totalQuoteValue: res.total_quote_value || 0,
                totalDiscountAmount: res.total_discount_amount || 0,
                discountedQuotesCount: res.discounted_quotes_count || 0,
                tiers: res.tiers || {
                    full_price: { count: 0, value: 0, discount: 0, pct: 0 },
                    small_disc: { count: 0, value: 0, discount: 0, pct: 0 },
                    med_disc:   { count: 0, value: 0, discount: 0, pct: 0 },
                    heavy_disc: { count: 0, value: 0, discount: 0, pct: 0 },
                }
            };
        } catch (e) {
            console.error("Failed to load quote discount analytics:", e);
        } finally {
            this.state.loadingQuoteDiscount = false;
        }
    }
}

registry.category("actions").add("crm_analytics_dashboard", CrmAnalyticsDashboard);
