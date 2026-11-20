/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart, onMounted } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { notificationService } from "@web/core/notifications/notification_service";
import { user } from "@web/core/user";

// Centralized Interceptor: Convert Missing Record error notifications into clean Modal Popup
// Centralized In-Page 404 Screen for Missing Records across ALL models
patch(notificationService, {
    start(env) {
        const originalNotification = super.start(...arguments);
        return {
            ...originalNotification,
            add(message, options = {}) {
                const msgStr = (typeof message === "string" ? message : (message?.toString() || "")).toLowerCase();

                // Detect Missing Record error across ALL models
                if (msgStr.includes("cannot be found") ||
                    msgStr.includes("might have been deleted") ||
                    msgStr.includes("missingerror") ||
                    msgStr.includes("does not exist")) {

                    // Remove blank container and render Design 2: Enterprise Minimalist
                    setTimeout(() => {
                        const targetContainer = document.querySelector(".o_action_manager") || document.body;
                        if (targetContainer) {
                            targetContainer.innerHTML = `
                                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; min-height:100vh; width:100%; text-align:center; padding:0 clamp(1.5rem, 3vw, 2.5rem); font-family:inherit; background-color:#ffffff; background-image:radial-gradient(circle at 50% 50%, rgba(224, 242, 254, 0.6) 0%, rgba(240, 249, 255, 0.2) 20vh, transparent 50vh), radial-gradient(circle at 50% 50%, #475569 clamp(0.05rem, 0.08vw, 0.07rem), transparent clamp(0.05rem, 0.08vw, 0.07rem)); background-size:100% 100%, clamp(1.1rem, 1.8vw, 1.4rem) clamp(1.1rem, 1.8vw, 1.4rem); -webkit-mask-image:radial-gradient(circle at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0.85) 38vh, transparent 50vh); mask-image:radial-gradient(circle at 50% 50%, rgba(0,0,0,1) 0%, rgba(0,0,0,0.85) 38vh, transparent 50vh); box-sizing:border-box;">
                                    <div style="font-size:clamp(2.2rem, 5.5vw, 3.8rem); font-weight:900; line-height:1; letter-spacing:0.04em; background:linear-gradient(135deg, #0284c7 0%, #38bdf8 60%, #0369a1 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:clamp(1.2rem, 2.5vh, 1.8rem); user-select:none; text-transform:uppercase;">
                                        404 NOT FOUND
                                    </div>
                                    <h1 style="font-size:clamp(1.5rem, 3vw, 2.2rem); font-weight:800; color:#0f172a; margin:0 0 clamp(0.9rem, 2vh, 1.3rem) 0; letter-spacing:-0.03em; line-height:1.2;">
                                        Oops! Record Not Found
                                    </h1>
                                    <p style="color:#334155; font-size:clamp(0.95rem, 1.4vw, 1.05rem); font-weight:500; max-width:480px; margin:0 0 clamp(1.8rem, 3.5vh, 2.5rem) 0; line-height:1.7;">
                                        We couldn't find the record you requested. It might have been deleted or the link is incorrect.
                                    </p>
                                    <div style="display:flex; gap:clamp(0.75rem, 1.5vw, 1.25rem); align-items:center; justify-content:center; flex-wrap:wrap;">
                                        <button id="btn_crm_goback" style="background:#ffffff; color:#334155; border:2px solid #cbd5e1; padding:clamp(0.6rem, 1.2vh, 0.75rem) clamp(1.2rem, 2vw, 1.6rem); font-size:clamp(0.85rem, 1.2vw, 0.95rem); font-weight:600; border-radius:8px; cursor:pointer; transition:all 0.2s; box-shadow:0 1px 2px rgba(0,0,0,0.05);">
                                            Go Back
                                        </button>
                                        <button id="btn_crm_dashboard" style="background:#0284c7; color:#ffffff; border:none; padding:clamp(0.6rem, 1.2vh, 0.75rem) clamp(1.4rem, 2.2vw, 1.8rem); font-size:clamp(0.85rem, 1.2vw, 0.95rem); font-weight:600; border-radius:8px; cursor:pointer; box-shadow:0 2px 8px rgba(2,132,199,0.3); transition:all 0.2s;">
                                            Dashboard
                                        </button>
                                    </div>
                                </div>
                            `;

                            // Bind Button Actions
                            document.getElementById("btn_crm_goback")?.addEventListener("click", () => {
                                if (window.history.length > 1) {
                                    window.history.back();
                                } else {
                                    window.location.replace("/app/action-435");
                                }
                            });

                            document.getElementById("btn_crm_dashboard")?.addEventListener("click", () => {
                                window.location.replace("/app/action-435");
                            });
                        }
                    }, 50);

                    return () => { }; // Suppress ugly red toast
                }

                return originalNotification.add(message, options);
            }
        };
    }
});

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);
        this.action = useService("action");
        this.orm = useService("orm");
        window.__crm_action_service = this.action;
        window.__crm_control_panel = this;
        this.empFilterState = useState({ accessibleEmployees: [] });

        onWillStart(async () => {
            try {
                const emps = await rpc("/web/dataset/call_kw", {
                    model: "res.users",
                    method: "get_accessible_employees",
                    args: [],
                    kwargs: {},
                });
                if (Array.isArray(emps)) {
                    this.empFilterState.accessibleEmployees = emps;
                }
            } catch (e) {
                this.empFilterState.accessibleEmployees = [];
            }
        });
    },
    goDashboard() {
        this.action.doAction(435);
    },
    openAssignWorkWizard() {
        this.action.doAction("custom_crm_extended.action_crm_task_assign_wizard", {
            onClose: async () => {
                const currentController = this.action.currentController;
                if (currentController?.model?.load) {
                    await currentController.model.load();
                } else if (currentController?.model?.root?.load) {
                    await currentController.model.root.load();
                }
            },
        });
    },
    async createNewLead() {
        const wizardId = await this.orm.create("crm.lead.wizard", [{ step: 1 }]);
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "crm.lead.wizard",
            res_id: wizardId[0],
            views: [[false, "form"]],
            target: "new",
            name: "Lead Creation",
        });
    },

    get canShowTaskCalendarNewButton() {
        const resModel = this.env.searchModel?.resModel || this.action?.currentController?.props?.resModel;
        const viewType = this.env.config?.viewType || this.action?.currentController?.props?.type;
        return resModel === "crm.task.management" && viewType === "calendar";
    },

    get canShowDashboardButton() {
        // Do NOT show Dashboard button inside modal popup dialogs!
        const ctx = this.env.searchModel?.context || {};
        if (ctx.is_unscheduled_modal || this.env.config?.target === "new") {
            return false;
        }
        return true;
    },

    get canShowVoucherConfigButton() {
        // Strictly restricted to System Administrator only - never show to dept managers, managers, global managers, or employees
        const viewAsUid = sessionStorage.getItem("crm_view_as_uid") || sessionStorage.getItem("crm_view_as_user_id");
        const isAdmin = !viewAsUid && (Boolean(user.isAdmin) || user.userId === 1);
        if (!isAdmin) {
            return false;
        }
        const resModel = this.env.searchModel?.resModel || this.action?.currentController?.props?.resModel;
        const viewType = this.env.config?.viewType || this.action?.currentController?.props?.type;
        const isVoucherModel = resModel === "service.ticket.voucher.batch" || resModel === "service.ticket.voucher.line";
        return isVoucherModel && viewType === "list";
    },

    openVoucherConfiguration() {
        this.action.doAction("custom_crm_extended.action_expense_setting");
    },

    get unscheduledTasksCount() {
        return window.__crm_unscheduled_count || 0;
    },

    async toggleUnscheduledTasksModal() {
        // Open Unscheduled tasks in standard view target with full Action menus, Delete, Export and Search
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Unscheduled Tasks",
            res_model: "crm.task.management",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            view_mode: "list,form",
            domain: [["date_deadline", "=", false], ["state", "=", "pending"]],
            context: {
                search_default_pending: 1,
                default_state: "pending",
            },
            target: "current",
        });
    },

    get isTotalPipelineView() {
        const ctx = this.env.searchModel?.context || {};
        const viewType = this.env.config?.viewType;
        return ctx.from_total_pipeline === true && viewType === "list";
    },

    get currentStageFilter() {
        const ctx = this.env.searchModel?.context || {};
        return ctx.default_stage_filter_val || "all";
    },

    onStageFilterChange(ev) {
        const val = ev.target.value;
        const ctx = this.env.searchModel?.context || {};
        const selectedText = ev.target.options[ev.target.selectedIndex].text;
        const currentEmp = ctx.filter_employee_user_id || "all";

        // Map quote sequence numbers to sale.order x_quote_stage values
        const quoteStageMap = {
            "30": "draft",
            "35": "sent",
            "40": "negotiation",
            "50": "order_expected",
            "90": "won",
        };

        if (quoteStageMap[val]) {
            // From Quote onwards -> open sale.order directly!
            const quoteStage = quoteStageMap[val];
            const cancelFilter = quoteStage === "won" ? [["state", "!=", "cancel"]] : [["state", "not in", ["sale", "cancel"]], ["x_quote_stage", "not in", ["won", "lost"]]];
            const empDomain = currentEmp !== "all" ? [["user_id", "=", parseInt(currentEmp)]] : [];

            this.action.doAction({
                type: "ir.actions.act_window",
                name: selectedText + " Quotations",
                res_model: "sale.order",
                views: [[false, "list"], [false, "form"]],
                domain: [["x_quote_stage", "=", quoteStage], ...cancelFilter, ...empDomain],
                context: {
                    ...ctx,
                    from_total_pipeline: true,
                    default_stage_filter_val: val,
                    filter_employee_user_id: currentEmp,
                },
            }, { clearBreadcrumbs: true });
        } else {
            // Early stages (All, Lead, Contacted, Tech Disc, Qualified, Opportunity) -> open crm.lead
            const stageDomain = val === "all" ? [] : [["x_stage_sequence", "=", parseInt(val)]];
            const empDomain = currentEmp !== "all" ? ["|", ["user_id", "=", parseInt(currentEmp)], ["x_assign_to_id", "=", parseInt(currentEmp)]] : [];

            this.action.doAction({
                type: "ir.actions.act_window",
                name: val === "all" ? "All Pipeline Leads" : selectedText + " Leads",
                res_model: "crm.lead",
                views: [[false, "list"], [false, "form"]],
                domain: [["active", "=", true], ...stageDomain, ...empDomain],
                context: {
                    ...ctx,
                    from_total_pipeline: true,
                    default_stage_filter_val: val,
                    filter_employee_user_id: currentEmp,
                },
            }, { clearBreadcrumbs: true });
        }
    },


    get showEmployeeFilter() {
        const viewType = this.env.config?.viewType;
        if (viewType !== "list" && viewType !== "kanban") return false;
        const resModel = this.env.searchModel?.resModel;
        const supportedModels = ['crm.lead', 'sale.order', 'equipment.master', 'service.ticket', 'amc.contract'];
        if (!supportedModels.includes(resModel)) return false;
        return (this.empFilterState?.accessibleEmployees || []).length > 1;
    },

    get accessibleEmployees() {
        return this.empFilterState?.accessibleEmployees || [];
    },

    get currentEmployeeFilter() {
        const ctx = this.env.searchModel?.context || {};
        return ctx.filter_employee_user_id || "all";
    },

    onEmployeeFilterChange(ev) {
        const val = ev.target.value;
        const searchModel = this.env.searchModel;
        if (!searchModel) return;

        const resModel = searchModel.resModel;
        const userField = resModel === 'service.ticket' ? 'engineer_id' : (resModel === 'amc.contract' ? 'create_uid' : 'user_id');

        // When a specific user is selected, filter strictly by currently assigned person / owner
        // NEVER include create_uid for leads/quotes: created-by does NOT mean assigned owner!
        let domain = [];
        if (val !== "all") {
            const uid = parseInt(val);
            if (resModel === 'crm.lead') {
                // When assigned, only the assigned employee sees the lead.
                // If not assigned yet, the creator/salesperson sees it.
                domain = [
                    '|',
                    '&', ['x_assign_to_id', '!=', false], ['x_assign_to_id', '=', uid],
                    '&', ['x_assign_to_id', '=', false], ['user_id', '=', uid]
                ];
            } else if (resModel === 'sale.order') {
                domain = [['user_id', '=', uid]];
            } else if (userField && userField !== 'create_uid') {
                domain = [[userField, '=', uid]];
            } else {
                domain = [['create_uid', '=', uid]];
            }
        }

        const actionService = this.action;
        const currentController = actionService.currentController;
        const currentAction = currentController?.action;
        if (currentAction) {
            // Find the underlying raw action XML/DB domain or clean base domain
            if (!window._crm_clean_base_domains) {
                window._crm_clean_base_domains = {};
            }
            const actionKey = currentAction.id || currentAction.xml_id || currentAction.name || resModel;
            if (!window._crm_clean_base_domains[actionKey]) {
                // Strip any existing employee filter domain fragments
                const raw = Array.isArray(currentAction.domain) ? currentAction.domain : [];
                window._crm_clean_base_domains[actionKey] = raw.filter(item => {
                    if (Array.isArray(item)) {
                        return !['user_id', 'x_assign_to_id', 'create_uid', 'engineer_id'].includes(item[0]);
                    }
                    return true;
                });
            }

            const baseDomain = [...window._crm_clean_base_domains[actionKey]];
            const newDomain = [...baseDomain, ...domain];
            const existingContext = currentAction.context || {};

            actionService.doAction({
                ...currentAction,
                domain: newDomain,
                context: {
                    ...existingContext,
                    filter_employee_user_id: val,
                }
            }, { clearBreadcrumbs: false });
        }
    },

    get pagerProps() {
        const rawProps = this.props.pagerProps;
        const controller = this.action?.currentController;
        const resModel = this.env.searchModel?.resModel || controller?.props?.resModel;
        const currentResId = controller?.model?.root?.resId || controller?.props?.resId;
        const isFormView = this.env.config?.viewType === "form" || controller?.props?.type === "form";

        // Multi-record view (List / Kanban): continuously cache active record IDs
        if (resModel && rawProps && rawProps.total > 1) {
            try {
                let ids = [];
                const root = controller?.model?.root;
                if (root?.records?.length > 0) {
                    ids = root.records.map((r) => r.resId).filter(Boolean);
                } else if (root?.groups?.length > 0) {
                    for (const grp of root.groups) {
                        if (grp.list?.records?.length > 0) {
                            ids.push(...grp.list.records.map((r) => r.resId).filter(Boolean));
                        }
                    }
                }
                if (ids.length > 1) {
                    sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(ids));
                    window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                    window.__crm_cached_res_ids[resModel] = ids;
                }
            } catch (e) {}
            return rawProps;
        }

        // Form View: restore full record count on refresh so pager shows 1/16 instead of 1/1
        if (isFormView && resModel && currentResId) {
            window.__crm_current_form_model = resModel;
            let activeIds = null;
            try {
                const stored = sessionStorage.getItem("crm_active_res_ids_" + resModel);
                if (stored) {
                    const parsed = JSON.parse(stored);
                    if (Array.isArray(parsed) && parsed.length > 1 && parsed.includes(currentResId)) {
                        activeIds = parsed;
                    }
                }
            } catch (e) {}

            if (!activeIds && window.__crm_cached_res_ids?.[resModel]?.includes(currentResId)) {
                activeIds = window.__crm_cached_res_ids[resModel];
            }

            // If not found in cache (e.g. after hard reload), fetch IDs via ORM in background and re-render ControlPanel
            if (!activeIds && this.orm && !window.__crm_fetching_ids?.[resModel]) {
                window.__crm_fetching_ids = window.__crm_fetching_ids || {};
                window.__crm_fetching_ids[resModel] = true;
                const domain = controller?.props?.domain || [];
                this.orm.search(resModel, domain, { limit: 1000 }).then((searchRes) => {
                    window.__crm_fetching_ids[resModel] = false;
                    if (Array.isArray(searchRes) && searchRes.length > 1 && searchRes.includes(currentResId)) {
                        sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(searchRes));
                        window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                        window.__crm_cached_res_ids[resModel] = searchRes;
                        if (controller?.model?.root) {
                            try { controller.model.root.resIds = searchRes; } catch (e) {}
                        }
                        this.render();
                    }
                }).catch(() => {
                    window.__crm_fetching_ids[resModel] = false;
                });
            }

            if (activeIds && activeIds.length > 1) {
                const currentIndex = activeIds.indexOf(currentResId);
                const offset = currentIndex >= 0 ? currentIndex : 0;

                if (controller?.model?.root) {
                    try {
                        controller.model.root.resIds = activeIds;
                    } catch (e) {}
                }

                return {
                    offset: offset,
                    limit: 1,
                    total: activeIds.length,
                    onUpdate: async (newOffset) => {
                        const targetId = activeIds[newOffset];
                        if (!targetId) return;
                        if (controller?.model?.root?.switchRecord) {
                            await controller.model.root.switchRecord(targetId);
                        } else if (controller?.model?.load) {
                            await controller.model.load({ resId: targetId });
                        }
                        this.render();
                    },
                };
            }
        }

        return rawProps;
    }
});

// ── Universal Navigation Helper to Return to Respective List/Pipeline Views ──
function navigateBackFromForm(resModel, actionService) {
    if (!actionService) return;
    if (resModel === "sale.order") {
        actionService.doAction("sale.action_quotations_with_onboarding", { clearBreadcrumbs: true });
    } else if (resModel === "crm.lead") {
        actionService.doAction("crm.crm_lead_action_pipeline", { clearBreadcrumbs: true });
    } else if (resModel === "service.ticket.voucher.batch") {
        actionService.doAction("custom_crm_extended.action_service_ticket_voucher_batch", { clearBreadcrumbs: true });
    } else if (resModel === "service.ticket") {
        actionService.doAction("custom_crm_extended.action_service_ticket", { clearBreadcrumbs: true });
    } else if (resModel === "equipment.master") {
        actionService.doAction("custom_crm_extended.action_equipment_master", { clearBreadcrumbs: true });
    } else if (resModel === "amc.contract") {
        actionService.doAction("custom_crm_extended.action_amc_contract", { clearBreadcrumbs: true });
    } else if (resModel === "crm.task.management") {
        actionService.doAction("custom_crm_extended.action_crm_task_management", { clearBreadcrumbs: true });
    } else if (resModel === "exhibition.contact") {
        actionService.doAction("exhibition_contacts.action_exhibition_contact", { clearBreadcrumbs: true });
    } else if (resModel === "res.partner") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Customers",
            res_model: "res.partner",
            views: [[false, "list"], [false, "form"]],
            domain: [["is_company", "=", true]],
        }, { clearBreadcrumbs: true });
    } else if (resModel === "product.template") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Products",
            res_model: "product.template",
            views: [[false, "list"], [false, "form"]],
        }, { clearBreadcrumbs: true });
    } else if (resModel === "res.users") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Users",
            res_model: "res.users",
            views: [[false, "list"], [false, "form"]],
            domain: [["share", "=", false]],
        }, { clearBreadcrumbs: true });
    } else if (resModel === "hr.job") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Roles & Groups",
            res_model: "hr.job",
            views: [[false, "list"], [false, "form"]],
            domain: [],
            context: { active_test: false },
        }, { clearBreadcrumbs: true });
    } else if (resModel) {
        actionService.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    } else {
        actionService.doAction(435, { clearBreadcrumbs: true });
    }
}

// ── Maintain Record IDs in SessionStorage for Pager Persistence Across Refresh ──
patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        const saveListIds = () => {
            try {
                const resModel = this.model?.root?.resModel || this.props?.resModel;
                const records = this.model?.root?.records;
                if (resModel && records && records.length > 0) {
                    const ids = records.map((r) => r.resId).filter(Boolean);
                    if (ids.length > 0) {
                        sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(ids));
                        window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                        window.__crm_cached_res_ids[resModel] = ids;
                    }
                }
            } catch (e) {}
        };
        onMounted(() => {
            saveListIds();
        });
    },
    async openRecord(record) {
        try {
            const resModel = this.model?.root?.resModel || this.props?.resModel;
            const records = this.model?.root?.records;
            if (resModel && records && records.length > 0) {
                const ids = records.map((r) => r.resId).filter(Boolean);
                if (ids.length > 0) {
                    sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(ids));
                    window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                    window.__crm_cached_res_ids[resModel] = ids;
                }
            }
        } catch (e) {}
        return super.openRecord ? super.openRecord(...arguments) : undefined;
    },
});

patch(KanbanController.prototype, {
    async openRecord(record) {
        try {
            const resModel = this.model?.root?.resModel || this.props?.resModel;
            let ids = [];
            const root = this.model?.root;
            if (root?.records?.length > 0) {
                ids = root.records.map((r) => r.resId).filter(Boolean);
            } else if (root?.groups?.length > 0) {
                for (const grp of root.groups) {
                    if (grp.list?.records?.length > 0) {
                        ids.push(...grp.list.records.map((r) => r.resId).filter(Boolean));
                    }
                }
            }
            if (resModel && ids.length > 0) {
                sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(ids));
                window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                window.__crm_cached_res_ids[resModel] = ids;
            }
        } catch (e) {}
        return super.openRecord ? super.openRecord(...arguments) : undefined;
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.actionService = this.env?.services?.action || this.action;
        const resModel = this.props.resModel;
        const currentResId = this.props.resId;

        // Restore resIds on refresh so pager shows full record count (e.g. 1/16 instead of 1/1)
        if (resModel && currentResId) {
            onWillStart(async () => {
                let restoredIds = null;
                try {
                    const stored = sessionStorage.getItem("crm_active_res_ids_" + resModel);
                    if (stored) {
                        const parsed = JSON.parse(stored);
                        if (Array.isArray(parsed) && parsed.length > 1 && parsed.includes(currentResId)) {
                            restoredIds = parsed;
                        }
                    }
                } catch (e) {}

                if (!restoredIds && this.model?.orm) {
                    try {
                        const domain = this.props.domain || [];
                        const searchRes = await this.model.orm.search(resModel, domain, { limit: 1000 });
                        if (Array.isArray(searchRes) && searchRes.length > 1 && searchRes.includes(currentResId)) {
                            restoredIds = searchRes;
                            sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(restoredIds));
                            window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                            window.__crm_cached_res_ids[resModel] = restoredIds;
                        }
                    } catch (err) {}
                }

                if (restoredIds && restoredIds.length > 1 && this.model?.root) {
                    try {
                        this.model.root.resIds = restoredIds;
                    } catch (e) {}
                }
            });
        }
    },

    async discard() {
        const actionService = this.actionService || this.action || this.env?.services?.action;

        // If inside a modal/dialog/wizard, simply close the dialog without redirecting to Dashboard
        if (this.props.close || this.env.config?.target === "new" || this.env.dialogData) {
            if (this.model?.root?.discard) await this.model.root.discard();
            if (typeof this.props.close === "function") {
                this.props.close();
            } else if (typeof this.env.dialogData?.close === "function") {
                this.env.dialogData.close();
            }
            return;
        }

        const isDirty = this.model?.root?.isDirty ? await this.model.root.isDirty() : false;
        const goBack = async () => {
            if (this.model?.root?.discard) await this.model.root.discard();
            const breadcrumbs = this.env.config?.breadcrumbs || [];
            if (breadcrumbs.length > 1) {
                const prev = breadcrumbs[breadcrumbs.length - 2];
                if (prev && prev.jsId && actionService?.restore) {
                    actionService.restore(prev.jsId);
                    return;
                }
            }
            // Fallback when opened without breadcrumbs stack (e.g. after page refresh)
            const resModel = this.props.resModel;
            navigateBackFromForm(resModel, actionService);
        };

        if (isDirty) {
            this.dialogService.add(ConfirmationDialog, {
                title: _t("Cancel changes?"),
                body: _t("The changes you made will be lost. Do you want to cancel and go back?"),
                confirmLabel: _t("Cancel"),
                cancelLabel: _t("Stay Here"),
                confirm: goBack,
                cancel: () => { },
            });
            return;
        }
        await goBack();
    }
});

// Auto-dismiss floating popovers/menus when scrolling the page/form
if (typeof window !== "undefined") {
    const handleScrollClose = (ev) => {
        try {
            // Never dismiss if any modal, dialog or wizard is currently active/open
            if (document.querySelector(".modal.show, .o_dialog, .o_technical_modal")) {
                return;
            }

            const el = (ev && ev.target instanceof Element) ? ev.target : null;
            if (el && typeof el.closest === "function") {
                if (
                    el.closest(".o_select_menu_menu") ||
                    el.closest(".o_field_selection_menu") ||
                    el.closest(".o-autocomplete--dropdown-menu") ||
                    el.closest(".ui-autocomplete") ||
                    el.closest(".dropdown-menu") ||
                    el.closest(".o_datetime_picker")
                ) {
                    return;
                }
            }

            // Close open select menus and dropdowns by clicking their active toggler
            const openTogglers = document.querySelectorAll(
                '.o_select_menu_toggler[aria-expanded="true"], ' +
                '.dropdown-toggle[aria-expanded="true"], ' +
                '[aria-expanded="true"]'
            );
            if (openTogglers.length > 0) {
                openTogglers.forEach(t => {
                    try { t.click(); } catch (e) {}
                });
            } else {
                // If an untracked popover is open, trigger click on body element (never document)
                const openPopovers = document.querySelectorAll(".o_select_menu_menu, .o_field_selection_menu, .o_popover");
                if (openPopovers.length > 0 && document.body) {
                    try { document.body.click(); } catch (e) {}
                }
            }
        } catch (err) {
            // Silently ignore
        }
    };

    window.addEventListener("scroll", handleScrollClose, true);
    window.addEventListener("wheel", handleScrollClose, { capture: true, passive: true });
    window.addEventListener("touchmove", handleScrollClose, { capture: true, passive: true });

    // Handle Cross (Cancel) button clicks on refreshed Form Views when breadcrumbs are empty
    document.addEventListener("click", async (ev) => {
        const cancelBtn = ev.target.closest(".o_form_button_cancel, .o_form_status_indicator_buttons .fa-times");
        if (!cancelBtn) return;
        if (cancelBtn.closest(".modal, .o_dialog")) return;

        const actionService = window.__crm_action_service;
        const controller = actionService?.currentController;
        const resModel = window.__crm_current_form_model || controller?.props?.resModel;

        const breadcrumbs = window.__crm_control_panel?.env?.config?.breadcrumbs || [];
        if (breadcrumbs.length <= 1) {
            ev.preventDefault();
            ev.stopPropagation();
            if (controller?.model?.root?.discard) {
                try { await controller.model.root.discard(); } catch (e) {}
            }
            navigateBackFromForm(resModel, actionService);
        }
    }, true);
}
