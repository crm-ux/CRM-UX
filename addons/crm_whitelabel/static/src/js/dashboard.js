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
        this.dialogService = useService("dialog");

        this.state = useState({
            leads: 0, qualified: 0, opportunity: 0, won: 0,
            stageLead: 0, stageContacted: 0, stageTechDisc: 0, stageQualified: 0, stageSent: 0,
            stageOpportunity: 0, stageQuotes: 0, stageNegotiation: 0, stageOrderExp: 0, stageWon: 0,
            leadsTotal: 0,
            quotesDraft: 0, quotesSent: 0, quotesNeg: 0, quotesOrderExp: 0, exhibitionContacts: 0,
            priorityLow: 0, priorityMedium: 0, priorityHigh: 0,
            priorityLowVal: 0, priorityMediumVal: 0, priorityHighVal: 0,
            meetingsThisMonth: 0, upcomingEvents: 0,
            customers: 0, quotes: 0, products: 0, users: 0,
            equipmentTotal: 0, equipmentActive: 0, equipmentInactive: 0, equipmentRepair: 0, equipmentStopped: 0,
            quoteRevenue: 0, wonRevenue: 0, todayRevenue: 0,
            ticketTotal: 0, ticketOpen: 0, ticketOngoing: 0, ticketClosed: 0,
            invoiceCreated: 0, invoicePending: 0,
            stageLeadVal: 0, stageContactedVal: 0, stageTechDiscVal: 0, stageQualifiedVal: 0, stageOpportunityVal: 0,
            stageQuotesVal: 0, stageSentVal: 0, stageNegotiationVal: 0, stageOrderExpVal: 0, stageWonVal: 0,
            pipelineTotalVal: 0,
            invoiceCreatedVal: 0, invoicePendingVal: 0,
            amcTotalVal: 0, amcDraftVal: 0, amcActiveVal: 0, amcExpiredVal: 0,
            equipmentTotalVal: 0, equipmentActiveVal: 0, equipmentInactiveVal: 0, equipmentRepairVal: 0,
            ticketTotalVal: 0, ticketOpenVal: 0, ticketOngoingVal: 0, ticketClosedVal: 0,
            stockTotalVal: 0,
            seriesSubmenuOpen: false,
            orgSubmenuOpen: false,
            userName: user.name || "User",
            companyName: "", companyLogo: "", heroImage: "",
            greeting: "", todayDate: "",
            companies: [], selectedCompanies: [],
            companyDropdownOpen: false, userDropdownOpen: false,
            sidebarOpen: false,
            productStockCount: 0,
            isAdmin: Boolean(user.isAdmin),
            canAssignTask: false,
            // Permission flags for Quick Access
            canAccessQuickMenu: false,
            canViewCustomer: false,
            canViewProduct: false,
            canViewExhibition: false,
            canViewEquipment: false,
            canViewUsers: false,
            canCreateCompany: false,
            canExport: false,
            canLog: false,
            loading: false,
            viewAsUserId: null,
            viewAsUserName: "",
            viewAsModalOpen: false,
            internalUsers: [],
            selectedViewAsId: null,
            viewAsDropdownOpen: false,
            adminMenuOpen: false, notifOpen: false,
            notifCount: 0, notifications: [],
            searchQuery: "", searchResults: [], searchOpen: false, mobileSearchOpen: false,
            taskDialogOpen: false, selectedUser: null,
            taskNote: "", taskTitle: "",
            taskMemberSearch: "",
            assignableUsers: [],
            taskAttachmentName: "",
            taskAttachmentData: null,
            taskDeadline: "",
            taskLoadingUsers: false,
            taskSubmitting: false,
            taskDetailModalOpen: false,
            selectedTaskDetail: null,
            accessModalOpen: false, accessModalModule: "",
            // My Profile Modal State
            profileModalOpen: false,
            profileActiveTab: "preferences",
            profileLoading: false,
            profileSaving: false,
            profileData: {
                id: null,
                name: user.name || "",
                login: user.login || "",
                email: "",
                phone: "",
                mobile: "",
                image_128: null,
                tz: "Asia/Calcutta",
                lang: "en_US",
                notification_type: "email",
                job_title: "",
                department: "",
                manager: "",
                expense_manager: "",
                timezones: [],
                langs: [],
            },
            // Change Password Modal State
            passwordModalOpen: false,
            oldPassword: "",
            newPassword: "",
            confirmPassword: "",
            passwordError: "",
            passwordLoading: false,
            showOldPassword: false,
            showNewPassword: false,
            showConfirmPassword: false,
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
            amcExpired: 0,
            amcExpiredVal: 0,
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
            outOfStockCount: 0,
            lowStockCount: 0,
            totalRegisteredStock: 0,
            customSalesTrend: null,
            realSalesMonths: [],
        });

        // Check admin status reliably using user service
        const isAdm = Boolean(user.isAdmin);
        this.state.isAdmin = isAdm;

        // Restore View As user from sessionStorage only (resets when website/tab is closed)
        try {
            localStorage.removeItem("crm_view_as_uid");
            localStorage.removeItem("crm_view_as_uname");
            const savedUid = sessionStorage.getItem("crm_view_as_uid");
            const savedName = sessionStorage.getItem("crm_view_as_uname");
            if (savedUid && isAdm) {
                this.state.viewAsUserId = parseInt(savedUid, 10);
                this.state.viewAsUserName = savedName || "";
                this.state.selectedViewAsId = parseInt(savedUid, 10);
                this.state.isAdmin = false;
            }
        } catch (e) { }

        // Expose helper on window for testing: window.testAssignWork()
        window.testAssignWork = () => this.openAssignTaskWizard();

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
        if (!this.state.isAdmin && !this.state.canViewProduct) {
            this.showAccessDenied("Products");
            return;
        }
        this.go({
            type: "ir.actions.act_window",
            name: "Product Stock Registry",
            res_model: "crm.product.stock",
            views: [[false, "list"]],
        });
    }

    openTaskManagement() {
        // Can create if Admin or Manager (has canAssignTask privilege)
        const canCreate = Boolean(this.state.isAdmin || this.state.canAssignTask);
        this.go({
            type: "ir.actions.act_window",
            name: "Task Management",
            res_model: "crm.task.management",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            context: {
                create: canCreate,
            },
        });
    }

    async checkAdminStatus() {
        const uid = this.state.viewAsUserId || user.userId;
        if (this.state.viewAsUserId) {
            this.state.isAdmin = false;
        } else {
            this.state.isAdmin = Boolean(user.isAdmin);
        }

        try {
            const canAssign = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "check_can_assign_task",
                args: [],
                kwargs: { user_id: uid },
            });
            this.state.canAssignTask = Boolean(canAssign);
        } catch (e) {
            this.state.canAssignTask = Boolean(this.state.isAdmin);
        }
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
            const activeUserId = this.state.viewAsUserId || user.userId;
            const activeIsAdmin = this.state.viewAsUserId ? false : (this.state.isAdmin || user.isAdmin);
            this.state.isAdmin = activeIsAdmin;

            // Single RPC call for all stats & user permissions
            const s = await rpc("/web/dataset/call_kw", {
                model: "crm.lead", method: "get_dashboard_stats",
                args: [activeUserId, activeIsAdmin, this.state.selectedCompanies], kwargs: {}
            });
            // Permissions unpacked
            const perms = s.permissions || {};
            const isAdm = activeIsAdmin;
            const canViewLeadQuote = Boolean(perms.lead_quote_read || isAdm);
            const canViewCustomer = Boolean(perms.customer_read || isAdm);
            const canViewProduct = Boolean(perms.product_read || isAdm);
            const canViewExhibition = Boolean(perms.exhibition_read || isAdm);
            const canViewEquipment = Boolean(perms.equipment_read || isAdm);
            const canViewTicket = Boolean(perms.ticket_read || isAdm);
            const canViewAmc = Boolean(perms.amc_read || isAdm);
            const canViewUsers = Boolean(perms.is_manager || isAdm);
            const canCreateCompany = Boolean(perms.can_create_company || isAdm);
            const canExport = Boolean(perms.can_export || isAdm);
            const canAccessQuickMenu = Boolean(isAdm || canViewCustomer || canViewProduct || canViewExhibition || canViewEquipment || canViewTicket || canViewAmc || canViewUsers || canCreateCompany);

            const lc = canViewLeadQuote ? (s.lead_counts || {}) : {}, qc = canViewLeadQuote ? (s.quote_counts || {}) : {};
            const stageLead = lc[0] || 0, stageContacted = lc[5] || 0, stageTechDisc = lc[7] || 0;
            const stageQualified = lc[10] || 0, stageOpportunity = lc[20] || 0;
            const quotesDraft = qc['draft'] || 0, quotesSent = qc['sent'] || 0;
            const quotesNeg = qc['negotiation'] || 0, quotesOrderExp = qc['order_expected'] || 0;
            const won = qc['won'] || 0;
            const quoteRevenue = canViewLeadQuote ? (s.quote_revenue || 0) : 0;
            const wonRevenue = canViewLeadQuote ? (s.won_revenue || 0) : 0;
            const todayRevenue = canViewLeadQuote ? (s.today_revenue || 0) : 0;
            const stageQuotes = lc[30] || 0;
            const stageSent = lc[35] || 0;
            const stageNegotiation = lc[40] || 0;
            const stageOrderExp = lc[50] || 0;
            const stageWon = lc[90] || 0;
            const quotes = quotesDraft + quotesSent + quotesNeg + quotesOrderExp;
            const leadsTotal = stageLead + stageContacted + stageTechDisc + stageQualified + stageOpportunity + stageQuotes + stageSent + stageNegotiation + stageOrderExp + stageWon;

            const lv = canViewLeadQuote ? (s.lead_values || {}) : {}, qv = canViewLeadQuote ? (s.quote_values || {}) : {};
            const stageLeadVal = lv[0] || 0, stageContactedVal = lv[5] || 0, stageTechDiscVal = lv[7] || 0;
            const stageQualifiedVal = lv[10] || 0, stageOpportunityVal = lv[20] || 0;
            const stageQuotesVal = qv['draft'] || lv[30] || 0;
            const stageSentVal = qv['sent'] || lv[35] || 0;
            const stageNegotiationVal = qv['negotiation'] || lv[40] || 0;
            const stageOrderExpVal = qv['order_expected'] || lv[50] || 0;
            const stageWonVal = qv['won'] || lv[90] || wonRevenue || 0;
            const pipelineTotalVal = stageLeadVal + stageContactedVal + stageTechDiscVal + stageQualifiedVal + stageOpportunityVal + stageQuotesVal + stageSentVal + stageNegotiationVal + stageOrderExpVal + stageWonVal;

            const invoiceCreated = canViewLeadQuote ? (s.invoice_created || 0) : 0;
            const invoiceCreatedVal = canViewLeadQuote ? (s.invoice_created_val || 0) : 0;
            const invoicePending = canViewLeadQuote ? (s.invoice_pending || 0) : 0;
            const invoicePendingVal = canViewLeadQuote ? (s.invoice_pending_val || 0) : 0;
            const customers = canViewCustomer ? (s.customers || 0) : 0;
            const products = canViewProduct ? (s.products || 0) : 0;
            const users = canViewUsers ? (s.users || 0) : 0;
            const exhibitionContacts = s.exhibition || 0;
            const pc = canViewLeadQuote ? (s.priority_counts || {}) : {};
            const pv = canViewLeadQuote ? (s.priority_values || {}) : {};
            const priorityLow = pc['low'] || 0, priorityMedium = pc['medium'] || 0, priorityHigh = pc['high'] || 0;
            const priorityLowVal = pv['low'] || 0, priorityMediumVal = pv['medium'] || 0, priorityHighVal = pv['high'] || 0;
            const meetingsThisMonth = s.meetings_this_month || 0, upcomingEvents = s.upcoming_events || 0;
            const leads = stageLead, qualified = stageQualified, opp = stageOpportunity;

            const eqCounts = canViewEquipment ? (s.equipment_counts || {}) : {};
            const eqVals = canViewEquipment ? (s.equipment_values || {}) : {};
            const equipmentTotal = eqCounts.total || 0;
            const equipmentActive = eqCounts.active || 0;
            const equipmentInactive = eqCounts.inactive || 0;
            const equipmentRepair = eqCounts.repair || 0;
            const equipmentTotalVal = eqVals.total || 0;
            const equipmentActiveVal = eqVals.active || 0;
            const equipmentInactiveVal = eqVals.inactive || 0;
            const equipmentRepairVal = eqVals.repair || 0;

            const tckCounts = canViewTicket ? (s.ticket_counts || {}) : {};
            const tckVals = canViewTicket ? (s.ticket_values || {}) : {};
            const ticketTotal = tckCounts.total || 0;
            const ticketOpen = tckCounts.open || 0;
            const ticketOngoing = tckCounts.ongoing || 0;
            const ticketClosed = tckCounts.closed || 0;
            const ticketTotalVal = tckVals.total || 0;
            const ticketOpenVal = tckVals.open || 0;
            const ticketOngoingVal = tckVals.ongoing || 0;
            const ticketClosedVal = tckVals.closed || 0;

            const amcCounts = canViewAmc ? (s.amc_counts || {}) : {};
            const amcVals = canViewAmc ? (s.amc_values || {}) : {};
            const amcTotal = amcCounts.total || 0;
            const amcDraft = amcCounts.draft || 0;
            const amcActive = amcCounts.active || 0;
            const amcExpired = amcCounts.expired || 0;
            const amcTotalVal = amcVals.total || 0;
            const amcDraftVal = amcVals.draft || 0;
            const amcActiveVal = amcVals.active || 0;
            const amcExpiredVal = amcVals.expired || 0;

            let productStockCount = 0;
            try {
                productStockCount = await this.ormService.searchCount("crm.product.stock", []);
            } catch (e) {
                productStockCount = 0;
            }
            const stockTotalVal = s.stock_total_val || 0;

            Object.assign(this.state, {
                exhibitionContacts, priorityLow, priorityMedium, priorityHigh,
                priorityLowVal, priorityMediumVal, priorityHighVal, meetingsThisMonth, upcomingEvents,
                leads, qualified, opportunity: opp,
                stageLead, stageContacted, stageTechDisc, stageQualified,
                stageOpportunity, stageQuotes, stageSent, stageNegotiation, stageOrderExp, stageWon,
                stageLeadVal, stageContactedVal, stageTechDiscVal, stageQualifiedVal,
                stageOpportunityVal, stageQuotesVal, stageSentVal, stageNegotiationVal, stageOrderExpVal, stageWonVal,
                pipelineTotalVal,
                quotes, quotesDraft, quotesSent, quotesNeg, quotesOrderExp, won, leadsTotal,
                invoiceCreated, invoiceCreatedVal, invoicePending, invoicePendingVal,
                customers, products, users, quoteRevenue, wonRevenue, todayRevenue,
                equipmentTotal, equipmentActive, equipmentInactive, equipmentRepair,
                equipmentTotalVal, equipmentActiveVal, equipmentInactiveVal, equipmentRepairVal,
                ticketTotal, ticketOpen, ticketOngoing, ticketClosed,
                ticketTotalVal, ticketOpenVal, ticketOngoingVal, ticketClosedVal,
                amcTotal, amcDraft, amcActive, amcExpired,
                amcTotalVal, amcDraftVal, amcActiveVal, amcExpiredVal,
                productStockCount, stockTotalVal,
                canAccessQuickMenu, canViewLeadQuote, canViewCustomer, canViewProduct, canViewExhibition, canViewEquipment, canViewTicket, canViewAmc, canViewUsers,
                canCreateCompany, canExport,
                // Advanced Analytics safe bindings (uses backend data if present, otherwise keeps safe state)
                complaintBreakdown: s.complaint_counts?.breakdown ?? 0,
                complaintPm: s.complaint_counts?.pm ?? 0,
                complaintFreeCall: s.complaint_counts?.free_call ?? 0,
                amcExpired: s.amc_renewals?.expired ?? this.state.amcExpired,
                amcExpiredVal: s.amc_renewals?.expired_val ?? this.state.amcExpiredVal,
                amcExpiring30: s.amc_renewals?.expiring_30 ?? this.state.amcExpiring30,
                amcExpiring30Val: s.amc_renewals?.expiring_30_val ?? this.state.amcExpiring30Val,
                amcExpiring60: s.amc_renewals?.expiring_60 ?? this.state.amcExpiring60,
                amcExpiring60Val: s.amc_renewals?.expiring_60_val ?? this.state.amcExpiring60Val,
                amcSecure: s.amc_renewals?.secure ?? this.state.amcSecure,
                amcSecureVal: s.amc_renewals?.secure_val ?? this.state.amcSecureVal,
                lowStockItems: s.low_stock_items !== undefined ? s.low_stock_items : this.state.lowStockItems,
                outOfStockCount: s.out_of_stock_count ?? 0,
                lowStockCount: s.low_stock_count ?? 0,
                totalRegisteredStock: s.total_registered_stock ?? 0,
                customSalesTrend: s.sales_trend || null,
                viewAsAccessibleUids: s.accessible_uids || [],
                viewAsLeadUids: s.lead_uids || null,
                viewAsEqUids: s.eq_uids || null,
                viewAsTicketUids: s.ticket_uids || null,
                viewAsAmcUids: s.amc_uids || null,
                viewAsScopes: {
                    lead: s.permissions?.scope_lead_quote,
                    equipment: s.permissions?.scope_equipment,
                    ticket: s.permissions?.scope_service_ticket,
                    amc: s.permissions?.scope_amc,
                },
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

    go(action) {
        if (typeof action === 'object' && action !== null) {
            action = { ...action };
            action.domain = action.domain ? [...action.domain] : [];
            action.context = action.context ? { ...action.context } : {};

            // Universal 'View As' Filtering: Applies to EVERY card and model!
            if (this.state.viewAsUserId) {
                const uid = this.state.viewAsUserId;
                const uids = (this.state.viewAsAccessibleUids && this.state.viewAsAccessibleUids.length)
                    ? this.state.viewAsAccessibleUids
                    : [uid];
                const scopes = this.state.viewAsScopes || {};
                const m = action.res_model;

                action.context = action.context || {};
                action.context.filter_employee_user_id = String(uid);

                if (['crm.lead', 'sale.order'].includes(m)) {
                    if (scopes.lead === 'none' || !this.state.canViewLeadQuote) {
                        action.domain.push(["id", "=", -1]);
                    } else if (scopes.lead !== 'all' && scopes.lead !== 'admin') {
                        const leadUids = (this.state.viewAsLeadUids && this.state.viewAsLeadUids.length) ? this.state.viewAsLeadUids : [uid];
                        // If user has access to multiple employees or subordinates, show all of them
                        action.domain.push("|", ["user_id", "in", leadUids], "&", ["user_id", "=", false], ["create_uid", "in", leadUids]);
                    }
                } else if (m === 'service.ticket') {
                    if (scopes.ticket !== 'all' && scopes.ticket !== 'admin') {
                        const ticketUids = (this.state.viewAsTicketUids && this.state.viewAsTicketUids.length) ? this.state.viewAsTicketUids : [uid];
                        action.domain.push("|", ["engineer_id", "in", ticketUids], ["create_uid", "in", ticketUids]);
                    }
                } else if (m === 'equipment.master') {
                    if (scopes.equipment !== 'all' && scopes.equipment !== 'admin') {
                        const eqUids = (this.state.viewAsEqUids && this.state.viewAsEqUids.length) ? this.state.viewAsEqUids : (this.state.viewAsAccessibleUids?.length ? this.state.viewAsAccessibleUids : [uid]);
                        action.domain.push(["create_uid", "in", eqUids]);
                    }
                } else if (m === 'amc.contract') {
                    if (scopes.amc !== 'all' && scopes.amc !== 'admin') {
                        const amcUids = (this.state.viewAsAmcUids && this.state.viewAsAmcUids.length) ? this.state.viewAsAmcUids : [uid];
                        action.domain.push(["create_uid", "in", amcUids]);
                    }
                } else if (m === 'exhibition.contact') {
                    // Exhibition contacts are shared or personal
                } else if (m === 'calendar.event') {
                    action.domain.push("|", ["user_id", "in", [uid]], ["partner_ids.user_ids", "in", [uid]]);
                }
            }
        }
        this.actionService.doAction(action, { clearBreadcrumbs: true });
    }
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

        const seqMap = {
            draft: 30,
            sent: 35,
            negotiation: 40,
            order_expected: 50,
            won: 90
        };
        const seq = seqMap[stage] || 30;
        let leadDomain = [["active", "=", true], ["x_stage_sequence", "=", seq]];
        if (seq !== 90) {
            leadDomain.push(["x_stage_sequence", "!=", 90]);
        }

        this.go({
            type: "ir.actions.act_window",
            name: (labels[stage] || stage) + " Leads & Deals",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: [...leadDomain, ...cd],
            context: { allowed_company_ids: this.state.selectedCompanies }
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
        if (!this.state.isAdmin && !this.state.canViewEquipment) {
            this.showAccessDenied("Equipment Master");
            return;
        }
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
        if (!this.state.isAdmin && !this.state.canViewTicket) {
            this.showAccessDenied("Service Tickets");
            return;
        }
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

    assignTaskComingSoon(ev) {
        if (ev && (ev.ctrlKey || ev.altKey || ev.shiftKey)) {
            this.openAssignTaskWizard();
            return;
        }
        this.showToast("Assign Task feature is coming soon!");
    }

    openAssignTaskWizard() {
        this.go({
            type: "ir.actions.act_window",
            name: "Assign Work",
            res_model: "crm.task.assign.wizard",
            views: [[false, "form"]],
            target: "new",
        });
    }

    openInsightsComingSoon() {
        this.actionService.doAction("crm_analytics_dashboard");
    }

    async openViewAsModal() {
        this.state.userDropdownOpen = false;
        this.state.selectedViewAsId = null;
        this.state.viewAsDropdownOpen = false;
        try {
            // Exclude current logged in user
            const excludeIds = [user.userId];
            const users = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "search_read",
                args: [[
                    ["active", "=", true],
                    ["share", "=", false],
                    ["id", "not in", excludeIds]
                ]],
                kwargs: { fields: ["id", "name"], limit: 100, order: "name asc" }
            });
            this.state.internalUsers = (users || []).filter(u =>
                u.id !== user.userId && u.name.toLowerCase() !== "administrator"
            );
            this.state.selectedViewAsId = null;
            this.state.viewAsModalOpen = true;
        } catch (e) { }
    }

    closeViewAsModal() {
        this.state.viewAsModalOpen = false;
    }

    onViewAsSelect(ev) {
        this.state.selectedViewAsId = parseInt(ev.target.value, 10);
    }

    async applyViewAs() {
        if (!this.state.selectedViewAsId) return;
        const u = this.state.internalUsers.find(x => x.id === this.state.selectedViewAsId);
        if (!u) return;
        this.state.viewAsUserId = u.id;
        this.state.viewAsUserName = u.name;
        this.state.viewAsModalOpen = false;
        this.state.isAdmin = false;
        try {
            sessionStorage.setItem("crm_view_as_uid", String(u.id));
            sessionStorage.setItem("crm_view_as_uname", u.name);
            localStorage.removeItem("crm_view_as_uid");
            localStorage.removeItem("crm_view_as_uname");
        } catch (e) { }
        this.showToast("Now viewing dashboard as " + u.name);
        await this.loadStats();
        await this.loadSalesTrendRange(this.state.salesRangeMonths || 6);
    }

    async exitViewAs() {
        this.state.viewAsUserId = null;
        this.state.viewAsUserName = "";
        this.state.selectedViewAsId = null;
        this.state.isAdmin = Boolean(user.isAdmin);
        try {
            sessionStorage.removeItem("crm_view_as_uid");
            sessionStorage.removeItem("crm_view_as_uname");
            localStorage.removeItem("crm_view_as_uid");
            localStorage.removeItem("crm_view_as_uname");
        } catch (e) { }
        this.showToast("Returned to Administrator view");
        await this.loadStats();
        await this.loadSalesTrendRange(this.state.salesRangeMonths || 6);
    }

    async openMyPreferences() {
        this.state.userDropdownOpen = false;
        this.state.profileActiveTab = "preferences";
        this.state.profileLoading = true;
        this.state.profileModalOpen = true;

        const currentUid = this.state.viewAsUserId || user.userId;
        try {
            const data = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "get_my_profile_data",
                args: [],
                kwargs: { user_id: currentUid },
            });

            if (data) {
                this.state.profileData = {
                    ...this.state.profileData,
                    ...data,
                };
            }
        } catch (err) {
            console.error("Error loading profile:", err);
            this.showToast("Failed to load profile details.");
        } finally {
            this.state.profileLoading = false;
        }
    }

    closeMyProfileModal() {
        this.state.profileModalOpen = false;
    }

    setProfileTab(tab) {
        this.state.profileActiveTab = tab;
    }

    async saveMyProfile() {
        this.state.profileSaving = true;
        try {
            const p = this.state.profileData;
            const currentUid = this.state.viewAsUserId || user.userId;

            const res = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "save_my_profile_data",
                args: [{
                    name: p.name,
                    login: p.login,
                    email: p.email,
                    phone: p.phone,
                    mobile: p.mobile,
                }],
                kwargs: { user_id: currentUid },
            });

            if (res && res.success === false) {
                this.showToast(res.error || "Failed to update profile.");
                return;
            }

            this.state.userName = p.name;
            this.showToast("Profile updated successfully!");
            this.closeMyProfileModal();
        } catch (err) {
            console.error("Error saving profile:", err);
            const msg = err?.data?.message || err?.message || "Failed to update profile.";
            this.showToast(msg);
        } finally {
            this.state.profileSaving = false;
        }
    }

    openChangePasswordModal() {
        this.state.userDropdownOpen = false;
        this.state.oldPassword = "";
        this.state.newPassword = "";
        this.state.confirmPassword = "";
        this.state.passwordError = "";
        this.state.passwordLoading = false;
        this.state.showOldPassword = false;
        this.state.showNewPassword = false;
        this.state.showConfirmPassword = false;
        this.state.passwordModalOpen = true;
    }

    closeChangePasswordModal() {
        this.state.passwordModalOpen = false;
        this.state.oldPassword = "";
        this.state.newPassword = "";
        this.state.confirmPassword = "";
        this.state.passwordError = "";
        this.state.passwordLoading = false;
    }

    toggleShowOldPassword() {
        this.state.showOldPassword = !this.state.showOldPassword;
    }

    toggleShowNewPassword() {
        this.state.showNewPassword = !this.state.showNewPassword;
    }

    toggleShowConfirmPassword() {
        this.state.showConfirmPassword = !this.state.showConfirmPassword;
    }

    async submitChangePassword() {
        this.state.passwordError = "";
        const oldP = (this.state.oldPassword || "").trim();
        const newP = (this.state.newPassword || "").trim();
        const confP = (this.state.confirmPassword || "").trim();

        if (!oldP) {
            this.state.passwordError = "Please enter your current password.";
            return;
        }
        if (!newP) {
            this.state.passwordError = "Please enter a new password.";
            return;
        }
        if (newP.length < 4) {
            this.state.passwordError = "New password must be at least 4 characters.";
            return;
        }
        if (newP !== confP) {
            this.state.passwordError = "New password and Confirm password do not match.";
            return;
        }

        this.state.passwordLoading = true;
        try {
            const res = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "action_change_own_password",
                args: [oldP, newP, confP],
                kwargs: {},
            });

            this.state.passwordLoading = false;
            if (res && res.success) {
                this.closeChangePasswordModal();
                this.showToast(res.message || "Password changed successfully!");
            } else {
                this.state.passwordError = (res && res.message) ? res.message : "Failed to change password.";
            }
        } catch (err) {
            this.state.passwordLoading = false;
            const errMsg = err?.data?.message || err?.message || "An unexpected error occurred.";
            this.state.passwordError = errMsg;
        }
    }

    toggleMobileSearch() {
        this.state.mobileSearchOpen = !this.state.mobileSearchOpen;
        if (this.state.mobileSearchOpen) {
            setTimeout(() => {
                const inp = document.querySelector(".crm-mobile-search-input");
                if (inp) inp.focus();
            }, 100);
        } else {
            this.state.searchQuery = "";
            this.state.searchResults = [];
            this.state.searchOpen = false;
        }
    }

    openSearchResult(item) {
        this.state.searchOpen = false;
        this.state.mobileSearchOpen = false;
        this.state.searchQuery = "";
        this.state.searchResults = [];

        // If user was clicked, open the Assign Task modal!
        if (item.type === 'User' || item.model === 'res.users') {
            this.state.selectedUser = item;
            this.state.taskTitle = "";
            this.state.taskNote = "";
            this.state.taskDialogOpen = true;
            return;
        }

        // Otherwise (Customer, Lead, AMC, etc.) open its form view
        if (item.model && item.id) {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: item.model,
                res_id: item.id,
                views: [[false, "form"]],
                target: "current",
            });
        }
    }


    createAmc() {
        if (!this.state.isAdmin && !this.state.canViewAmc) {
            this.showAccessDenied("AMC Contracts");
            return;
        }
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
        this.go({
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
            domain: [["x_quote_stage", "=", "won"], ["amount_total", ">", 0], ["x_invoice_date", "!=", false], ...cd],
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
            domain: [["x_quote_stage", "=", "won"], ["amount_total", ">", 0], ["x_invoice_date", "=", false], ...cd],
            context: { allowed_company_ids: this.state.selectedCompanies }
        });
    }

    async newLead() {
        if (!this.state.isAdmin && !this.state.canViewLeadQuote) {
            this.showAccessDenied("Leads & Pipeline");
            return;
        }
        const selected = this.state.selectedCompanies;
        const companyId = (selected && selected.length === 1) ? selected[0] : user.activeCompanies[0].id;
        const wizardId = await this.ormService.create("crm.lead.wizard", [{ company_id: companyId, step: 1 }]);
        this.go({ type: "ir.actions.act_window", res_model: "crm.lead.wizard", res_id: wizardId[0], views: [[false, "form"]], target: "new", name: "Lead Creation" });
    }
    openExhibition() {
        if (!this.state.isAdmin && !this.state.canViewExhibition) {
            this.showAccessDenied("Exhibition Database");
            return;
        }
        this.go({ type: "ir.actions.act_window", name: "Exhibition Contacts", res_model: "exhibition.contact", views: [[false, "list"], [false, "form"]] });
    }
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

    toggleMobileSearch() {
        this.state.mobileSearchOpen = !this.state.mobileSearchOpen;
        if (!this.state.mobileSearchOpen) {
            this.state.searchResults = [];
            this.state.searchQuery = "";
            this.state.searchOpen = false;
        }
    }

    openSearchResult(item) {
        this.state.mobileSearchOpen = false;
        this.openTaskDialog(item);
    }

    async assignTask() {
        if (!this.state.selectedUser) {
            this.showToast("Please select a team member to assign the task to.");
            return;
        }
        if (!this.state.taskTitle || !this.state.taskTitle.trim()) {
            this.showToast("Please enter a task title.");
            return;
        }

        this.state.taskSubmitting = true;
        try {
            let attachmentIds = [];
            // If attachment is uploaded, save it to ir.attachment
            if (this.state.taskAttachmentName && this.state.taskAttachmentData) {
                try {
                    const attId = await rpc("/web/dataset/call_kw", {
                        model: "ir.attachment",
                        method: "create",
                        args: [{
                            name: this.state.taskAttachmentName,
                            datas: this.state.taskAttachmentData,
                            res_model: "mail.activity",
                            res_id: 0,
                            type: "binary",
                        }],
                        kwargs: {},
                    });
                    if (attId) attachmentIds.push(attId);
                } catch (attErr) {
                    console.error("Attachment upload error:", attErr);
                }
            }

            const deadline = this.state.taskDeadline || new Date().toISOString().split('T')[0];

            // Call backend sudo method to ensure task activity and notification are created
            const assignRes = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "assign_team_task",
                args: [this.state.selectedUser.id, this.state.taskTitle.trim()],
                kwargs: {
                    note: this.state.taskNote ? this.state.taskNote.trim() : "",
                    deadline: deadline,
                    attachment_name: this.state.taskAttachmentName || "",
                    attachment_data: this.state.taskAttachmentData || "",
                },
            });

            if (assignRes && assignRes.success === false) {
                console.warn("Backend assign warning:", assignRes.error);
                this.showToast("Failed to assign task: " + (assignRes.error || "Unknown error"));
                return;
            }

            this.showToast("Task assigned to " + this.state.selectedUser.name);
            this.closeTaskDialog();
        } catch (e) {
            console.error("Assign task error:", e);
            const errStr = e?.data?.message || e?.message || "Server Error";
            this.showToast("Error: " + errStr);
        } finally {
            this.state.taskSubmitting = false;
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
    async _getCurrentPartnerId() {
        if (this._cachedPartnerId) return this._cachedPartnerId;
        if (user.partnerId) {
            this._cachedPartnerId = user.partnerId;
            return this._cachedPartnerId;
        }
        try {
            const uid = this.state.viewAsUserId || user.userId;
            const uData = await rpc("/web/dataset/call_kw", {
                model: "res.users",
                method: "read",
                args: [[uid], ['partner_id']],
                kwargs: {}
            });
            if (uData && uData.length && uData[0].partner_id) {
                this._cachedPartnerId = uData[0].partner_id[0];
                return this._cachedPartnerId;
            }
        } catch (e) {
            console.error("Failed to get partnerId:", e);
        }
        return 0;
    }
    async loadNotifCount() {
        try {
            const readIds = JSON.parse(localStorage.getItem('crm_read_notifs') || '[]');
            const partnerId = await this._getCurrentPartnerId();
            if (!partnerId) return;
            const messages = await rpc('/web/dataset/call_kw', {
                model: 'mail.message',
                method: 'search_read',
                args: [[['partner_ids', 'in', [partnerId]]]],
                kwargs: { fields: ['id'], limit: 30, order: 'date desc' }
            });
            this.state.notifCount = messages.map(m => m.id).filter(id => !readIds.includes(id)).length;
        } catch (e) { this.state.notifCount = 0; }
    }
    async toggleNotifications() {
        this.state.notifOpen = !this.state.notifOpen;
        if (this.state.notifOpen) {
            try {
                const partnerId = await this._getCurrentPartnerId();
                // Query the latest notifications for current user, strictly newest 3
                let messages = [];
                if (partnerId) {
                    messages = await rpc('/web/dataset/call_kw', {
                        model: 'mail.message',
                        method: 'search_read',
                        args: [[['partner_ids', 'in', [partnerId]]]],
                        kwargs: { fields: ['id', 'record_name', 'body', 'date', 'res_id', 'model', 'author_id', 'subject'], limit: 3, order: 'date desc' }
                    });
                }
                localStorage.setItem('crm_read_notifs', JSON.stringify(messages.map(m => m.id)));
                this.state.notifCount = 0;
                this.state.notifications = messages.map(m => {
                    // Extract author/manager/owner name cleanly without any brackets or designations
                    let senderName = '';
                    if (m.author_id && m.author_id[1]) {
                        senderName = m.author_id[1].replace(/\s*\(.*?\)\s*/g, '').trim();
                    }

                    // Extract task title
                    let taskTitle = '';
                    const taskMatch = m.body ? m.body.match(/<b>New Task:\s*([^<]+)<\/b>/i) : null;
                    if (taskMatch && taskMatch[1]) {
                        taskTitle = taskMatch[1].trim();
                    } else if (m.subject && m.subject.trim()) {
                        taskTitle = m.subject.trim();
                    } else if (m.record_name && m.record_name.trim()) {
                        taskTitle = m.record_name.trim();
                    }

                    // If it is standard Odoo automated activity notification (e.g. "Dear Pratham, Administrator has just assigned you...")
                    // extract the actual task or document name
                    let rawBody = m.body ? m.body.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() : '';
                    const docMatch = rawBody.match(/activity:\s*Document:\s*["“']?([^"”'(\n]+)/i);
                    if (docMatch && docMatch[1]) {
                        taskTitle = docMatch[1].trim();
                    } else {
                        const leadMatch = rawBody.match(/assigned to the Lead\s+(.*)/i);
                        if (leadMatch && leadMatch[1]) {
                            taskTitle = leadMatch[1].trim().replace(/\.$/, '');
                        }
                    }

                    // Extract instructions/notes cleanly
                    let taskInstructions = '';
                    if (taskMatch) {
                        taskInstructions = rawBody.replace(/^New Task:\s*[^.]*?(?=\s+|$)/i, '').replace(/📎 Attached:.*$/i, '').trim();
                    } else if (rawBody) {
                        taskInstructions = rawBody.replace(/📎 Attached:.*$/i, '').trim();
                    }

                    // Extract attached filename if mentioned in body
                    let attachedFileName = '';
                    const attMatch = m.body ? m.body.match(/📎 Attached:\s*([^<]+)/i) : null;
                    if (attMatch && attMatch[1]) {
                        attachedFileName = attMatch[1].trim();
                    }

                    return {
                        id: m.id,
                        res_id: m.res_id,
                        model: m.model,
                        sender: senderName || 'Administrator',
                        task_title: taskTitle,
                        task_note: taskInstructions,
                        attachment_name: attachedFileName,
                        attachment_ids: m.attachment_ids || [],
                        date: m.date ? m.date.substring(0, 16) : ''
                    };
                });
            } catch (e) {
                console.error("Notifications fetch error:", e);
                this.state.notifications = [];
            }
        }
    }
    openLead(notif) {
        this.state.notifOpen = false;
        if (notif.model === 'crm.lead') {
            this.actionService.doAction({ type: 'ir.actions.act_window', res_model: 'crm.lead', res_id: notif.res_id, view_mode: 'form', views: [[false, 'form']], target: 'current' });
        } else {
            // For tasks (res.partner / activities), open Task Detail Wizard Modal instead of partner profile
            this.openTaskDetailModal(notif);
        }
    }

    openTaskDetailModal(notif) {
        this.state.selectedTaskDetail = notif;
        this.state.taskDetailModalOpen = true;
    }

    closeTaskDetailModal() {
        this.state.taskDetailModalOpen = false;
        this.state.selectedTaskDetail = null;
    }

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

    get totalComplaints() {
        return (this.state.complaintBreakdown || 0) + (this.state.complaintPm || 0) + (this.state.complaintFreeCall || 0);
    }

    get complaintBreakdownPct() {
        const total = this.totalComplaints;
        if (!total) return 0;
        return Math.round(((this.state.complaintBreakdown || 0) / total) * 100);
    }

    get complaintPmPct() {
        const total = this.totalComplaints;
        if (!total) return 0;
        return Math.round(((this.state.complaintPm || 0) / total) * 100);
    }

    get complaintFreeCallPct() {
        const total = this.totalComplaints;
        if (!total) return 0;
        return Math.round(((this.state.complaintFreeCall || 0) / total) * 100);
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
            return;
        }

        // Allow navigation, control keys, Tab, Enter, Backspace, Delete
        if (e.ctrlKey || e.metaKey || e.altKey || [
            "Backspace", "Delete", "Tab", "Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"
        ].includes(e.key)) {
            return;
        }

        // If user types '/' but 2 slashes already exist, or typing consecutive slashes
        if (e.key === "/") {
            const val = this.state[fieldName] || "";
            const slashCount = (val.match(/\//g) || []).length;
            if (slashCount >= 2 || val.endsWith("/") || val.length === 0) {
                e.preventDefault();
                this.showToast("Cannot add extra '/'");
                return;
            }
        }

        // If typing a single character that is NOT a number and NOT slash, show warning toast
        if (e.key.length === 1 && !/[0-9/]/.test(e.key)) {
            e.preventDefault();
            this.showToast("Only numbers and '/' are allowed");
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
        e.target.value = val;
        this.state[fieldName] = val;
    }

    validateDateInput(rawStr, fieldLabel) {
        if (!rawStr || !rawStr.trim()) {
            return { error: `Please enter ${fieldLabel}` };
        }
        const parts = rawStr.trim().split("/");
        if (parts.length !== 3) {
            return { error: `${fieldLabel} must be in DD/MM/YYYY format` };
        }
        let [dStr, mStr, yStr] = parts.map(p => p.trim());
        if (!dStr || !mStr || !yStr) {
            return { error: `Please complete ${fieldLabel} in DD/MM/YYYY format` };
        }

        // Smart year parsing (2 digits -> 4 digits)
        if (yStr.length === 2) {
            const currentYearPrefix = String(new Date().getFullYear()).substring(0, 2);
            yStr = currentYearPrefix + yStr;
        } else if (yStr.length === 4 && yStr.startsWith("0")) {
            yStr = yStr.replace(/^0+/, "");
            if (yStr.length === 2) {
                const currentYearPrefix = String(new Date().getFullYear()).substring(0, 2);
                yStr = currentYearPrefix + yStr;
            }
        }
        if (yStr.length !== 4) {
            return { error: `Please enter a 4-digit year for ${fieldLabel}` };
        }

        const day = parseInt(dStr, 10);
        const month = parseInt(mStr, 10);
        const year = parseInt(yStr, 10);

        if (isNaN(day) || isNaN(month) || isNaN(year)) {
            return { error: `Please enter valid numbers for ${fieldLabel}` };
        }

        // Check month bounds
        if (month < 1 || month > 12) {
            return { error: `Invalid month in ${fieldLabel}! Month must be between 01 and 12` };
        }

        // Check day bounds for specific month & leap year
        const maxDaysInMonth = new Date(year, month, 0).getDate();
        if (day < 1 || day > maxDaysInMonth) {
            return { error: `Invalid day in ${fieldLabel}! Maximum day for this month is ${maxDaysInMonth}` };
        }

        const padD = String(day).padStart(2, "0");
        const padM = String(month).padStart(2, "0");
        const dateStr = `${year}-${padM}-${padD}`;
        const dateObj = new Date(year, month - 1, day, 23, 59, 59);

        // Check future date
        const today = new Date();
        today.setHours(23, 59, 59, 999);
        if (dateObj > today) {
            return { error: `${fieldLabel} cannot be in the future` };
        }

        return { dateStr: dateStr, dateObj: dateObj };
    }

    async applyCustomDateRange() {
        const startCheck = this.validateDateInput(this.state.customStartDateInput, "Start Date");
        if (startCheck.error) {
            this.showToast(startCheck.error);
            return;
        }

        const endCheck = this.validateDateInput(this.state.customEndDateInput, "End Date");
        if (endCheck.error) {
            this.showToast(endCheck.error);
            return;
        }

        const startStr = startCheck.dateStr;
        const endStr = endCheck.dateStr;

        if (startStr > endStr) {
            this.showToast("Start date cannot be after End date");
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

    _getSalesChartUserDomain() {
        if (this.state.viewAsUserId && this.state.viewAsScopes?.lead !== 'all' && this.state.viewAsScopes?.lead !== 'admin') {
            const allowed = (this.state.viewAsLeadUids && this.state.viewAsLeadUids.length)
                ? this.state.viewAsLeadUids
                : [this.state.viewAsUserId];
            return [["user_id", "in", allowed]];
        }
        return [];
    }

    async _fetchHourlySales(dateStr) {
        const domain = [
            ["date_order", ">=", dateStr + " 00:00:00"],
            ["date_order", "<=", dateStr + " 23:59:59"],
            "|",
            ["x_quote_stage", "=", "won"],
            ["state", "in", ["sale", "done"]],
            ...this._getSalesChartUserDomain()
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
            ["state", "in", ["sale", "done"]],
            ...this._getSalesChartUserDomain()
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
            ["state", "in", ["sale", "done"]],
            ...this._getSalesChartUserDomain()
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
            ["state", "in", ["sale", "done"]],
            ...this._getSalesChartUserDomain()
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
                ["state", "in", ["sale", "done"]],
                ...this._getSalesChartUserDomain()
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
        let title = m.label || "Orders";

        if (m.startDt && m.endDt) {
            domain.push(["date_order", ">=", m.startDt]);
            domain.push(["date_order", "<=", m.endDt]);
            title = m.label;
        } else if (m.fullDay) {
            domain.push(["date_order", ">=", m.fullDay + " 00:00:00"]);
            domain.push(["date_order", "<=", m.fullDay + " 23:59:59"]);
            title = m.label;
        } else if (m.fullMonth) {
            const [yr, mo] = m.fullMonth.split("-").map(Number);
            const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            const lastDay = new Date(yr, mo, 0).getDate();
            const startStr = `${m.fullMonth}-01 00:00:00`;
            const endStr = `${m.fullMonth}-${String(lastDay).padStart(2, "0")} 23:59:59`;
            domain.push(["date_order", ">=", startStr]);
            domain.push(["date_order", "<=", endStr]);
            title = `${monthNames[mo - 1]} ${yr}`;
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
            breakdown: [["complaint_type", "=", "breakdown"]],
            pm: [["complaint_type", "=", "pm"]],
            preventive: [["complaint_type", "=", "pm"]],
            free_call: [["complaint_type", "=", "free_call"]]
        };
        const titleMap = {
            breakdown: "Breakdown",
            pm: "PM",
            preventive: "PM",
            free_call: "Free Call"
        };
        const domain = domainMap[type] || [];
        const cleanTitle = titleMap[type] || title;
        this.openServiceTicketList(domain, cleanTitle);
    }

    openProductMaster() {
        if (!this.state.isAdmin && !this.state.canViewProduct) {
            this.showAccessDenied("Products");
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Master",
            res_model: "product.template",
            view_mode: "kanban,list,form",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            target: "current",
            context: { search_default_filter_to_sell: 1 },
        });
    }


    openAmcRenewalList(type, title = "AMC Renewals") {
        if (!this.state.isAdmin && !this.state.canViewAmc) {
            this.showAccessDenied("AMC Contracts");
            return;
        }
        let domain = [];
        const today = new Date();
        const fmtDate = (d) => d.toISOString().split('T')[0];

        let cleanTitle = title;
        if (type === 'expired') {
            cleanTitle = "Expired";
            domain = ["|", ["contract_status", "=", "expired"], "&", ["contract_status", "in", ["active", "renewed"]], ["contract_end_date", "<", fmtDate(today)]];
        } else if (type === '30') {
            cleanTitle = "< 30 Days";
            const target = new Date();
            target.setDate(today.getDate() + 30);
            domain = [["contract_status", "in", ["active", "renewed"]], ["contract_end_date", ">=", fmtDate(today)], ["contract_end_date", "<=", fmtDate(target)]];
        } else if (type === '60') {
            cleanTitle = "30–60 Days";
            const start = new Date();
            start.setDate(today.getDate() + 31);
            const target = new Date();
            target.setDate(today.getDate() + 60);
            domain = [["contract_status", "in", ["active", "renewed"]], ["contract_end_date", ">=", fmtDate(start)], ["contract_end_date", "<=", fmtDate(target)]];
        } else if (type === 'secure') {
            cleanTitle = "> 60 Days";
            const minDate = new Date();
            minDate.setDate(today.getDate() + 60);
            domain = ["|", ["contract_end_date", "=", false], ["contract_end_date", ">", fmtDate(minDate)], ["contract_status", "in", ["active", "renewed"]]];
        }

        this.openAmcList(domain, cleanTitle);
    }

    openLowStockRegistry() {
        if (!this.state.isAdmin && !this.state.canViewProduct) {
            this.showAccessDenied("Products");
            return;
        }
        this.openLowStockFiltered();
    }

    openLowStockFiltered() {
        if (!this.state.isAdmin && !this.state.canViewProduct) {
            this.showAccessDenied("Products");
            return;
        }
        this.go({
            type: "ir.actions.act_window",
            name: "Low Stock",
            res_model: "crm.product.stock",
            views: [[false, "list"], [false, "form"]],
            domain: [["stock_status", "=", "low_stock"]],
            target: "current"
        });
    }

    openOutOfStockFiltered() {
        if (!this.state.isAdmin && !this.state.canViewProduct) {
            this.showAccessDenied("Products");
            return;
        }
        this.go({
            type: "ir.actions.act_window",
            name: "Out of Stock",
            res_model: "crm.product.stock",
            views: [[false, "list"], [false, "form"]],
            domain: [["stock_status", "=", "out_of_stock"]],
            target: "current"
        });
    }
}
registry.category("actions").add("crm_dashboard", CrmDashboard);
export default CrmDashboard;

