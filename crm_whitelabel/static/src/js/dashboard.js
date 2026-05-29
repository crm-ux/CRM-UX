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
        });

        onMounted(() => this.loadStats());
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
        const res = await rpc("/web/dataset/call_kw", {
            model: model,
            method: "read_group",
            args: [domain, [field], []],
            kwargs: {},
        });

        return res[0] ? (res[0][field] || 0) : 0;
    }

    async loadStats() {
        try {
            const [
                leads,
                qualified,
                opp,
                quotes,
                won,
                customers,
                products,
                users,
                revenue
            ] = await Promise.all([
                this._count("crm.lead", [["active","=",true],["x_stage_sequence","=",0]]),
                this._count("crm.lead", [["active","=",true],["x_stage_sequence","=",1]]),
                this._count("crm.lead", [["active","=",true],["x_stage_sequence","=",2]]),
                this._count("sale.order", [["state","in",["draft","sent"]]]),
                this._count("crm.lead", [["active","=",true],["x_stage_sequence","=",4]]),
                this._count("res.partner", [["customer_rank",">",0]]),
                this._count("product.template", [["sale_ok","=",true]]),
                this._count("res.users", [["active","=",true],["share","=",false]]),
                this._sum("sale.order", "amount_total", [["state","in",["sale","done"]]]),
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
                revenue,
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

    openLeads() { this.go(212); }
    openQuotes() { this.go({ type:"ir.actions.act_window", name:"Quotations", res_model:"sale.order", views:[[false,"list"],[false,"form"]] }); }
    openContacts() { this.go({ type:"ir.actions.act_window", name:"Customers", res_model:"res.partner", views:[[false,"list"],[false,"form"]], domain:[["customer_rank",">",0]] }); }
    openProducts() { this.go({ type:"ir.actions.act_window", name:"Products", res_model:"product.template", views:[[false,"list"],[false,"form"]] }); }
    openUsers() { this.go({ type:"ir.actions.act_window", name:"Users", res_model:"res.users", views:[[false,"list"],[false,"form"]], domain:[["share","=",false]] }); }
    openWon() { this.go({ type:"ir.actions.act_window", name:"Won Deals", res_model:"crm.lead", views:[[false,"list"],[false,"form"]], domain:[["x_stage_sequence","=",4]] }); }
    openStage(seq) { this.go({ type:"ir.actions.act_window", name:"Pipeline", res_model:"crm.lead", views:[[false,"list"],[false,"form"]], domain:[["active","=",true],["x_stage_sequence","=",seq]] }); }
    newLead() { this.go(405); }
}

registry.category("actions").add("crm_dashboard", CrmDashboard);

export default CrmDashboard;
