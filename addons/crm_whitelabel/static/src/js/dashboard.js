/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState, useExternalListener } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

class CrmDashboard extends Component {
    static template = "crm_whitelabel.Dashboard";

    setup() {
        this.actionService = useService("action");

        this.state = useState({
            open_leads: 0,
            leads: 0,
            qualified: 0,
            opportunity: 0,
            won: 0,
            customers: 0,
            quotes: 0,
            products: 0,
            users: 0,
            revenue: 0,
            userName: user.name || "User",
            companies: [],
            selectedCompanies: [1, 2, 3],
            companyDropdownOpen: false,
            userDropdownOpen: false,
            isAdmin: user.userId === 2,
            adminMenuOpen: false,
            notifCount: 0,
        });

        onMounted(() => {
            this.loadStats();
            this.loadCompanies();
            this.loadNotifications();
            setInterval(() => this.loadNotifications(), 30000);
            // Close dropdowns when clicking outside
            this._closeDropdowns = (e) => {
                if (!e.target.closest('.crm-user-dropdown-wrapper')) {
                    this.state.userDropdownOpen = false;
                }
                if (!e.target.closest('.crm-company-multiselect')) {
                    this.state.companyDropdownOpen = false;
                }
                if (!e.target.closest('.crm-admin-multiselect')) {
                    this.state.adminMenuOpen = false;
                }
            };
            document.addEventListener('click', this._closeDropdowns);
        });
        useExternalListener(window, "click", (ev) => {
            if (this.state.companyDropdownOpen && !ev.target.closest('.crm-company-multiselect')) {
                this.state.companyDropdownOpen = false;
            }
            if (this.state.adminMenuOpen && !ev.target.closest('.crm-admin-multiselect')) {
                this.state.adminMenuOpen = false;
            }
        });
    }

    toggleAdminMenu() {
        this.state.adminMenuOpen = !this.state.adminMenuOpen;
    }

    async loadCompanies() {
        try {
            const res = await rpc("/web/dataset/call_kw", {
                model: "res.company",
                method: "search_read",
                args: [[]],
                kwargs: { fields: ["id", "name"], limit: 20 },
            });
            this.state.companies = res || [];
            // Keep currentCompany from localStorage, don't override it
        } catch(e) {
            this.state.companies = [];
        }
    }

    toggleCompany(cid) {
        const idx = this.state.selectedCompanies.indexOf(cid);
        if (idx === -1) {
            this.state.selectedCompanies.push(cid);
        } else {
            if (this.state.selectedCompanies.length > 1) {
                this.state.selectedCompanies.splice(idx, 1);
            }
        }
        localStorage.setItem('crm_selected_companies', JSON.stringify(this.state.selectedCompanies));
        this.loadStats();
    }

    async loadNotifications() {
        try {
            const result = await rpc('/web/dataset/call_kw', {
                model: 'mail.notification',
                method: 'search_count',
                args: [[['res_partner_id', '=', user.partnerId], ['is_read', '=', false]]],
                kwargs: {},
            });
            this.state.notifCount = result || 0;
        } catch(e) {
            this.state.notifCount = 0;
        }
    }

    openNotifications() {
        // Open a list of unread notifications for current user
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            name: 'My Notifications',
            res_model: 'mail.notification',
            view_mode: 'list',
            views: [[false, 'list']],
            domain: [['res_partner_id', '=', user.partnerId], ['is_read', '=', false]],
            context: {},
            target: 'new',
        });
    }

    toggleUserDropdown() {
        this.state.userDropdownOpen = !this.state.userDropdownOpen;
        this.state.companyDropdownOpen = false;
    }

    toggleCompanyDropdown() {
        this.state.companyDropdownOpen = !this.state.companyDropdownOpen;
        this.state.userDropdownOpen = false;
    }

    isCompanySelected(cid) {
        return this.state.selectedCompanies.includes(cid);
    }

    get selectedCompanyInitial() {
        const selected = this.state.companies.filter(c => this.state.selectedCompanies.includes(c.id));
        if (selected.length === 0) return "?";
        if (selected.length === 1) return selected[0].name[0].toUpperCase();
        return selected.length;
    }

    get selectedCompanyLabel() {
        const names = this.state.companies
            .filter(c => this.state.selectedCompanies.includes(c.id))
            .map(c => c.name);
        if (names.length === 0) return "Select Company";
        if (names.length === 1) return names[0];
        return names.length + " Companies";
    }

    async _count(model, domain = []) {
        return await rpc("/web/dataset/call_kw", {
            model: model,
            method: "search_count",
            args: [domain],
            kwargs: {},
        });
    }

    async _sum(model, field, domain = []) {
        try {
            const res = await rpc("/web/dataset/call_kw", {
                model: model,
                method: "read_group",
                args: [domain, [field], []],
                kwargs: {},
            });
            return res[0] ? (res[0][field] || 0) : 0;
        } catch(e) {
            return 0;
        }
    }

    async loadStats() {
        try {
            // Get ALL company ids from API
            const companyRes = await rpc("/web/dataset/call_kw", {
                model: "res.company",
                method: "search_read",
                args: [[], ["id"]],
                kwargs: {limit: 100},
            });
            const allCids = companyRes.map(c => c.id);
            const activeCids = this.state.selectedCompanies.length ? this.state.selectedCompanies : allCids;
            const companyDomain = [["company_id","in",activeCids]];
            const isAdmin = user.userId === 2;
            const userDomain = isAdmin ? [] : [["user_id","=",user.userId]];
            const [
                leads,
                qualified,
                opp,
                quotes,
                won,
                customers,
                products,
                users,
                quoteRevenue,
                wonRevenue
            ] = await Promise.all([
                this._count("crm.lead", [["active","=",true],["x_stage_sequence","=",0],...companyDomain,...userDomain]),
                this._count("crm.lead", [["active","=",true],["x_stage_sequence","=",1],...companyDomain,...userDomain]),
                this._count("crm.lead", [["active","=",true],["x_stage_sequence","=",2],...companyDomain,...userDomain]),
                this._count("sale.order", [["x_quote_stage","not in",["won","lost"]],["state","!=","cancel"],...companyDomain,...userDomain]),
                this._count("sale.order", [["x_quote_stage","=","won"],...companyDomain,...userDomain]),
                this._count("res.partner", isAdmin ? [["customer_rank",">",0]] : [["customer_rank",">",0],["user_id","=",user.userId]]),
                this._count("product.template", [["sale_ok","=",true]]),
                this._count("res.users", [["active","=",true],["share","=",false]]),
                this._sum("sale.order", "amount_total", [["x_quote_stage","not in",["won","lost"]],["state","!=","cancel"],...companyDomain,...userDomain]),
                this._sum("sale.order", "amount_total", [["x_quote_stage","=","won"],...companyDomain,...userDomain]),
            ]);

            const userName = user.name || "User";
            Object.assign(this.state, {
                leads,
                qualified,
                opportunity: opp,
                open_leads: leads,
                quotes,
                won,
                customers,
                products,
                users,
                revenue: wonRevenue,
                quoteRevenue: quoteRevenue,
                wonRevenue,
                userName: userName,
            });

        } catch (e) {
            console.log("Dashboard error:", e);
        }
    }

    fmt(n) {
        if (!n) return "₹0";
        if (n >= 10000000) return "₹" + (n / 10000000).toFixed(1) + "Cr";
        if (n >= 100000) return "₹" + (n / 100000).toFixed(1) + "L";
        if (n >= 1000) return "₹" + (n / 1000).toFixed(1) + "K";
        return "₹" + Math.round(n);
    }

    go(action) {
        this.actionService.doAction(action);
    }

    openLeads() {
        const isAdmin = user.userId === 2;
        const userFilter = isAdmin ? [] : [["user_id","=",user.userId]];
        const domain = [["active","=",true],["company_id","in",this.state.selectedCompanies],...userFilter];
        this.go({ type:"ir.actions.act_window", name:"Leads", res_model:"crm.lead", views:[[false,"list"],[false,"form"]], domain });
    }
    openQuotes() {
        const isAdmin = user.userId === 2;
        const userFilter = isAdmin ? [] : [["user_id","=",user.userId]];
        const domain = [["x_quote_stage","not in",["won","lost"]],["state","!=","cancel"],["company_id","in",this.state.selectedCompanies],...userFilter];
        this.go({ type:"ir.actions.act_window", name:"Quotations", res_model:"sale.order", views:[[false,"list"],[false,"form"]], domain });
    }
    openContacts() {
        const isAdmin = user.userId === 2;
        const userFilter = isAdmin ? [] : [["user_id","=",user.userId]];
        const domain = [["customer_rank",">",0],...userFilter];
        this.go({ type:"ir.actions.act_window", name:"Customers", res_model:"res.partner", views:[[false,"list"],[false,"form"]], domain });
    }
    openProducts() { this.go({ type:"ir.actions.act_window", name:"Products", res_model:"product.template", views:[[false,"list"],[false,"form"]] }); }
    openUsers() { this.go({ type:"ir.actions.act_window", name:"Users", res_model:"res.users", views:[[false,"list"],[false,"form"]], domain:[["share","=",false]] }); }
    openWon() {
        const isAdmin = user.userId === 2;
        const userFilter = isAdmin ? [] : [["user_id","=",user.userId]];
        const domain = [["x_quote_stage","=","won"],["company_id","in",this.state.selectedCompanies],...userFilter];
        this.go({ type:"ir.actions.act_window", name:"Won Deals", res_model:"sale.order", views:[[false,"list"],[false,"form"]], domain });
    }
    openStage(ev) { const seq = parseInt(ev.currentTarget.dataset.seq || 0); this.go({ type:"ir.actions.act_window", name:"Pipeline", res_model:"crm.lead", views:[[false,"list"],[false,"form"]], domain:[["active","=",true],["x_stage_sequence","=",seq]] }); }
    newLead() { this.go(405); }
}

registry.category("actions").add("crm_dashboard", CrmDashboard);

export default CrmDashboard;
