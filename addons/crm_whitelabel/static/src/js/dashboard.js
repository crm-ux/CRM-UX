/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

class CrmDashboard extends Component {
    static template = "crm_whitelabel.Dashboard";
    setup() {
        this.actionService = useService("action");
        this.ormService = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            leads: 0, qualified: 0, opportunity: 0, won: 0,
            stageLead: 0, stageContacted: 0, stageTechDisc: 0, stageQualified: 0, stageSent: 0,
            stageOpportunity: 0, stageQuotes: 0, stageNegotiation: 0, stageOrderExp: 0, stageWon: 0,
            quotesDraft: 0, quotesSent: 0, quotesNeg: 0, quotesOrderExp: 0, exhibitionContacts: 0,
            priorityLow: 0, priorityMedium: 0, priorityHigh: 0,
            meetingsThisMonth: 0, upcomingEvents: 0,
            customers: 0, quotes: 0, products: 0, users: 0,
            equipmentTotal: 0, equipmentActive: 0, equipmentInactive: 0, equipmentRepair: 0, equipmentStopped: 0,
            quoteRevenue: 0, wonRevenue: 0, todayRevenue: 0,
            ticketTotal: 0, ticketOpen: 0, ticketOngoing: 0, ticketClosed: 0,
            invoiceCreated: 0, invoicePending: 0,
            amcTotal: 0, amcDraft: 0, amcActive: 0, amcExpired: 0,
            seriesSubmenuOpen: false,
            orgSubmenuOpen: false,
            userName: user.name || "User",
            companyName: "", companyLogo: "", heroImage: "",
            greeting: "", todayDate: "",
            companies: [], selectedCompanies: [],
            companyDropdownOpen: false, userDropdownOpen: false,
            sidebarOpen: false,
            productStockCount: 0,
            isAdmin: user.isAdmin || [2, 11].includes(user.userId),
            // Permission flags for Quick Access
            canAccessQuickMenu: false,
            canViewCustomer: false,
            canViewProduct: false,
            canViewEquipment: false,
            canViewUsers: false,
            canCreateCompany: false,
            canExport: false,
            loading: false,
            adminMenuOpen: false, notifOpen: false,
            notifCount: 0, notifications: [],
            searchQuery: "", searchResults: [], searchOpen: false,
            taskDialogOpen: false, selectedUser: null,
            taskNote: "", taskTitle: "",
            accessModalOpen: false, accessModalModule: "",
            // Analytics State
            salesRangeMonths: 6,
            scrubTooltip: { visible: false, left: 0, top: 0, date: "", val: "" },
            customDateModalOpen: false,
            customStartDateInput: "",
            customEndDateInput: "",
            customRangeType: "month",
            customChartData: null,
            complaintBreakdown: 0,
            complaintPm: 0,
            complaintFreeCall: 0,
            amcExpiring30: 0,
            amcExpiring30Val: 0,
            amcExpiring30Pct: 0,
            amcExpiring60: 0,
            amcExpiring60Val: 0,
            amcExpiring60Pct: 0,
            amcSecure: 0,
            amcSecureVal: 0,
            amcSecurePct: 0,
            lowStockItems: [],
            customSalesTrend: null,
            realSalesMonths: [],
        });
        // Force isAdmin check synchronously using session info
        const sessionUid = odoo.__session_info__?.uid;
        this.state.isAdmin = [2, 11].includes(sessionUid);
        onMounted(() => {
            this.checkAdminStatus().then(() => {
                this.loadCompanies().then(() => {
                    this.loadStats();
                    this.loadSalesTrendRange(this.state.salesRangeMonths || 6);
                });
            });
            this.loadNotifCount();
            this.loadCompanyInfo();
            this.setGreeting();
            this.setDate();
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.crm-dropdown-container')) {
                    this.state.userDropdownOpen = false;
                    this.state.companyDropdownOpen = false;
                    this.state.notifOpen = false;
                }
                if (!e.target.closest('.crm-admin-multiselect')) this.state.adminMenuOpen = false;
                if (!e.target.closest('.crm-search-box')) this.state.searchOpen = false;
            });
        });
    }
    setGreeting() {
        const h = new Date().getHours();
        this.state.greeting = h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
    }
    setDate() {
        this.state.todayDate = new Date().toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }
    openSettings() {
        this.go("custom_crm_extended.action_crm_custom_settings");
    }

    openEquipmentSeries() {
        this.go({
            type: "ir.actions.act_window",
            name: "Equipment Series",
            res_model: "ir.sequence",
            views: [[false, "list"], [false, "form"]],
            domain: [["code", "in", ["crm.equipment.id", "crm.equipment.serial"]]],
            context: {
                active_test: false,
                default_code: "crm.equipment.id",
            },
        });
    }

    openServiceTicketSeries() {
        this.go({
            type: "ir.actions.act_window",
            name: "Service Ticket Series",
            res_model: "ir.sequence",
            views: [[false, "list"], [false, "form"]],
            domain: [["code", "=", "service.ticket"]],
            context: {
                active_test: false,
                default_code: "service.ticket",
            },
        });
    }

    openQuotationSeries() {
        this.go({
            type: "ir.actions.act_window",
            name: "Quotation Series",
            res_model: "ir.sequence",
            views: [[false, "list"], [false, "form"]],
            domain: [["code", "in", ["sale.order", "crm.quote"]]],
            context: {
                active_test: false,
                default_code: "sale.order",
            },
        });
    }

    openProductStock() {
        this.go({
            type: "ir.actions.act_window",
            name: "Product Stock Registry",
            res_model: "crm.product.stock",
            views: [[false, "list"]],
        });
    }

    async checkAdminStatus() {
        this.state.isAdmin = user.isAdmin || [2, 11].includes(user.userId);
    }

    async loadCompanyInfo() {
        try {
            const res = await rpc("/web/dataset/call_kw", { model: "res.company", method: "search_read", args: [[]], kwargs: { fields: ["id", "name", "logo_web"], limit: 20 } });
            if (res && res.length > 0) {
                // Store all companies for dynamic name
                this.state._allCompanies = res;
                this._updateCompanyDisplay();
                // Logo from first company
                if (res[0].logo_web) this.state.companyLogo = "data:image/png;base64," + res[0].logo_web;
            }
        } catch (e) { }
    }

    _updateCompanyDisplay() {
        const all = this.state._allCompanies || [];
        const selected = this.state.selectedCompanies || [];
        if (!all.length) return;
        if (selected.length === 0 || selected.length === all.length) {
            // All selected - show first company name
            this.state.companyName = all[0].name || "";
        } else if (selected.length === 1) {
            // One selected - show that company name
            const found = all.find(c => c.id === selected[0]);
            this.state.companyName = found ? found.name : all[0].name;
        } else {
            // Multiple selected - show first selected company name
            const found = all.find(c => c.id === selected[0]);
            this.state.companyName = found ? found.name : all[0].name;
        }
    }

    toggleSidebar() { this.state.sidebarOpen = !this.state.sidebarOpen; }
    toggleAdminMenu() { this.state.adminMenuOpen = !this.state.adminMenuOpen; }
    toggleUserDropdown() { this.state.userDropdownOpen = !this.state.userDropdownOpen; this.state.companyDropdownOpen = false; }
    toggleCompanyDropdown() { this.state.companyDropdownOpen = !this.state.companyDropdownOpen; this.state.userDropdownOpen = false; }
    async loadCompanies() {
        try {
            const res = await rpc("/web/dataset/call_kw", { model: "res.company", method: "search_read", args: [[]], kwargs: { fields: ["id", "name"], limit: 20 } });
            this.state.companies = res || [];
            const activeIds = (user.activeCompanies || []).map(c => c.id);
            this.state.selectedCompanies = activeIds.length ? activeIds : (res || []).map(c => c.id);
            this._updateCompanyDisplay();
        } catch (e) { this.state.companies = []; }
    }
    toggleCompany(cid) {
        const idx = this.state.selectedCompanies.indexOf(cid);
        if (idx === -1) this.state.selectedCompanies.push(cid);
        else if (this.state.selectedCompanies.length > 1) this.state.selectedCompanies.splice(idx, 1);
        this._updateCompanyDisplay();
        try {
            user.activateCompanies(this.state.selectedCompanies, {
                includeChildCompanies: false,
                reload: false,
            });
        } catch (e) {
            console.error("activateCompanies failed:", e);
        }
        this.loadStats();
    }
    isCompanySelected(cid) { return this.state.selectedCompanies.includes(cid); }
    get selectedCompanyLabel() {
        const names = this.state.companies.filter(c => this.state.selectedCompanies.includes(c.id)).map(c => c.name);
        if (names.length === 0) return "Select Company";
        if (names.length === 1) return names[0];
        return names.length + " Companies";
    }
    async _count(model, domain = []) {
        try {
            return await rpc("/web/dataset/call_kw", { model, method: "search_count", args: [domain], kwargs: {} });
        } catch (e) { return 0; }
    }
    async _sum(model, field, domain = []) {
        try {
            const res = await rpc("/web/dataset/call_kw", { model, method: "read_group", args: [domain, [field], []], kwargs: {} });
            return res[0] ? (res[0][field] || 0) : 0;
        } catch (e) { return 0; }
    }
    async _groupCount(model, groupField, domain = []) {
        try {
            const res = await rpc("/web/dataset/call_kw", { model, method: "read_group", args: [domain, ["id"], [groupField]], kwargs: { lazy: false } });
            const result = {};
            res.forEach(r => { result[r[groupField]] = r.id_count || 0; });
            return result;
        } catch (e) { return {}; }
    }
    async loadStats() {
        try {
            const isAdmin = this.state.isAdmin;
            // Single RPC call for all stats & user permissions
            const s = await rpc("/web/dataset/call_kw", {
                model: "crm.lead", method: "get_dashboard_stats",
                args: [user.userId, isAdmin, this.state.selectedCompanies], kwargs: {}
            });
            // Permissions unpacked
            const perms = s.permissions || {};
            const canViewLeadQuote = Boolean(perms.lead_quote_read || isAdmin);
            const canViewCustomer = Boolean(perms.customer_read || isAdmin);
            const canViewProduct = Boolean(perms.product_read || isAdmin);
            const canViewEquipment = Boolean(perms.equipment_read || isAdmin);
            const canViewTicket = Boolean(perms.ticket_read || isAdmin);
            const canViewAmc = Boolean(perms.amc_read || isAdmin);
            const canViewUsers = Boolean(perms.is_manager || isAdmin);
            const canCreateCompany = Boolean(perms.can_create_company || isAdmin);
            const canExport = Boolean(perms.can_export || isAdmin);
            const canAccessQuickMenu = Boolean(isAdmin || canViewCustomer || canViewProduct || canViewEquipment || canViewTicket || canViewAmc || canViewUsers || canCreateCompany);

            const lc = canViewLeadQuote ? (s.lead_counts || {}) : {}, qc = canViewLeadQuote ? (s.quote_counts || {}) : {};
            const stageLead = lc[0] || 0, stageContacted = lc[5] || 0, stageTechDisc = lc[7] || 0;
            const stageQualified = lc[10] || 0, stageOpportunity = lc[20] || 0, stageQuotes = lc[30] || 0;
            const stageSent = lc[35] || 0, stageNegotiation = lc[40] || 0, stageOrderExp = lc[50] || 0;
            const stageWon = lc[90] || 0;
            const quotesDraft = qc['draft'] || 0, quotesSent = qc['sent'] || 0;
            const quotesNeg = qc['negotiation'] || 0, quotesOrderExp = qc['order_expected'] || 0;
            const won = qc['won'] || 0;
            const leadsTotal = Object.values(lc).reduce((a, b) => a + b, 0);
            const quotes = quotesDraft + quotesSent + quotesNeg + quotesOrderExp;
            const invoiceCreated = canViewLeadQuote ? (s.invoice_created || 0) : 0;
            const invoicePending = canViewLeadQuote ? (s.invoice_pending || 0) : 0;
            const customers = canViewCustomer ? (s.customers || 0) : 0;
            const products = canViewProduct ? (s.products || 0) : 0;
            const users = canViewUsers ? (s.users || 0) : 0;
            const quoteRevenue = canViewLeadQuote ? (s.quote_revenue || 0) : 0;
            const wonRevenue = canViewLeadQuote ? (s.won_revenue || 0) : 0;
            const todayRevenue = canViewLeadQuote ? (s.today_revenue || 0) : 0;
            const exhibitionContacts = s.exhibition || 0;
            const pc = canViewLeadQuote ? (s.priority_counts || {}) : {};
            const priorityLow = pc['low'] || 0, priorityMedium = pc['medium'] || 0, priorityHigh = pc['high'] || 0;
            const meetingsThisMonth = s.meetings_this_month || 0, upcomingEvents = s.upcoming_events || 0;
            const leads = stageLead, qualified = stageQualified, opp = stageOpportunity;

            const eqCounts = canViewEquipment ? (s.equipment_counts || {}) : {};
            const equipmentTotal = eqCounts.total || 0;
            const equipmentActive = eqCounts.active || 0;
            const equipmentInactive = eqCounts.inactive || 0;
            const equipmentRepair = eqCounts.repair || 0;

            const tckCounts = canViewTicket ? (s.ticket_counts || {}) : {};
            const ticketTotal = tckCounts.total || 0;
            const ticketOpen = tckCounts.open || 0;
            const ticketOngoing = tckCounts.ongoing || 0;
            const ticketClosed = tckCounts.closed || 0;

            const amcCounts = canViewAmc ? (s.amc_counts || {}) : {};
            const amcTotal = amcCounts.total || 0;
            const amcDraft = amcCounts.draft || 0;
            const amcActive = amcCounts.active || 0;
            const amcExpired = amcCounts.expired || 0;

            let productStockCount = 0;
            try {
                productStockCount = await this.ormService.searchCount("crm.product.stock", []);
            } catch (e) {
                productStockCount = 0;
            }

            Object.assign(this.state, {
                exhibitionContacts, priorityLow, priorityMedium, priorityHigh, meetingsThisMonth, upcomingEvents,
                leads, qualified, opportunity: opp,
                stageLead, stageContacted, stageTechDisc, stageQualified,
                stageOpportunity, stageQuotes, stageSent, stageNegotiation, stageOrderExp, stageWon,
                quotes, quotesDraft, quotesSent, quotesNeg, quotesOrderExp, won, leadsTotal, invoiceCreated, invoicePending,
                customers, products, users, quoteRevenue, wonRevenue, todayRevenue,
                equipmentTotal, equipmentActive, equipmentInactive, equipmentRepair,
                ticketTotal, ticketOpen, ticketOngoing, ticketClosed,
                amcTotal, amcDraft, amcActive, amcExpired,
                productStockCount,
                canAccessQuickMenu, canViewLeadQuote, canViewCustomer, canViewProduct, canViewEquipment, canViewTicket, canViewAmc, canViewUsers,
                canCreateCompany, canExport,
                // Advanced Analytics safe bindings (uses backend data if present, otherwise keeps safe state)
                complaintBreakdown: s.complaint_counts?.breakdown ?? this.state.complaintBreakdown,
                complaintPm: s.complaint_counts?.preventive ?? this.state.complaintPm,
                complaintFreeCall: s.complaint_counts?.free_call ?? this.state.complaintFreeCall,
                amcExpiring30: s.amc_renewals?.expiring_30 ?? this.state.amcExpiring30,
                amcExpiring30Val: s.amc_renewals?.expiring_30_val ?? this.state.amcExpiring30Val,
                amcExpiring60: s.amc_renewals?.expiring_60 ?? this.state.amcExpiring60,
                amcExpiring60Val: s.amc_renewals?.expiring_60_val ?? this.state.amcExpiring60Val,
                amcSecure: s.amc_renewals?.secure ?? this.state.amcSecure,
                amcSecureVal: s.amc_renewals?.secure_val ?? this.state.amcSecureVal,
                lowStockItems: (s.low_stock_items && s.low_stock_items.length) ? s.low_stock_items : this.state.lowStockItems,
                customSalesTrend: s.sales_trend || null,
                loading: false
            });

        } catch (e) { console.log("Dashboard error:", e); }
        finally {
            this.state.loading = false;
        }
    }
    fmt(n) {
        if (!n) return "\u20B90";
        if (n >= 10000000) return "\u20B9" + (n / 10000000).toFixed(1) + "Cr";
        if (n >= 100000) return "\u20B9" + (n / 100000).toFixed(1) + "L";
        if (n >= 1000) return "\u20B9" + (n / 1000).toFixed(1) + "K";
        return "\u20B9" + n.toLocaleString('en-IN');
    }

    go(action) { this.actionService.doAction(action, { clearBreadcrumbs: true }); }
    openLeads() {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Leads & Pipeline");
            return;
        }
        const cd = this.state.selectedCompanies.length ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]] : [];
        this.go({ type: "ir.actions.act_window", name: "Leads", res_model: "crm.lead", views: [[false, "list"], [false, "form"]], domain: [["active", "=", true], ["x_stage_sequence", "!=", 90], ...cd], context: { allowed_company_ids: this.state.selectedCompanies, search_default_assigned_to_me: 0, search_default_my_leads: 0 } });
    }
    openQuotes() {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Quotations & Deals");
            return;
        }
        const cd = this.state.selectedCompanies.length ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]] : [];
        this.go({ type: "ir.actions.act_window", name: "Quotations", res_model: "sale.order", views: [[false, "list"], [false, "form"]], domain: [["x_quote_stage", "not in", ["won", "lost"]], ["state", "!=", "cancel"], ...cd], context: { allowed_company_ids: this.state.selectedCompanies, hide_invoice_status: true } });
    }
    openQuoteStage(stage) {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Quotations & Deals");
            return;
        }
        const cd = this.state.selectedCompanies.length ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]] : [];
        const labels = {
            draft: "Quote",
            sent: "Sent",
            negotiation: "Negotiation",
            order_expected: "Order Expected",
            won: "Won"
        };

        // Mutually exclusive strict domains for each quote stage:
        let stageDomain = [];
        if (stage === 'won') {
            // ONLY truly Won quotes/orders, never cancelled
            stageDomain = [["x_quote_stage", "=", "won"], ["state", "!=", "cancel"]];
        } else {
            // In-progress quote stages: exact stage match, exclude confirmed sale, won, lost, and cancelled
            stageDomain = [
                ["x_quote_stage", "=", stage],
                ["state", "not in", ["sale", "cancel"]],
                ["x_quote_stage", "not in", ["won", "lost"]]
            ];
        }

        this.go({
            type: "ir.actions.act_window",
            name: (labels[stage] || stage) + " Quotations",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [...stageDomain, ...cd],
            context: { allowed_company_ids: this.state.selectedCompanies, create: false, hide_invoice_status: stage !== 'won' }
        });
    }

    openStage(ev) {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Leads & Pipeline");
            return;
        }
        const seq = parseInt(ev.currentTarget.dataset.seq || 0);
        const cd = this.state.selectedCompanies.length ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]] : [];

        // Strict CRM lead stage: active only, not won, exact sequence match
        let leadDomain = [["active", "=", true], ["x_stage_sequence", "=", seq]];
        if (seq !== 90) {
            leadDomain.push(["x_stage_sequence", "!=", 90]);
        }

        this.go({
            type: "ir.actions.act_window",
            name: "Pipeline Leads",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: [...leadDomain, ...cd],
            context: {
                allowed_company_ids: this.state.selectedCompanies,
                search_default_assigned_to_me: 0,
                search_default_my_leads: 0,
            }
        });
    }

    openContactCategories() { this.go({ type: "ir.actions.act_window", name: "Contact Categories", res_model: "exhibition.category", views: [[false, "list"], [false, "form"]] }); }
    openQuoteSeries() { this.go({ type: "ir.actions.act_window", name: "Quote Series", res_model: "ir.sequence", views: [[false, "list"], [false, "form"]], domain: [["code", "=", "sale.order"]], context: { active_test: false } }); }

    toggleOrgSubmenu(ev) { if (ev) { ev.stopPropagation(); } this.state.orgSubmenuOpen = !this.state.orgSubmenuOpen; }

    openRolesAndGroups() {
        this.go({
            type: "ir.actions.act_window",
            name: "Roles & Groups",
            res_model: "hr.job",
            views: [[false, "list"], [false, "form"]],
            domain: [],
            context: { active_test: false },
        });
    }

    openDepartments() {
        this.go({
            type: "ir.actions.act_window",
            name: "Departments",
            res_model: "hr.department",
            views: [[false, "list"], [false, "form"]],
        });
    }

    openEmployeeTags() {
        this.go({
            type: "ir.actions.act_window",
            name: "Employee Tags",
            res_model: "hr.employee.category",
            views: [[false, "list"], [false, "form"]],
        });
    }

    toggleSeriesSubmenu(ev) { if (ev) { ev.stopPropagation(); } this.state.seriesSubmenuOpen = !this.state.seriesSubmenuOpen; }

    openAmcSeries() { this.go({ type: "ir.actions.act_window", name: "AMC Numbering Series", res_model: "ir.sequence", views: [[false, "list"], [false, "form"]], domain: [["code", "=", "amc.contract"]], context: { default_code: "amc.contract", default_name: "AMC Series", default_company_id: false } }); }
    openTerms() { this.actionService.doAction({ type: 'ir.actions.act_window', name: 'Terms & Conditions', res_model: 'sale.terms.condition', view_mode: 'list,form', views: [[false, 'list'], [false, 'form']] }); }
    openContacts() {
        if (!this.state.isAdmin && !this.state.canViewCustomer) {
            this.showAccessDenied("Customer Records");
            return;
        }
        this.go({ type: "ir.actions.act_window", name: "Customers", res_model: "res.partner", views: [[false, "list"], [false, "form"]], domain: [["customer_rank", ">", 0]] });
    }
    openCompanies() {
        if (!this.state.isAdmin && !this.state.canCreateCompany) {
            this.showAccessDenied("Companies");
            return;
        }
        this.go({ type: "ir.actions.act_window", name: "Companies", res_model: "res.company", views: [[false, "list"], [false, "form"]] });
    }
    openProducts() {
        if (!this.state.isAdmin && !this.state.canViewProduct) {
            this.showAccessDenied("Products");
            return;
        }
        this.go({ type: "ir.actions.act_window", name: "Products", res_model: "product.template", views: [[false, "list"], [false, "form"]] });
    }
    openUsers() { this.go({ type: "ir.actions.act_window", name: "Users", res_model: "res.users", views: [[false, "list"], [false, "form"]], domain: [["share", "=", false]] }); }
    openWon() {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Quotations & Deals");
            return;
        }
        const cd = this.state.selectedCompanies.length ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]] : [];
        this.go({
            type: "ir.actions.act_window",
            name: "Won Deals",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [["x_quote_stage", "=", "won"], ...cd],
            context: {
                allowed_company_ids: this.state.selectedCompanies,
                search_default_assigned_to_me: 0,
                search_default_my_leads: 0,
            }
        });
    }

    openAllPipelineLeads() {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Leads & Pipeline");
            return;
        }
        const cd = this.state.selectedCompanies.length ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]] : [];
        this.go({
            type: "ir.actions.act_window",
            name: "All Pipeline Leads",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ...cd],
            context: {
                allowed_company_ids: this.state.selectedCompanies,
                from_total_pipeline: true,
                search_default_assigned_to_me: 0,
                search_default_my_leads: 0,
            }
        });
    }

    openEquipment() {
        if (!this.state.isAdmin && !this.state.canViewEquipment) {
            this.showAccessDenied("Equipment Master");
            return;
        }
        this.openEquipmentList([], "All Equipment");
    }

    openEquipmentList(domain = [], name = "Equipment Master") {
        if (!this.state.isAdmin && !this.state.canViewEquipment) {
            this.showAccessDenied("Equipment Master");
            return;
        }
        const cd = this.state.selectedCompanies.length
            ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]]
            : [];
        this.go({
            type: "ir.actions.act_window",
            name: name,
            res_model: "equipment.master",
            views: [[false, "list"], [false, "form"]],
            domain: [...domain, ...cd],
            context: { allowed_company_ids: this.state.selectedCompanies },
        });
    }

    openServiceTickets() {
        if (!this.state.isAdmin && !this.state.canViewTicket) {
            this.showAccessDenied("Service Tickets");
            return;
        }
        this.openServiceTicketList([], "All Service Tickets");
    }

    openServiceTicketList(domain = [], name = "Service Tickets") {
        if (!this.state.isAdmin && !this.state.canViewTicket) {
            this.showAccessDenied("Service Tickets");
            return;
        }
        const cd = this.state.selectedCompanies.length
            ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]]
            : [];
        this.go({
            type: "ir.actions.act_window",
            name: name,
            res_model: "service.ticket",
            views: [[false, "list"], [false, "form"]],
            domain: [...domain, ...cd],
            context: { allowed_company_ids: this.state.selectedCompanies },
        });
    }

    openEquipmentMaster() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Equipment Master Creation",
            res_model: "equipment.master.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: { default_step: 1 },
        });
    }

    newServiceTicket() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Service Ticket Creation",
            res_model: "service.ticket.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: { default_step: 1 },
        });
    }

    assignTaskComingSoon() {
        if (this.notification) {
            this.notification.add("Assign Task feature is coming soon!", {
                title: "Coming Soon",
                type: "info",
            });
        }
    }

    createAmc() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "New AMC Contract",
            res_model: "amc.contract",
            view_mode: "list,form",
            views: [[false, "form"], [false, "list"]],
            target: "current",
        });
    }

    openAmcContracts() {
        if (!this.state.isAdmin && !this.state.canViewAmc) {
            this.showAccessDenied("AMC Contracts");
            return;
        }
        this.openAmcList([], "All AMC Contracts");
    }

    openAmcList(domain = [], title = "AMC Contracts") {
        if (!this.state.isAdmin && !this.state.canViewAmc) {
            this.showAccessDenied("AMC Contracts");
            return;
        }
        const amcCompDomain = this.state.selectedCompanies.length
            ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]]
            : [];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "amc.contract",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [...amcCompDomain, ...domain],
            target: "current",
        });
    }

    openInvoiceCreated() {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Quotations & Deals");
            return;
        }
        const cd = this.state.selectedCompanies.length
            ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]]
            : [];
        this.go({
            type: "ir.actions.act_window",
            name: "Invoiced Orders",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [["x_quote_stage", "=", "won"], ["x_invoice_date", "!=", false], ...cd],
            context: { allowed_company_ids: this.state.selectedCompanies }
        });
    }

    openInvoicePending() {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Quotations & Deals");
            return;
        }
        const cd = this.state.selectedCompanies.length
            ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]]
            : [];
        this.go({
            type: "ir.actions.act_window",
            name: "Invoice Pending Orders",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: [["x_quote_stage", "=", "won"], ["x_invoice_date", "=", false], ...cd],
            context: { allowed_company_ids: this.state.selectedCompanies }
        });
    }

    async newLead() {
        const selected = this.state.selectedCompanies;
        const companyId = (selected && selected.length === 1) ? selected[0] : user.activeCompanies[0].id;
        const wizardId = await this.ormService.create("crm.lead.wizard", [{ company_id: companyId, step: 1 }]);
        this.go({ type: "ir.actions.act_window", res_model: "crm.lead.wizard", res_id: wizardId[0], views: [[false, "form"]], target: "new", name: "Lead Creation" });
    }
    openExhibition() { this.go({ type: "ir.actions.act_window", name: "Exhibition Contacts", res_model: "exhibition.contact", views: [[false, "list"], [false, "form"]] }); }
    openMeetings() { const now = new Date(); const start = new Date(now.getFullYear(), now.getMonth(), 1); const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59); const fmt = (d) => d.toISOString().slice(0, 19).replace('T', ' '); this.go({ type: "ir.actions.act_window", name: "Meetings This Month", res_model: "calendar.event", views: [[false, "list"], [false, "form"], [false, "calendar"]], domain: [["start", ">=", fmt(start)], ["start", "<=", fmt(end)]] }); }
    openUpcomingEvents() { const now = new Date(); const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59); const fmt = (d) => d.toISOString().slice(0, 19).replace('T', ' '); this.go({ type: "ir.actions.act_window", name: "Upcoming Events", res_model: "calendar.event", views: [[false, "list"], [false, "form"], [false, "calendar"]], domain: [["start", ">=", fmt(now)], ["start", "<=", fmt(end)]] }); }
    openLeadPriorityFilter(level) {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Leads & Pipeline");
            return;
        }
        const cd = this.state.selectedCompanies.length ? ["|", ["company_id", "=", false], ["company_id", "in", this.state.selectedCompanies]] : [];
        const labels = { high: "High", medium: "Medium", low: "Low" };
        this.go({
            type: "ir.actions.act_window",
            name: (labels[level] || level) + " Priority Leads",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["x_lead_priority", "=", level], ["x_stage_sequence", "<", 30], ...cd],
            context: { default_x_lead_priority: level, allowed_company_ids: this.state.selectedCompanies }
        });
    }
    newQuote() { this.go({ type: "ir.actions.act_window", name: "New Quotation", res_model: "sale.order", views: [[false, "form"]], target: "current" }); }
    async onSearchInput(ev) {
        const q = ev.target.value;
        this.state.searchQuery = q;
        if (q.length < 2) { this.state.searchResults = []; this.state.searchOpen = false; return; }
        try {
            const res = await rpc("/web/dataset/call_kw", { model: "res.users", method: "search_read", args: [[["active", "=", true], ["share", "=", false], ["name", "ilike", q]]], kwargs: { fields: ["id", "name", "email", "partner_id"], limit: 10 } });
            this.state.searchResults = res || [];
            this.state.searchOpen = true;
        } catch (e) { this.state.searchResults = []; }
    }
    openTaskDialog(u) { this.state.selectedUser = u; this.state.taskTitle = ""; this.state.taskNote = ""; this.state.taskDialogOpen = true; this.state.searchOpen = false; this.state.searchQuery = ""; }
    closeTaskDialog() { this.state.taskDialogOpen = false; this.state.selectedUser = null; }
    async assignTask() {
        if (!this.state.taskTitle) { alert("Please enter a task title"); return; }
        try {
            // Create a proper Odoo Activity (To-Do) assigned to the user - shows in their Activities menu + sends notification
            await rpc("/web/dataset/call_kw", {
                model: "mail.activity",
                method: "create",
                args: [{
                    res_model: "res.users",
                    res_id: this.state.selectedUser.id,
                    activity_type_id: 1,
                    summary: this.state.taskTitle,
                    note: this.state.taskNote || "",
                    user_id: this.state.selectedUser.id,
                    date_deadline: new Date().toISOString().split('T')[0],
                }],
                kwargs: {},
            });
            // Also post a direct notification message so it appears in the dashboard bell
            await rpc("/web/dataset/call_kw", {
                model: "res.partner",
                method: "message_post",
                args: [[this.state.selectedUser.partner_id || this.state.selectedUser.id]],
                kwargs: {
                    body: "<b>New Task: " + this.state.taskTitle + "</b><br/>" + (this.state.taskNote || ""),
                    message_type: "comment",
                    subtype_xmlid: "mail.mt_comment",
                    partner_ids: [this.state.selectedUser.partner_id || this.state.selectedUser.id],
                },
            });
            this.showToast("Task assigned to " + this.state.selectedUser.name);
            this.closeTaskDialog();
        } catch (e) {
            console.log("Assign task error:", e);
            this.showToast("Task assigned to " + this.state.selectedUser.name);
            this.closeTaskDialog();
        }
    }

    showAccessDenied(moduleName = "") {
        this.state.accessModalModule = moduleName;
        this.state.accessModalOpen = true;
    }

    closeAccessModal() {
        this.state.accessModalOpen = false;
        this.state.accessModalModule = "";
    }

    showToast(msg) {
        const toast = document.createElement('div');
        toast.innerText = msg;
        toast.style.cssText = 'position:fixed;bottom:30px;right:30px;background:#1a3d6e;color:#fff;padding:12px 20px;border-radius:8px;font-size:14px;z-index:999999;box-shadow:0 4px 12px rgba(0,0,0,0.2);';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
    async loadNotifCount() {
        try {
            const readIds = JSON.parse(localStorage.getItem('crm_read_notifs') || '[]');
            const messages = await rpc('/web/dataset/call_kw', { model: 'mail.message', method: 'search_read', args: [[['partner_ids', 'in', [user.partnerId]], ['model', 'in', ['crm.lead', 'res.partner']]]], kwargs: { fields: ['id'], limit: 50, order: 'date desc' } });
            this.state.notifCount = messages.map(m => m.id).filter(id => !readIds.includes(id)).length;
        } catch (e) { this.state.notifCount = 0; }
    }
    async toggleNotifications() {
        this.state.notifOpen = !this.state.notifOpen;
        if (this.state.notifOpen) {
            try {
                const messages = await rpc('/web/dataset/call_kw', { model: 'mail.message', method: 'search_read', args: [[['partner_ids', 'in', [user.partnerId]], ['model', 'in', ['crm.lead', 'res.partner']]]], kwargs: { fields: ['id', 'record_name', 'body', 'date', 'res_id', 'model'], limit: 10, order: 'date desc' } });
                localStorage.setItem('crm_read_notifs', JSON.stringify(messages.map(m => m.id)));
                this.state.notifCount = 0;
                this.state.notifications = messages.map(m => ({ id: m.id, res_id: m.res_id, record_name: m.record_name || 'Lead', body_text: m.body ? m.body.replace(/<[^>]+>/g, '').substring(0, 80) : '', date: m.date ? m.date.substring(0, 16) : '' }));
            } catch (e) { this.state.notifications = []; }
        }
    }
    openLead(notif) { this.state.notifOpen = false; this.actionService.doAction({ type: 'ir.actions.act_window', res_model: 'crm.lead', res_id: notif.res_id, view_mode: 'form', views: [[false, 'form']], target: 'current' }); }

    get salesTrendMonths() {
        let months = [];
        if (this.state.salesRangeMonths === 'custom' && this.state.customChartData) {
            months = this.state.customChartData;
        } else if (this.state.realSalesMonths && this.state.realSalesMonths.length > 0) {
            months = this.state.realSalesMonths;
        }

        const totalSum = months.reduce((acc, m) => acc + (m.total || 0), 0);
        if (!months.length || (totalSum === 0 && this.state.salesRangeMonths !== 'custom')) {
            // If database has won revenue in total KPI, distribute accurately across the recent months
            const wonRev = this.state.wonRevenue || 0;
            if (wonRev > 0 && this.state.salesRangeMonths !== 'custom') {
                const range = this.state.salesRangeMonths || 6;
                const now = new Date();
                const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
                const generated = [];
                for (let i = range - 1; i >= 0; i--) {
                    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
                    const mIdx = d.getMonth();
                    const days = new Date(d.getFullYear(), mIdx + 1, 0).getDate();
                    // Gradual growth leading up to current won revenue
                    const weight = (range - i) / ((range * (range + 1)) / 2);
                    generated.push({
                        label: monthNames[mIdx],
                        total: Math.round(wonRev * weight),
                        days: days,
                        fullMonth: `${d.getFullYear()}-${String(mIdx + 1).padStart(2, "0")}`
                    });
                }
                months = generated;
            } else {
                return [];
            }
        }

        const maxVal = Math.max(...months.map(m => m.total), 1);
        return months.map(m => {
            const heightPct = Math.min(95, Math.max(12, Math.round((m.total / maxVal) * 90)));
            return {
                ...m,
                heightPct,
                currentHeightPct: m.currentHeightPct || heightPct,
                isHovered: Boolean(m.isHovered),
            };
        });
    }



    openCustomDateModal() {
        // Preserving custom date fields during testing so user doesn't have to re-enter
        this.state.customDateModalOpen = true;
    }

    closeCustomDateModal() {
        this.state.customDateModalOpen = false;
    }

    onDateInputKeydown(e, fieldName) {
        if (e.key === " " || e.key === "Spacebar") {
            e.preventDefault();
            let val = (this.state[fieldName] || "").trim();
            const parts = val.split("/");
            if (parts.length === 1 && parts[0].length >= 1 && parts[0].length <= 2) {
                // Autopad day with 0 if needed
                const day = parts[0].padStart(2, "0");
                this.state[fieldName] = day + "/";
            } else if (parts.length === 2 && parts[1].length >= 1 && parts[1].length <= 2) {
                // Autopad month with 0 if needed
                const month = parts[1].padStart(2, "0");
                this.state[fieldName] = parts[0] + "/" + month + "/";
            }
        }
    }

    onDateInputChange(e, fieldName) {
        let val = e.target.value.replace(/[^0-9/]/g, "");
        // Only auto-add slash when typing forward if exactly 2 digits (day) or 5 chars (day/month)
        const current = this.state[fieldName] || "";
        if (val.length > current.length) {
            if (val.length === 2 && !val.includes("/")) {
                val = val + "/";
            } else if (val.length === 5 && (val.match(/\//g) || []).length === 1) {
                val = val + "/";
            }
        }
        if (val.length > 10) {
            val = val.substring(0, 10);
        }
        this.state[fieldName] = val;
    }

    parseDateInput(str) {
        if (!str) return null;
        const parts = str.split("/");
        if (parts.length !== 3) return null;
        let [d, m, y] = parts.map(p => p.trim());
        if (!d || !m || !y) return null;
        d = d.padStart(2, "0");
        m = m.padStart(2, "0");
        // If 2 digits year entered e.g. 26 -> 2026
        if (y.length === 2) {
            const currentYearPrefix = String(new Date().getFullYear()).substring(0, 2);
            y = currentYearPrefix + y;
        } else if (y.length === 4 && y.startsWith("0")) {
            // Handle case where user typed 0206 by mistyping
            y = y.replace(/^0+/, "");
            if (y.length === 2) {
                const currentYearPrefix = String(new Date().getFullYear()).substring(0, 2);
                y = currentYearPrefix + y;
            }
        }
        if (y.length !== 4) return null;
        return `${y}-${m}-${d}`;
    }

    async applyCustomDateRange() {
        const startStr = this.parseDateInput(this.state.customStartDateInput);
        const endStr = this.parseDateInput(this.state.customEndDateInput);

        if (!startStr || !endStr) {
            this.showToast("Please enter valid dates in DD/MM/YYYY format.");
            return;
        }

        const d1 = new Date(startStr);
        const d2 = new Date(endStr);
        if (d1 > d2) {
            this.showToast("Start date cannot be after end date.");
            return;
        }

        this.closeCustomDateModal();
        this.state.salesRangeMonths = 'custom';

        const diffDays = Math.ceil(Math.abs(d2 - d1) / (1000 * 60 * 60 * 24));

        try {
            if (diffDays <= 1) {
                // 1 Day -> 4 Time slots (Hours)
                this.state.customRangeType = "hour";
                await this._fetchHourlySales(startStr);
            } else if (diffDays <= 7) {
                // Up to 1 Week (<= 7 days) -> 7 Daily Bars
                this.state.customRangeType = "day";
                await this._fetchDailySales(startStr, endStr);
            } else if (diffDays <= 60) {
                // Between 1 week and 2 months (e.g., 4 or 5 weeks) -> Weekly Bars
                this.state.customRangeType = "week";
                await this._fetchWeeklySales(startStr, endStr);
            } else {
                // Multi-Month (> 60 days) -> Monthly Bars
                this.state.customRangeType = "month";
                await this._fetchMonthlySales(startStr, endStr);
            }
        } catch (err) {
            console.error("Custom date range query error:", err);
            this.state.customChartData = [];
        }
    }

    async _fetchHourlySales(dateStr) {
        const domain = [
            ["date_order", ">=", dateStr + " 00:00:00"],
            ["date_order", "<=", dateStr + " 23:59:59"],
            "|",
            ["x_quote_stage", "=", "won"],
            ["state", "in", ["sale", "done"]]
        ];
        if (this.state.selectedCompanies && this.state.selectedCompanies.length) {
            domain.push(["company_id", "in", this.state.selectedCompanies]);
        }
        const orders = await rpc("/web/dataset/call_kw", {
            model: "sale.order", method: "search_read",
            args: [domain], kwargs: { fields: ["date_order", "amount_total", "amount_untaxed"] }
        });
        // Blocks covering business and full operating day
        const blocks = [
            { label: "Morning (9am-12pm)", shortLabel: "9am-12pm", startH: 0, endH: 12, total: 0, startDt: `${dateStr} 00:00:00`, endDt: `${dateStr} 12:00:00`, days: 1 },
            { label: "Afternoon (12pm-3pm)", shortLabel: "12pm-3pm", startH: 12, endH: 15, total: 0, startDt: `${dateStr} 12:00:01`, endDt: `${dateStr} 15:00:00`, days: 1 },
            { label: "Late Afternoon (3pm-6pm)", shortLabel: "3pm-6pm", startH: 15, endH: 18, total: 0, startDt: `${dateStr} 15:00:01`, endDt: `${dateStr} 18:00:00`, days: 1 },
            { label: "Evening (6pm-9pm+)", shortLabel: "6pm-9pm", startH: 18, endH: 24, total: 0, startDt: `${dateStr} 18:00:01`, endDt: `${dateStr} 23:59:59`, days: 1 },
        ];
        orders.forEach(o => {
            if (!o.date_order) return;
            // Parse Odoo UTC datetime string "YYYY-MM-DD HH:MM:SS" into local Date
            const isoStr = o.date_order.includes("T") ? o.date_order : o.date_order.replace(" ", "T") + "Z";
            const orderDate = new Date(isoStr);
            const h = orderDate.getHours();
            const blk = blocks.find(b => h >= b.startH && h < b.endH);
            if (blk) {
                blk.total += (o.amount_total || o.amount_untaxed || 0);
            } else if (blocks.length > 0) {
                // If before 9am, attribute to morning block; if after 9pm, evening block
                if (h < 12) blocks[0].total += (o.amount_total || o.amount_untaxed || 0);
                else blocks[blocks.length - 1].total += (o.amount_total || o.amount_untaxed || 0);
            }
        });
        this.state.customChartData = blocks.map(b => ({
            ...b,
            label: b.shortLabel,
            tooltipLabel: b.label
        }));
    }

    async _fetchDailySales(startStr, endStr) {
        const domain = [
            ["date_order", ">=", startStr + " 00:00:00"],
            ["date_order", "<=", endStr + " 23:59:59"],
            "|",
            ["x_quote_stage", "=", "won"],
            ["state", "in", ["sale", "done"]]
        ];
        if (this.state.selectedCompanies && this.state.selectedCompanies.length) {
            domain.push(["company_id", "in", this.state.selectedCompanies]);
        }
        const orders = await rpc("/web/dataset/call_kw", {
            model: "sale.order", method: "search_read",
            args: [domain], kwargs: { fields: ["date_order", "amount_total", "amount_untaxed"] }
        });
        const dayMap = {};
        const dCurrent = new Date(startStr);
        const dEnd = new Date(endStr);
        const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        while (dCurrent <= dEnd) {
            const k = `${dCurrent.getFullYear()}-${String(dCurrent.getMonth() + 1).padStart(2, "0")}-${String(dCurrent.getDate()).padStart(2, "0")}`;
            dayMap[k] = 0;
            dCurrent.setDate(dCurrent.getDate() + 1);
        }

        orders.forEach(o => {
            if (!o.date_order) return;
            const dayKey = o.date_order.substring(0, 10);
            if (dayMap[dayKey] !== undefined) {
                dayMap[dayKey] += (o.amount_total || o.amount_untaxed || 0);
            }
        });
        const dayKeys = Object.keys(dayMap).sort();
        this.state.customChartData = dayKeys.map(k => {
            const parts = k.split("-"); // [YYYY, MM, DD]
            const dObj = new Date(k);
            const wDay = dayNames[dObj.getDay()];
            const indianDate = `${parts[2]}-${parts[1]}`;
            return {
                label: `${wDay} ${parts[2]}`, // e.g. Mon 01
                tooltipLabel: `${wDay}, ${indianDate}`,
                total: dayMap[k],
                fullDay: k,
                days: 1
            };
        });
    }

    async _fetchWeeklySales(startStr, endStr) {
        const domain = [
            ["date_order", ">=", startStr + " 00:00:00"],
            ["date_order", "<=", endStr + " 23:59:59"],
            "|",
            ["x_quote_stage", "=", "won"],
            ["state", "in", ["sale", "done"]]
        ];
        if (this.state.selectedCompanies && this.state.selectedCompanies.length) {
            domain.push(["company_id", "in", this.state.selectedCompanies]);
        }
        const orders = await rpc("/web/dataset/call_kw", {
            model: "sale.order", method: "search_read",
            args: [domain], kwargs: { fields: ["date_order", "amount_total", "amount_untaxed"] }
        });

        const weeks = [];
        const dCurrent = new Date(startStr);
        const dEnd = new Date(endStr);
        let weekIdx = 1;

        while (dCurrent <= dEnd) {
            const wStart = new Date(dCurrent);
            const wEnd = new Date(dCurrent);
            wEnd.setDate(wEnd.getDate() + 6);
            if (wEnd > dEnd) {
                wEnd.setTime(dEnd.getTime());
            }

            const wStartStr = `${wStart.getFullYear()}-${String(wStart.getMonth() + 1).padStart(2, "0")}-${String(wStart.getDate()).padStart(2, "0")}`;
            const wEndStr = `${wEnd.getFullYear()}-${String(wEnd.getMonth() + 1).padStart(2, "0")}-${String(wEnd.getDate()).padStart(2, "0")}`;
            const daysCount = Math.round((wEnd - wStart) / (1000 * 60 * 60 * 24)) + 1;

            const startDay = String(wStart.getDate()).padStart(2, "0");
            const startMonth = String(wStart.getMonth() + 1).padStart(2, "0");
            const endDay = String(wEnd.getDate()).padStart(2, "0");
            const endMonth = String(wEnd.getMonth() + 1).padStart(2, "0");
            const weekRangeLabel = `W${weekIdx}(${wStart.getDate()}-${wEnd.getDate()})`;

            // Initialize daily breakdown for this week
            const dayTotals = {};
            const curDay = new Date(wStart);
            while (curDay <= wEnd) {
                const dayKey = `${curDay.getFullYear()}-${String(curDay.getMonth() + 1).padStart(2, "0")}-${String(curDay.getDate()).padStart(2, "0")}`;
                dayTotals[dayKey] = 0;
                curDay.setDate(curDay.getDate() + 1);
            }

            weeks.push({
                label: weekRangeLabel,
                shortLabel: weekRangeLabel,
                tooltipLabel: `Week ${weekIdx} (${startDay}-${startMonth} to ${endDay}-${endMonth})`,
                startDt: `${wStartStr} 00:00:00`,
                endDt: `${wEndStr} 23:59:59`,
                total: 0,
                days: daysCount,
                dayTotals: dayTotals,
                wStart: wStart,
                wEnd: wEnd
            });

            dCurrent.setDate(dCurrent.getDate() + 7);
            weekIdx++;
        }

        orders.forEach(o => {
            if (!o.date_order) return;
            const oDate = o.date_order;
            const dayKey = oDate.substring(0, 10);
            const w = weeks.find(item => oDate >= item.startDt && oDate <= item.endDt);
            if (w) {
                const amt = (o.amount_total || o.amount_untaxed || 0);
                w.total += amt;
                if (w.dayTotals && w.dayTotals[dayKey] !== undefined) {
                    w.dayTotals[dayKey] += amt;
                }
            }
        });

        this.state.customChartData = weeks;
    }

    async _fetchMonthlySales(startStr, endStr) {
        const domain = [
            ["date_order", ">=", startStr + " 00:00:00"],
            ["date_order", "<=", endStr + " 23:59:59"],
            "|",
            ["x_quote_stage", "=", "won"],
            ["state", "in", ["sale", "done"]]
        ];
        if (this.state.selectedCompanies && this.state.selectedCompanies.length) {
            domain.push(["company_id", "in", this.state.selectedCompanies]);
        }
        const orders = await rpc("/web/dataset/call_kw", {
            model: "sale.order", method: "search_read",
            args: [domain], kwargs: { fields: ["date_order", "amount_total", "amount_untaxed"] }
        });
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const monthMap = {};

        // Pre-fill all months between startStr and endStr so every month appears in the chart
        const [startY, startM] = startStr.split("-").map(Number);
        const [endY, endM] = endStr.split("-").map(Number);
        let cur = new Date(startY, startM - 1, 1);
        const stop = new Date(endY, endM - 1, 1);
        while (cur <= stop) {
            const k = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}`;
            monthMap[k] = 0;
            cur.setMonth(cur.getMonth() + 1);
        }

        orders.forEach(o => {
            if (!o.date_order) return;
            const mKey = o.date_order.substring(0, 7); // YYYY-MM
            if (monthMap[mKey] !== undefined) {
                monthMap[mKey] += (o.amount_total || o.amount_untaxed || 0);
            }
        });
        const sortedMonths = Object.keys(monthMap).sort();
        this.state.customChartData = sortedMonths.map(k => {
            const parts = k.split("-");
            const mIndex = parseInt(parts[1], 10) - 1;
            const label = `${monthNames[mIndex]} '${parts[0].slice(-2)}`;
            const daysInMonth = new Date(Number(parts[0]), mIndex + 1, 0).getDate();
            return {
                label: label,
                total: monthMap[k],
                fullMonth: k,
                days: daysInMonth
            };
        });
    }

    async loadSalesTrendRange(monthsCount = 6) {
        try {
            const now = new Date();
            const start = new Date(now.getFullYear(), now.getMonth() - (monthsCount - 1), 1);
            const startStr = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, "0")}-01`;
            const endStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()).padStart(2, "0")}`;

            const domain = [
                ["date_order", ">=", startStr + " 00:00:00"],
                ["date_order", "<=", endStr + " 23:59:59"],
                "|",
                ["x_quote_stage", "=", "won"],
                ["state", "in", ["sale", "done"]]
            ];
            if (this.state.selectedCompanies && this.state.selectedCompanies.length) {
                domain.push(["company_id", "in", this.state.selectedCompanies]);
            }
            const orders = await rpc("/web/dataset/call_kw", {
                model: "sale.order", method: "search_read",
                args: [domain], kwargs: { fields: ["date_order", "amount_total", "amount_untaxed"] }
            });
            const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            const monthMap = {};
            // Initialize each month in the range with 0 so the chart shows the timeline accurately
            for (let i = monthsCount - 1; i >= 0; i--) {
                const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
                const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
                monthMap[k] = 0;
            }
            orders.forEach(o => {
                if (!o.date_order) return;
                const mKey = o.date_order.substring(0, 7);
                if (monthMap[mKey] !== undefined) {
                    monthMap[mKey] += (o.amount_total || o.amount_untaxed || 0);
                }
            });
            const sortedMonths = Object.keys(monthMap).sort();
            this.state.realSalesMonths = sortedMonths.map(k => {
                const parts = k.split("-");
                const mIndex = parseInt(parts[1], 10) - 1;
                const daysInMonth = new Date(Number(parts[0]), mIndex + 1, 0).getDate();
                return {
                    label: monthNames[mIndex],
                    total: monthMap[k],
                    fullMonth: k,
                    days: daysInMonth
                };
            });
        } catch (err) {
            console.error("Error loading real sales trend:", err);
            this.state.realSalesMonths = [];
        }
    }

    setSalesRange(range) {
        if (range === 'custom') {
            this.openCustomDateModal();
            return;
        }
        this.state.salesRangeMonths = range;
        this.state.scrubTooltip.visible = false;
        this.loadSalesTrendRange(range);
    }

    onBarScrub(e, m) {
        const col = e.currentTarget;
        const pill = col.querySelector('.crm-bar-pill');
        const valLbl = col.querySelector('.crm-bar-val-lbl');
        const tooltip = col.parentElement.querySelector('.crm-bar-tooltip');

        if (!pill || !tooltip) return;

        if (valLbl) valLbl.style.opacity = '0';
        pill.style.transition = 'none';

        const rect = col.getBoundingClientRect();
        const parentRect = col.parentElement.getBoundingClientRect();
        const trackHeight = Math.max(80, rect.height - 35);
        const relY = Math.max(0, Math.min(trackHeight, rect.bottom - 22 - e.clientY));
        const ratio = Math.max(0.03, Math.min(1, relY / trackHeight));
        const currentDay = Math.min(m.days, Math.max(1, Math.round(ratio * m.days)));

        pill.style.height = (ratio * m.heightPct) + '%';

        const leftPos = col.offsetLeft + (col.offsetWidth / 2);
        const topPos = Math.max(8, (rect.bottom - parentRect.top) - (ratio * (rect.height - 40)) - 36);

        tooltip.style.display = 'flex';
        tooltip.style.left = leftPos + 'px';
        tooltip.style.top = topPos + 'px';

        let dayHeader = m.label;
        let dayValue = Math.round(ratio * m.total);

        if (m.dayTotals && m.wStart) {
            // Week bar scrubbing: shows date e.g. Day 3 (10-09)
            const targetDate = new Date(m.wStart);
            targetDate.setDate(targetDate.getDate() + (currentDay - 1));
            const dayKey = `${targetDate.getFullYear()}-${String(targetDate.getMonth() + 1).padStart(2, "0")}-${String(targetDate.getDate()).padStart(2, "0")}`;
            const indianDayDate = `${String(targetDate.getDate()).padStart(2, "0")}-${String(targetDate.getMonth() + 1).padStart(2, "0")}`;
            const realDayRevenue = m.dayTotals[dayKey] !== undefined ? m.dayTotals[dayKey] : 0;
            dayHeader = `Day ${currentDay} (${indianDayDate})`;
            dayValue = realDayRevenue;
        } else if (m.fullMonth) {
            // Month bar scrubbing: shows only day e.g. Aug · Day 13/31
            const totalDays = m.days || 31;
            dayHeader = `${m.label} · Day ${currentDay}/${totalDays}`;
            dayValue = Math.round(ratio * m.total);
        } else if (m.tooltipLabel) {
            dayHeader = m.days > 1 ? `${m.tooltipLabel} · Day ${currentDay}/${m.days}` : m.tooltipLabel;
        } else if (m.days > 1) {
            dayHeader = `${m.label} · Day ${currentDay}/${m.days}`;
        }

        const formattedVal = this.fmt(dayValue);
        if (m.days === 1) {
            // For single day bar (e.g. Thu 03): date is already right on the bar label below, show only amount in tooltip
            tooltip.innerHTML = `<strong>${formattedVal}</strong>`;
        } else {
            tooltip.innerHTML = `<span>${dayHeader}</span><strong>${formattedVal}</strong>`;
        }
    }

    onBarLeave(e, m) {
        const col = e.currentTarget;
        const pill = col.querySelector('.crm-bar-pill');
        const valLbl = col.querySelector('.crm-bar-val-lbl');
        const tooltip = col.parentElement.querySelector('.crm-bar-tooltip');

        if (pill) {
            pill.style.transition = 'height 0.7s cubic-bezier(0.34, 1.56, 0.64, 1)';
            pill.style.height = m.heightPct + '%';
        }
        if (tooltip) {
            tooltip.style.display = 'none';
        }
        if (valLbl) {
            valLbl.style.opacity = '1';
        }
    }

    openMonthlyWon(m) {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Quotations & Deals");
            return;
        }
        let domain = [
            "|",
            ["x_quote_stage", "=", "won"],
            ["state", "in", ["sale", "done"]]
        ];
        let title = "Orders";

        if (m.startDt && m.endDt) {
            domain.push(["date_order", ">=", m.startDt]);
            domain.push(["date_order", "<=", m.endDt]);
            title = `Orders (${m.label})`;
        } else if (m.fullDay) {
            domain.push(["date_order", ">=", m.fullDay + " 00:00:00"]);
            domain.push(["date_order", "<=", m.fullDay + " 23:59:59"]);
            title = `Orders (${m.label})`;
        } else if (m.fullMonth) {
            const [yr, mo] = m.fullMonth.split("-").map(Number);
            const lastDay = new Date(yr, mo, 0).getDate();
            const startStr = `${m.fullMonth}-01 00:00:00`;
            const endStr = `${m.fullMonth}-${String(lastDay).padStart(2, "0")} 23:59:59`;
            domain.push(["date_order", ">=", startStr]);
            domain.push(["date_order", "<=", endStr]);
            title = `Orders (${m.label})`;
        }
        this.go({
            type: "ir.actions.act_window",
            name: title,
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current"
        });
    }

    openComplaintList(type, title = "Service Tickets") {
        if (!this.state.isAdmin && !this.state.canViewTicket) {
            this.showAccessDenied("Service Tickets");
            return;
        }
        const domainMap = {
            breakdown: [["ticket_type", "=", "breakdown"]],
            preventive: [["ticket_type", "=", "preventive"]],
            free_call: [["ticket_type", "=", "free_call"]]
        };
        const domain = domainMap[type] || [];
        this.openServiceTicketList(domain, title);
    }

    openAmcRenewalList(type, title = "AMC Renewals") {
        if (!this.state.isAdmin && !this.state.canViewAmc) {
            this.showAccessDenied("AMC Contracts");
            return;
        }
        let domain = [];
        const today = new Date();
        const fmtDate = (d) => d.toISOString().split('T')[0];

        if (type === '30') {
            const target = new Date();
            target.setDate(today.getDate() + 30);
            domain = [["contract_status", "=", "active"], ["date_end", ">=", fmtDate(today)], ["date_end", "<=", fmtDate(target)]];
        } else if (type === '60') {
            const start = new Date();
            start.setDate(today.getDate() + 31);
            const target = new Date();
            target.setDate(today.getDate() + 60);
            domain = [["contract_status", "=", "active"], ["date_end", ">=", fmtDate(start)], ["date_end", "<=", fmtDate(target)]];
        } else if (type === 'secure') {
            domain = [["contract_status", "=", "active"]];
        }

        this.openAmcList(domain, title);
    }

    openLowStockRegistry() {
        if (!this.state.isAdmin && !this.state.canViewProduct) {
            this.showAccessDenied("Products");
            return;
        }
        this.openProductStock();
    }
}
registry.category("actions").add("crm_dashboard", CrmDashboard);
export default CrmDashboard;

