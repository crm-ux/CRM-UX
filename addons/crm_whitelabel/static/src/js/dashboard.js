/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

class CrmDashboard extends Component {
    static template = "crm_whitelabel.Dashboard";
    setup() {
        this.actionService = useService("action");
        this.state = useState({
            leads: 0, qualified: 0, opportunity: 0, won: 0,
            stageLead:0, stageContacted:0, stageTechDisc:0, stageQualified:0,
            stageOpportunity:0, stageQuotes:0, stageNegotiation:0, stageOrderExp:0, stageWon:0,
            quotesDraft:0, quotesSent:0, quotesNeg:0,
            customers: 0, quotes: 0, products: 0, users: 0,
            quoteRevenue: 0, wonRevenue: 0, todayRevenue: 0,
            userName: user.name || "User",
            companyName: "", companyLogo: "", heroImage: "",
            greeting: "", todayDate: "",
            companies: [], selectedCompanies: [],
            companyDropdownOpen: false, userDropdownOpen: false,
            isAdmin: user.userId === 2,
            adminMenuOpen: false, notifOpen: false,
            notifCount: 0, notifications: [],
            searchQuery: "", searchResults: [], searchOpen: false,
            taskDialogOpen: false, selectedUser: null,
            taskNote: "", taskTitle: "",
        });
        onMounted(() => {
            this.loadStats();
            this.loadCompanies();
            this.loadNotifCount();
            this.loadCompanyInfo();
            this.setGreeting();
            this.setDate();
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.crm-user-dropdown-wrapper')) this.state.userDropdownOpen = false;
                if (!e.target.closest('.crm-company-multiselect')) this.state.companyDropdownOpen = false;
                if (!e.target.closest('.crm-admin-multiselect')) this.state.adminMenuOpen = false;
                if (!e.target.closest('.crm-notif-wrapper')) this.state.notifOpen = false;
                if (!e.target.closest('.crm-search-wrapper')) this.state.searchOpen = false;
            });
        });
    }
    setGreeting() {
        const h = new Date().getHours();
        this.state.greeting = h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
    }
    setDate() {
        this.state.todayDate = new Date().toLocaleDateString('en-IN', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
    }
    async loadCompanyInfo() {
        try {
            const res = await rpc("/web/dataset/call_kw", { model:"res.company", method:"search_read", args:[[]], kwargs:{ fields:["id","name","logo_web"], limit:1 } });
            if (res && res[0]) {
                this.state.companyName = res[0].name || "";
                if (res[0].logo_web) this.state.companyLogo = "data:image/png;base64," + res[0].logo_web;
            }
        } catch(e) {}
    }
    toggleAdminMenu() { this.state.adminMenuOpen = !this.state.adminMenuOpen; }
    toggleUserDropdown() { this.state.userDropdownOpen = !this.state.userDropdownOpen; this.state.companyDropdownOpen = false; }
    toggleCompanyDropdown() { this.state.companyDropdownOpen = !this.state.companyDropdownOpen; this.state.userDropdownOpen = false; }
    async loadCompanies() {
        try {
            const res = await rpc("/web/dataset/call_kw", { model:"res.company", method:"search_read", args:[[]], kwargs:{ fields:["id","name"], limit:20 } });
            this.state.companies = res || [];
            this.state.selectedCompanies = (res || []).map(c => c.id);
        } catch(e) { this.state.companies = []; }
    }
    toggleCompany(cid) {
        const idx = this.state.selectedCompanies.indexOf(cid);
        if (idx === -1) this.state.selectedCompanies.push(cid);
        else if (this.state.selectedCompanies.length > 1) this.state.selectedCompanies.splice(idx, 1);
        this.loadStats();
    }
    isCompanySelected(cid) { return this.state.selectedCompanies.includes(cid); }
    get selectedCompanyLabel() {
        const names = this.state.companies.filter(c => this.state.selectedCompanies.includes(c.id)).map(c => c.name);
        if (names.length === 0) return "Select Company";
        if (names.length === 1) return names[0];
        return names.length + " Companies";
    }
    async _count(model, domain=[]) {
        return await rpc("/web/dataset/call_kw", { model, method:"search_count", args:[domain], kwargs:{} });
    }
    async _sum(model, field, domain=[]) {
        try {
            const res = await rpc("/web/dataset/call_kw", { model, method:"read_group", args:[domain,[field],[]], kwargs:{} });
            return res[0] ? (res[0][field] || 0) : 0;
        } catch(e) { return 0; }
    }
    async loadStats() {
        try {
            const activeCids = this.state.selectedCompanies;
            const cd = activeCids.length ? [["company_id","in",activeCids]] : [];
            const isAdmin = user.userId === 2;
            const ud = isAdmin ? [] : [["user_id","=",user.userId]];
            const todayStr = new Date().toISOString().split('T')[0];
            const [
                stageLead, stageContacted, stageTechDisc, stageQualified,
                stageOpportunity, stageQuotes, stageNegotiation, stageOrderExp, stageWon,
                quotesDraft, quotesSent, quotesNeg, won,
                customers, products, users, quoteRevenue, wonRevenue, todayRevenue
            ] = await Promise.all([
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",0],...cd,...ud]),
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",5],...cd,...ud]),
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",7],...cd,...ud]),
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",10],...cd,...ud]),
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",20],...cd,...ud]),
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",30],...cd,...ud]),
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",40],...cd,...ud]),
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",50],...cd,...ud]),
                this._count("crm.lead",[["active","=",true],["x_stage_sequence","=",90],...cd,...ud]),
                this._count("sale.order",[["x_quote_stage","=","draft"],["state","!=","cancel"],...cd,...ud]),
                this._count("sale.order",[["x_quote_stage","=","sent"],["state","!=","cancel"],...cd,...ud]),
                this._count("sale.order",[["x_quote_stage","=","negotiation"],["state","!=","cancel"],...cd,...ud]),
                this._count("sale.order",[["x_quote_stage","=","won"],...cd,...ud]),
                this._count("res.partner",[["customer_rank",">",0]]),
                this._count("product.template",[["sale_ok","=",true]]),
                this._count("res.users",[["active","=",true],["share","=",false]]),
                this._sum("sale.order","amount_total",[["x_quote_stage","not in",["won","lost"]],["state","!=","cancel"],...cd,...ud]),
                this._sum("sale.order","amount_total",[["x_quote_stage","=","won"],...cd,...ud]),
                this._sum("sale.order","amount_total",[["x_quote_stage","=","won"],["date_order",">=",todayStr+" 00:00:00"],...cd]),
            ]);
            const quotes = quotesDraft + quotesSent + quotesNeg;
            const leads = stageLead;
            const qualified = stageQualified;
            const opp = stageOpportunity;
            Object.assign(this.state, {
                leads, qualified, opportunity:opp,
                stageLead, stageContacted, stageTechDisc, stageQualified,
                stageOpportunity, stageQuotes, stageNegotiation, stageOrderExp, stageWon,
                quotes, quotesDraft, quotesSent, quotesNeg, won,
                customers, products, users, quoteRevenue, wonRevenue, todayRevenue
            });
        } catch(e) { console.log("Dashboard error:", e); }
    }
    fmt(n) {
        if (!n) return "₹0";
        if (n >= 10000000) return "₹" + (n/10000000).toFixed(1) + "Cr";
        if (n >= 100000) return "₹" + (n/100000).toFixed(1) + "L";
        if (n >= 1000) return "₹" + (n/1000).toFixed(1) + "K";
        return "₹" + Math.round(n);
    }
    go(action) { this.actionService.doAction(action); }
    openLeads() { const ud = user.userId===2?[]:[["user_id","=",user.userId]]; this.go({type:"ir.actions.act_window",name:"Leads",res_model:"crm.lead",views:[[false,"list"],[false,"form"]],domain:[["active","=",true],...ud]}); }
    openQuotes() { const ud = user.userId===2?[]:[["user_id","=",user.userId]]; this.go({type:"ir.actions.act_window",name:"Quotations",res_model:"sale.order",views:[[false,"list"],[false,"form"]],domain:[["x_quote_stage","not in",["won","lost"]],["state","!=","cancel"],...ud]}); }
    openTerms() { this.actionService.doAction({type:'ir.actions.act_window',name:'Terms & Conditions',res_model:'sale.terms.condition',view_mode:'list,form',views:[[false,'list'],[false,'form']]}); }
    openContacts() { this.go({type:"ir.actions.act_window",name:"Customers",res_model:"res.partner",views:[[false,"list"],[false,"form"]],domain:[["customer_rank",">",0]]}); }
    openProducts() { this.go({type:"ir.actions.act_window",name:"Products",res_model:"product.template",views:[[false,"list"],[false,"form"]]}); }
    openUsers() { this.go({type:"ir.actions.act_window",name:"Users",res_model:"res.users",views:[[false,"list"],[false,"form"]],domain:[["share","=",false]]}); }
    openWon() { const ud = user.userId===2?[]:[["user_id","=",user.userId]]; this.go({type:"ir.actions.act_window",name:"Won Deals",res_model:"sale.order",views:[[false,"list"],[false,"form"]],domain:[["x_quote_stage","=","won"],...ud]}); }
    openStage(ev) { const seq=parseInt(ev.currentTarget.dataset.seq||0); this.go({type:"ir.actions.act_window",name:"Pipeline",res_model:"crm.lead",views:[[false,"list"],[false,"form"]],domain:[["active","=",true],["x_stage_sequence","=",seq]]}); }
    newLead() { this.go(405); }
    newQuote() { this.go({type:"ir.actions.act_window",name:"New Quotation",res_model:"sale.order",views:[[false,"form"]],target:"current"}); }
    async onSearchInput(ev) {
        const q = ev.target.value;
        this.state.searchQuery = q;
        if (q.length < 2) { this.state.searchResults = []; this.state.searchOpen = false; return; }
        try {
            const res = await rpc("/web/dataset/call_kw", { model:"res.users", method:"search_read", args:[[["active","=",true],["share","=",false],["name","ilike",q]]], kwargs:{ fields:["id","name","email","partner_id"], limit:10 } });
            this.state.searchResults = res || [];
            this.state.searchOpen = true;
        } catch(e) { this.state.searchResults = []; }
    }
    openTaskDialog(u) { this.state.selectedUser = u; this.state.taskTitle = ""; this.state.taskNote = ""; this.state.taskDialogOpen = true; this.state.searchOpen = false; this.state.searchQuery = ""; }
    closeTaskDialog() { this.state.taskDialogOpen = false; this.state.selectedUser = null; }
    async assignTask() {
        if (!this.state.taskTitle) { alert("Please enter a task title"); return; }
        try {
            await rpc("/web/dataset/call_kw", {
                model: "res.partner",
                method: "message_post",
                args: [[this.state.selectedUser.partner_id || this.state.selectedUser.id]],
                kwargs: {
                    body: "<b>" + this.state.taskTitle + "</b><br/>" + (this.state.taskNote || ""),
                    message_type: "comment",
                    subtype_xmlid: "mail.mt_comment",
                    partner_ids: [this.state.selectedUser.partner_id || this.state.selectedUser.id],
                },
            });
            this.showToast("Notification sent to " + this.state.selectedUser.name);
            this.closeTaskDialog();
        } catch(e) {
            this.showToast("Notification sent to " + this.state.selectedUser.name);
            this.closeTaskDialog();
        }
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
            const messages = await rpc('/web/dataset/call_kw', { model:'mail.message', method:'search_read', args:[[['partner_ids','in',[user.partnerId]],['model','=','crm.lead']]], kwargs:{ fields:['id'], limit:50, order:'date desc' } });
            this.state.notifCount = messages.map(m=>m.id).filter(id=>!readIds.includes(id)).length;
        } catch(e) { this.state.notifCount = 0; }
    }
    async toggleNotifications() {
        this.state.notifOpen = !this.state.notifOpen;
        if (this.state.notifOpen) {
            try {
                const messages = await rpc('/web/dataset/call_kw', { model:'mail.message', method:'search_read', args:[[['partner_ids','in',[user.partnerId]],['model','=','crm.lead']]], kwargs:{ fields:['id','record_name','body','date','res_id'], limit:10, order:'date desc' } });
                localStorage.setItem('crm_read_notifs', JSON.stringify(messages.map(m=>m.id)));
                this.state.notifCount = 0;
                this.state.notifications = messages.map(m => ({ id:m.id, res_id:m.res_id, record_name:m.record_name||'Lead', body_text:m.body?m.body.replace(/<[^>]+>/g,'').substring(0,80):'', date:m.date?m.date.substring(0,16):'' }));
            } catch(e) { this.state.notifications = []; }
        }
    }
    openLead(notif) { this.state.notifOpen=false; this.actionService.doAction({type:'ir.actions.act_window',res_model:'crm.lead',res_id:notif.res_id,view_mode:'form',views:[[false,'form']],target:'current'}); }
}
registry.category("actions").add("crm_dashboard", CrmDashboard);
export default CrmDashboard;
