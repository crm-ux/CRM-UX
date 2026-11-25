/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
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
        try {
            sessionStorage.setItem("crm_from_total_pipeline", "true");
            sessionStorage.setItem("crm_last_stage_filter_val", val);
            sessionStorage.setItem("crm_last_stage_filter_name", selectedText);
            sessionStorage.setItem("crm_last_employee_filter_val", currentEmp);
        } catch (e) { }

        // All stages (including Quotes, Sent, Negotiation, Order Expected, Won) maintain crm.lead list view
        let stageDomain = [];
        if (val !== "all") {
            const seq = parseInt(val, 10);
            stageDomain = [["x_stage_sequence", "=", seq]];
            if (seq !== 90) {
                stageDomain.push(["x_stage_sequence", "!=", 90]);
            }
        }
        const empDomain = currentEmp !== "all" ? ["|", ["user_id", "=", parseInt(currentEmp)], ["x_assign_to_id", "=", parseInt(currentEmp)]] : [];

        this.action.doAction({
            type: "ir.actions.act_window",
            name: val === "all" ? "All Pipeline Leads" : selectedText + " Leads & Deals",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ...stageDomain, ...empDomain],
            context: {
                ...ctx,
                from_total_pipeline: true,
                default_stage_filter_val: val,
                filter_employee_user_id: currentEmp,
                is_quote_stage: val !== "all" && parseInt(val, 10) >= 30,
            },
        }, { clearBreadcrumbs: true });
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
        try {
            sessionStorage.setItem("crm_last_employee_filter_val", val);
        } catch (e) { }
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
    }
});

// Safely override ControlPanel.prototype.pagerProps getter and setter using Object.defineProperty
const origPagerPropsDesc = Object.getOwnPropertyDescriptor(ControlPanel.prototype, "pagerProps") || {
    get() { return this.props.pagerProps; }
};

Object.defineProperty(ControlPanel.prototype, "pagerProps", {
    get() {
        const rawProps = this._customPagerProps || (origPagerPropsDesc.get ? origPagerPropsDesc.get.call(this) : this.props.pagerProps);
        const controller = this.action?.currentController;

        // Resilient resolution of model and record id (including immediately on F5 refresh from URL hash)
        let resModel = this.env.searchModel?.resModel || controller?.props?.resModel || window.__crm_current_form_model;
        if (!resModel) {
            try {
                const m = window.location.hash.match(/[#&]model=([^&]+)/);
                if (m) resModel = decodeURIComponent(m[1]);
            } catch (e) { }
        }

        let currentResId = controller?.model?.root?.resId || controller?.props?.resId;
        if (!currentResId) {
            try {
                const m = window.location.hash.match(/[#&]id=(\d+)/);
                if (m) currentResId = parseInt(m[1], 10);
            } catch (e) { }
        }

        let isFormView = this.env.config?.viewType === "form" || controller?.props?.type === "form";
        if (!isFormView && (window.location.hash.includes("view_type=form") || window.location.hash.includes("id="))) {
            isFormView = true;
        }

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

                    const ctx = this.env.searchModel?.context || {};
                    const currentStageVal = ctx.default_stage_filter_val || sessionStorage.getItem("crm_last_stage_filter_val") || "all";

                    // Cache specific stage IDs vs Total Pipeline IDs
                    if (this.isTotalPipelineView || ctx.from_total_pipeline) {
                        sessionStorage.setItem("crm_from_total_pipeline", "true");
                        if (currentStageVal === "all") {
                            sessionStorage.setItem("crm_active_pipeline_ids", JSON.stringify(ids));
                        } else {
                            sessionStorage.setItem("crm_stage_ids_" + currentStageVal, JSON.stringify(ids));
                        }
                    }
                }
            } catch (e) { }
            return rawProps;
        }

        // Form View: restore stage-accurate record count immediately so pager shows the real stage count
        if (isFormView && resModel) {
            window.__crm_current_form_model = resModel;
            let activeIds = null;
            const fromTotalPipeline = sessionStorage.getItem("crm_from_total_pipeline") === "true";

            // Resolve stage for the current record across all 10 stages
            let recordStage = null;
            if (currentResId) {
                recordStage = sessionStorage.getItem("crm_record_stage_" + currentResId);
            }
            if (!recordStage && controller?.model?.root?.data) {
                const rData = controller.model.root.data;
                if (rData.x_stage_sequence !== undefined && rData.x_stage_sequence !== false) {
                    recordStage = String(rData.x_stage_sequence);
                } else if (rData.x_quote_stage) {
                    const quoteMap = { draft: "30", sent: "35", negotiation: "40", order_expected: "50", won: "90" };
                    recordStage = quoteMap[rData.x_quote_stage] || null;
                }
            }
            if (!recordStage) {
                const storedStage = sessionStorage.getItem("crm_last_stage_filter_val");
                if (storedStage && storedStage !== "all") {
                    recordStage = storedStage;
                }
            }

            try {
                // 1. If record belongs to any of the 10 stages, strictly use that stage's exact IDs
                if (recordStage && recordStage !== "all") {
                    const stageStored = sessionStorage.getItem("crm_stage_ids_" + recordStage);
                    if (stageStored) {
                        const parsedStage = JSON.parse(stageStored);
                        if (Array.isArray(parsedStage) && parsedStage.length > 0) {
                            activeIds = parsedStage.map(Number).filter(Boolean);
                        }
                    }

                    // If not in cache, fetch exact stage IDs via ORM
                    if (!activeIds && this.orm && !window.__crm_fetching_stage_ids?.[recordStage]) {
                        window.__crm_fetching_stage_ids = window.__crm_fetching_stage_ids || {};
                        window.__crm_fetching_stage_ids[recordStage] = true;

                        const quoteStageMap = { "30": "draft", "35": "sent", "40": "negotiation", "50": "order_expected", "90": "won" };
                        const isQuote = quoteStageMap[recordStage];
                        const stageModel = isQuote ? "sale.order" : "crm.lead";
                        const stageDomain = isQuote
                            ? [["x_quote_stage", "=", isQuote], (isQuote === "won" ? ["state", "!=", "cancel"] : ["state", "not in", ["sale", "cancel"]])]
                            : [["active", "=", true], ["x_stage_sequence", "=", parseInt(recordStage)]];

                        this.orm.search(stageModel, stageDomain, { limit: 1000 }).then((searchRes) => {
                            window.__crm_fetching_stage_ids[recordStage] = false;
                            if (Array.isArray(searchRes) && searchRes.length > 0) {
                                sessionStorage.setItem("crm_stage_ids_" + recordStage, JSON.stringify(searchRes));
                                if (controller?.model?.root) {
                                    try { controller.model.root.resIds = searchRes; } catch (e) { }
                                }
                                this.render();
                            }
                        }).catch(() => {
                            window.__crm_fetching_stage_ids[recordStage] = false;
                        });
                    }
                }

                // 2. Fallback to model-specific cached IDs only if not a specific stage
                if (!activeIds && !recordStage) {
                    const stored = sessionStorage.getItem("crm_active_res_ids_" + resModel);
                    if (stored) {
                        const parsed = JSON.parse(stored);
                        if (Array.isArray(parsed) && parsed.length > 1) {
                            const parsedNums = parsed.map(Number).filter(Boolean);
                            if (!currentResId || parsedNums.includes(Number(currentResId))) {
                                activeIds = parsedNums;
                            } else {
                                activeIds = [Number(currentResId), ...parsedNums];
                            }
                        }
                    }
                }
            } catch (e) { }

            if (!activeIds && !recordStage && window.__crm_cached_res_ids?.[resModel]?.length > 1) {
                activeIds = window.__crm_cached_res_ids[resModel];
            }

            // If not found in cache (e.g. after hard reload), fetch IDs via ORM in background and re-render ControlPanel
            if (!activeIds && this.orm && !window.__crm_fetching_ids?.[resModel]) {
                window.__crm_fetching_ids = window.__crm_fetching_ids || {};
                window.__crm_fetching_ids[resModel] = true;
                const domain = controller?.props?.domain || [];
                this.orm.search(resModel, domain, { limit: 1000 }).then((searchRes) => {
                    window.__crm_fetching_ids[resModel] = false;
                    if (Array.isArray(searchRes) && searchRes.length > 1) {
                        sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(searchRes));
                        window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                        window.__crm_cached_res_ids[resModel] = searchRes;
                        if (controller?.model?.root) {
                            try { controller.model.root.resIds = searchRes; } catch (e) { }
                        }
                        this.render();
                    }
                }).catch(() => {
                    window.__crm_fetching_ids[resModel] = false;
                });
            }

            if (activeIds && activeIds.length > 1) {
                const currentIndex = currentResId ? activeIds.indexOf(Number(currentResId)) : 0;
                const offset = currentIndex >= 0 ? currentIndex : 0;

                if (controller?.model?.root) {
                    try {
                        controller.model.root.resIds = activeIds;
                    } catch (e) { }
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
    },
    set(val) {
        this._customPagerProps = val;
    },
    configurable: true,
    enumerable: true,
});

// ── Universal Navigation Helper to Return to Respective List/Pipeline Views ──
function navigateBackFromForm(resModel, actionService) {
    if (!actionService) actionService = window.__crm_action_service;
    if (!actionService) return;

    const stageNamesMap = {
        "all": "All Pipeline",
        "0": "Lead",
        "5": "Contacted",
        "7": "Tech. Discussion",
        "10": "Qualified",
        "20": "Opportunity",
        "30": "Quotes",
        "35": "Sent",
        "40": "Negotiation",
        "50": "Order Expected",
        "90": "Won"
    };

    // Check if this record originated from Total Pipeline or a Pipeline Stage
    const fromTotalPipeline = sessionStorage.getItem("crm_from_total_pipeline") === "true";
    let lastStageVal = "all";
    let lastStageName = "All Pipeline";
    let lastEmp = "all";
    try {
        lastStageVal = sessionStorage.getItem("crm_last_stage_filter_val") || "all";
        lastStageName = sessionStorage.getItem("crm_last_stage_filter_name") || stageNamesMap[lastStageVal] || "All Pipeline";
        lastEmp = sessionStorage.getItem("crm_last_employee_filter_val") || "all";
    } catch (e) { }

    // Check if the current record was tagged with its origin stage
    const controller = actionService.currentController;
    const curResId = controller?.model?.root?.resId || controller?.props?.resId;
    if (curResId) {
        const recStage = sessionStorage.getItem("crm_record_stage_" + curResId);
        if (recStage) {
            lastStageVal = recStage;
            lastStageName = stageNamesMap[recStage] || lastStageName;
        }
    }

    // Returning from crm.lead or sale.order: Maintain crm.lead list view
    if (resModel === "crm.lead" || (resModel === "sale.order" && fromTotalPipeline)) {
        const stageTitle = stageNamesMap[lastStageVal] || lastStageName || "Pipeline";
        let stageDomain = [];
        if (lastStageVal && lastStageVal !== "all") {
            const seq = parseInt(lastStageVal, 10);
            stageDomain = [["x_stage_sequence", "=", seq]];
            if (seq !== 90) {
                stageDomain.push(["x_stage_sequence", "!=", 90]);
            }
        }
        const empDomain = (lastEmp && lastEmp !== "all") ? ["|", ["user_id", "=", parseInt(lastEmp)], ["x_assign_to_id", "=", parseInt(lastEmp)]] : [];

        actionService.doAction({
            type: "ir.actions.act_window",
            name: lastStageVal === "all" ? "All Pipeline Leads" : stageTitle + " Leads & Deals",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ...stageDomain, ...empDomain],
            context: {
                from_total_pipeline: true,
                default_stage_filter_val: lastStageVal || "all",
                filter_employee_user_id: lastEmp || "all",
                is_quote_stage: lastStageVal !== "all" && parseInt(lastStageVal, 10) >= 30,
            },
        }, { clearBreadcrumbs: true });
        return;
    }

    try { sessionStorage.removeItem("crm_from_total_pipeline"); } catch (e) { }

    if (resModel === "sale.order") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Quotations",
            res_model: "sale.order",
            views: [[false, "list"], [false, "form"]],
        }, { clearBreadcrumbs: true });
    } else if (resModel === "crm.lead") {
        const controller = actionService.currentController;
        const rootData = controller?.model?.root?.data || {};
        const stageSeq = rootData.x_stage_sequence;
        let lastStageVal = null;
        let lastStageName = null;
        let lastEmp = null;
        try {
            lastStageVal = sessionStorage.getItem("crm_last_stage_filter_val");
            lastStageName = sessionStorage.getItem("crm_last_stage_filter_name");
            lastEmp = sessionStorage.getItem("crm_last_employee_filter_val");
        } catch (e) { }

        let filterVal = lastStageVal;
        if ((!filterVal || filterVal === "all") && stageSeq !== undefined && stageSeq !== false) {
            filterVal = stageSeq.toString();
        }

        const stageDomain = (filterVal && filterVal !== "all") ? [["x_stage_sequence", "=", parseInt(filterVal)]] : [];
        const empDomain = (lastEmp && lastEmp !== "all") ? ["|", ["user_id", "=", parseInt(lastEmp)], ["x_assign_to_id", "=", parseInt(lastEmp)]] : [];

        actionService.doAction({
            type: "ir.actions.act_window",
            name: (lastStageName || "Pipeline") + " Leads",
            res_model: "crm.lead",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ...stageDomain, ...empDomain],
            context: {
                from_total_pipeline: true,
                default_stage_filter_val: filterVal || "all",
                filter_employee_user_id: lastEmp || "all",
            },
        }, { clearBreadcrumbs: true });
    } else if (resModel === "service.ticket.voucher.batch") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Voucher Submissions",
            res_model: "service.ticket.voucher.batch",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    } else if (resModel === "service.ticket") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Service Tickets",
            res_model: "service.ticket",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    } else if (resModel === "equipment.master") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Equipment Master",
            res_model: "equipment.master",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    } else if (resModel === "amc.contract") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "AMC Contracts",
            res_model: "amc.contract",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    } else if (resModel === "crm.task.management") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Task Management",
            res_model: "crm.task.management",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    } else if (resModel === "exhibition.contact") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Exhibition Contacts",
            res_model: "exhibition.contact",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
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
    } else if (resModel === "hr.employee") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Employees",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    } else if (resModel === "hr.department") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Departments",
            res_model: "hr.department",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    } else if (resModel === "hr.employee.category") {
        actionService.doAction({
            type: "ir.actions.act_window",
            name: "Employee Tags",
            res_model: "hr.employee.category",
            views: [[false, "list"], [false, "form"]],
            target: "current",
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
        const stageNamesMap = {
            "all": "All Pipeline",
            "0": "Lead",
            "5": "Contacted",
            "7": "Tech. Discussion",
            "10": "Qualified",
            "20": "Opportunity",
            "30": "Quotes",
            "35": "Sent",
            "40": "Negotiation",
            "50": "Order Expected",
            "90": "Won"
        };

        const detectCurrentStage = () => {
            const domain = this.props.domain || this.env.searchModel?.domain || [];
            let detectedStage = null;
            if (Array.isArray(domain)) {
                for (const cond of domain) {
                    if (Array.isArray(cond)) {
                        if (cond[0] === "x_stage_sequence" && cond[1] === "=") {
                            detectedStage = String(cond[2]);
                            break;
                        }
                        if (cond[0] === "x_quote_stage" && cond[1] === "=") {
                            const revMap = { draft: "30", sent: "35", negotiation: "40", order_expected: "50", won: "90" };
                            detectedStage = revMap[cond[2]] || "30";
                            break;
                        }
                    }
                }
            }
            return detectedStage;
        };

        const saveListIds = () => {
            try {
                const resModel = this.model?.root?.resModel || this.props?.resModel;
                const records = this.model?.root?.records;
                const ctx = this.props.context || this.env.searchModel?.context || {};
                const detected = detectCurrentStage();

                if (detected !== null) {
                    sessionStorage.setItem("crm_from_total_pipeline", "true");
                    sessionStorage.setItem("crm_last_stage_filter_val", detected);
                    sessionStorage.setItem("crm_last_stage_filter_name", stageNamesMap[detected] || "Pipeline");
                } else if (ctx.from_total_pipeline) {
                    sessionStorage.setItem("crm_from_total_pipeline", "true");
                    if (ctx.default_stage_filter_val) {
                        sessionStorage.setItem("crm_last_stage_filter_val", ctx.default_stage_filter_val);
                        sessionStorage.setItem("crm_last_stage_filter_name", stageNamesMap[ctx.default_stage_filter_val] || "Pipeline");
                    } else {
                        sessionStorage.setItem("crm_last_stage_filter_val", "all");
                        sessionStorage.setItem("crm_last_stage_filter_name", "All Pipeline");
                    }
                    if (ctx.filter_employee_user_id) {
                        sessionStorage.setItem("crm_last_employee_filter_val", ctx.filter_employee_user_id);
                    }
                } else if (resModel !== "crm.lead" && resModel !== "sale.order") {
                    sessionStorage.removeItem("crm_from_total_pipeline");
                }

                if (resModel && records && records.length > 0) {
                    const ids = records.map((r) => r.resId).filter(Boolean);
                    if (ids.length > 0) {
                        sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(ids));
                        window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                        window.__crm_cached_res_ids[resModel] = ids;
                        const effectiveStage = detected || ctx.default_stage_filter_val || "all";
                        if (effectiveStage !== "all") {
                            sessionStorage.setItem("crm_stage_ids_" + effectiveStage, JSON.stringify(ids));
                        } else {
                            sessionStorage.setItem("crm_active_pipeline_ids", JSON.stringify(ids));
                        }
                    }
                }
            } catch (e) { }
        };
        onMounted(() => {
            saveListIds();
        });
        onWillUnmount(() => {
            saveListIds();
        });
    },
    async openRecord(record) {
        try {
            const resModel = this.model?.root?.resModel || this.props?.resModel;
            const records = this.model?.root?.records;
            const ctx = this.props.context || this.env.searchModel?.context || {};
            const domain = this.props.domain || this.env.searchModel?.domain || [];
            let detected = null;
            if (Array.isArray(domain)) {
                for (const cond of domain) {
                    if (Array.isArray(cond)) {
                        if (cond[0] === "x_stage_sequence" && cond[1] === "=") {
                            detected = String(cond[2]);
                            break;
                        }
                        if (cond[0] === "x_quote_stage" && cond[1] === "=") {
                            const revMap = { draft: "30", sent: "35", negotiation: "40", order_expected: "50", won: "90" };
                            detected = revMap[cond[2]] || "30";
                            break;
                        }
                    }
                }
            }

            const stageNamesMap = {
                "all": "All Pipeline",
                "0": "Lead",
                "5": "Contacted",
                "7": "Tech. Discussion",
                "10": "Qualified",
                "20": "Opportunity",
                "30": "Quotes",
                "35": "Sent",
                "40": "Negotiation",
                "50": "Order Expected",
                "90": "Won"
            };

            const targetStage = detected || ctx.default_stage_filter_val || (record?.data?.x_stage_sequence !== undefined ? String(record.data.x_stage_sequence) : "all");
            sessionStorage.setItem("crm_from_total_pipeline", "true");
            sessionStorage.setItem("crm_last_stage_filter_val", targetStage);
            sessionStorage.setItem("crm_last_stage_filter_name", stageNamesMap[targetStage] || "Pipeline");
            if (record?.resId) {
                sessionStorage.setItem("crm_record_stage_" + record.resId, targetStage);
            }

            if (resModel && records && records.length > 0) {
                const ids = records.map((r) => r.resId).filter(Boolean);
                if (ids.length > 0) {
                    sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(ids));
                    window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                    window.__crm_cached_res_ids[resModel] = ids;
                    if (targetStage !== "all") {
                        sessionStorage.setItem("crm_stage_ids_" + targetStage, JSON.stringify(ids));
                    } else {
                        sessionStorage.setItem("crm_active_pipeline_ids", JSON.stringify(ids));
                    }
                }
            }

            // For the 5 Quote Stages (Quotes:30, Sent:35, Negotiation:40, Order Expected:50, Won:90), open record directly as Quotation (sale.order)
            if (resModel === "crm.lead" && record?.resId) {
                const leadId = record.resId;
                const orm = this.env?.services?.orm;
                const action = this.actionService || this.action || this.env?.services?.action || window.__crm_action_service;

                let seq = 0;
                if (record.data?.x_stage_sequence !== undefined && record.data.x_stage_sequence !== false) {
                    seq = parseInt(record.data.x_stage_sequence, 10);
                } else if (targetStage && targetStage !== "all") {
                    seq = parseInt(targetStage, 10);
                }

                if ((!seq || isNaN(seq)) && orm) {
                    try {
                        const lRes = await orm.read("crm.lead", [leadId], ["x_stage_sequence"]);
                        if (lRes && lRes[0] && lRes[0].x_stage_sequence) {
                            seq = parseInt(lRes[0].x_stage_sequence, 10);
                        }
                    } catch (e) { }
                }

                const isQuoteStage = Boolean(ctx.is_quote_stage || (seq && seq >= 30));

                if (isQuoteStage && orm && action) {
                    const quotes = await orm.searchRead(
                        "sale.order",
                        [["opportunity_id", "=", leadId]],
                        ["id"],
                        { order: "id desc", limit: 1 }
                    );
                    if (quotes && quotes.length > 0) {
                        const stageVal = String(seq || 30);
                        sessionStorage.setItem("crm_from_total_pipeline", "true");
                        sessionStorage.setItem("crm_last_stage_filter_val", stageVal);
                        sessionStorage.setItem("crm_record_stage_" + quotes[0].id, stageVal);
                        return action.doAction({
                            type: "ir.actions.act_window",
                            name: "Quotation",
                            res_model: "sale.order",
                            res_id: quotes[0].id,
                            views: [[false, "form"]],
                            context: {
                                ...ctx,
                                from_total_pipeline: true,
                                default_stage_filter_val: stageVal,
                            },
                        });
                    }
                }
            }
        } catch (e) { }
        return super.openRecord ? super.openRecord(...arguments) : undefined;
    },
});

patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        const saveKanbanIds = () => {
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
            } catch (e) { }
        };
        onMounted(saveKanbanIds);
        onWillUnmount(saveKanbanIds);
    },
    async openRecord(record) {
        try {
            const resModel = this.model?.root?.resModel || this.props?.resModel;
            const ctx = this.props?.context || this.env?.searchModel?.context || {};
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

            // For the 5 Quote Stages (Quotes:30, Sent:35, Negotiation:40, Order Expected:50, Won:90), open record directly as Quotation (sale.order)
            if (resModel === "crm.lead" && record?.resId) {
                const leadId = record.resId;
                const orm = this.env?.services?.orm;
                const action = this.actionService || this.action || this.env?.services?.action || window.__crm_action_service;

                let seq = 0;
                if (record.data?.x_stage_sequence !== undefined && record.data.x_stage_sequence !== false) {
                    seq = parseInt(record.data.x_stage_sequence, 10);
                }

                if ((!seq || isNaN(seq)) && orm) {
                    try {
                        const lRes = await orm.read("crm.lead", [leadId], ["x_stage_sequence"]);
                        if (lRes && lRes[0] && lRes[0].x_stage_sequence) {
                            seq = parseInt(lRes[0].x_stage_sequence, 10);
                        }
                    } catch (e) { }
                }

                const isQuoteStage = Boolean(ctx.is_quote_stage || (seq && seq >= 30));

                if (isQuoteStage && orm && action) {
                    const quotes = await orm.searchRead(
                        "sale.order",
                        [["opportunity_id", "=", leadId]],
                        ["id"],
                        { order: "id desc", limit: 1 }
                    );
                    if (quotes && quotes.length > 0) {
                        const stageVal = String(seq || 30);
                        sessionStorage.setItem("crm_from_total_pipeline", "true");
                        sessionStorage.setItem("crm_last_stage_filter_val", stageVal);
                        sessionStorage.setItem("crm_record_stage_" + quotes[0].id, stageVal);
                        return action.doAction({
                            type: "ir.actions.act_window",
                            name: "Quotation",
                            res_model: "sale.order",
                            res_id: quotes[0].id,
                            views: [[false, "form"]],
                            context: {
                                ...ctx,
                                from_total_pipeline: true,
                                default_stage_filter_val: stageVal,
                            },
                        });
                    }
                }
            }
        } catch (e) { }
        return super.openRecord ? super.openRecord(...arguments) : undefined;
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.actionService = this.env?.services?.action || this.action;
        const orm = this.env?.services?.orm;
        const resModel = this.props.resModel;
        const currentResId = this.props.resId;

        // Restore resIds on refresh so pager shows full record count immediately on initial render
        if (resModel && currentResId) {
            onWillStart(async () => {
                let restoredIds = null;
                const fromTotalPipeline = sessionStorage.getItem("crm_from_total_pipeline") === "true";
                const lastStageVal = sessionStorage.getItem("crm_last_stage_filter_val") || "all";
                try {
                    if (fromTotalPipeline && lastStageVal !== "all") {
                        const stageStored = sessionStorage.getItem("crm_stage_ids_" + lastStageVal);
                        if (stageStored) {
                            const parsedStage = JSON.parse(stageStored);
                            if (Array.isArray(parsedStage) && parsedStage.length > 1 && parsedStage.includes(currentResId)) {
                                restoredIds = parsedStage;
                            }
                        }
                    }
                    if (!restoredIds && fromTotalPipeline && lastStageVal === "all") {
                        const pipeStored = sessionStorage.getItem("crm_active_pipeline_ids");
                        if (pipeStored) {
                            const parsedPipe = JSON.parse(pipeStored);
                            if (Array.isArray(parsedPipe) && parsedPipe.length > 1 && parsedPipe.includes(currentResId)) {
                                restoredIds = parsedPipe;
                            }
                        }
                    }
                    if (!restoredIds) {
                        const stored = sessionStorage.getItem("crm_active_res_ids_" + resModel);
                        if (stored) {
                            const parsed = JSON.parse(stored);
                            if (Array.isArray(parsed) && parsed.length > 1 && parsed.includes(currentResId)) {
                                restoredIds = parsed;
                            }
                        }
                    }
                } catch (e) { }

                if (!restoredIds && orm) {
                    try {
                        const domain = this.props.domain || [];
                        const searchRes = await orm.search(resModel, domain, { limit: 1000 });
                        if (Array.isArray(searchRes) && searchRes.length > 1 && searchRes.includes(currentResId)) {
                            restoredIds = searchRes;
                            sessionStorage.setItem("crm_active_res_ids_" + resModel, JSON.stringify(restoredIds));
                        }
                    } catch (err) { }
                }

                if (restoredIds && restoredIds.length > 1) {
                    window.__crm_cached_res_ids = window.__crm_cached_res_ids || {};
                    window.__crm_cached_res_ids[resModel] = restoredIds;
                    if (this.model?.root) {
                        try {
                            this.model.root.resIds = restoredIds;
                        } catch (e) { }
                    }
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
                    try { t.click(); } catch (e) { }
                });
            } else {
                // If an untracked popover is open, trigger click on body element (never document)
                const openPopovers = document.querySelectorAll(".o_select_menu_menu, .o_field_selection_menu, .o_popover");
                if (openPopovers.length > 0 && document.body) {
                    try { document.body.click(); } catch (e) { }
                }
            }
        } catch (err) {
            // Silently ignore
        }
    };

    window.addEventListener("scroll", handleScrollClose, true);
    window.addEventListener("wheel", handleScrollClose, { capture: true, passive: true });
    window.addEventListener("touchmove", handleScrollClose, { capture: true, passive: true });

    // Handle Cross (Cancel) button clicks on Form Views to reliably navigate back
    document.addEventListener("click", async (ev) => {
        const cancelBtn = ev.target.closest(".o_form_button_cancel, .o_form_status_indicator_buttons .fa-times");
        if (!cancelBtn) return;
        if (cancelBtn.closest(".modal, .o_dialog")) return;

        ev.preventDefault();
        ev.stopPropagation();

        const actionService = window.__crm_action_service;
        const controller = actionService?.currentController;
        let resModel = window.__crm_current_form_model || controller?.props?.resModel;
        if (!resModel) {
            try {
                resModel = new URLSearchParams(window.location.hash.substring(1)).get("model");
            } catch (e) { }
        }

        if (controller?.model?.root?.discard) {
            try { await controller.model.root.discard(); } catch (e) { }
        }

        navigateBackFromForm(resModel, actionService);
    }, true);
}

if (typeof window !== "undefined") {
    window.navigateBackFromForm = navigateBackFromForm;

    // Remove text 'New', 'Save', 'Discard' from DOM inside control panel and render clean icons
    const cleanNewButtonsGlobally = () => {
        const btns = document.querySelectorAll(
            ".o_control_panel_main_buttons .o_form_button_create, " +
            ".o_control_panel_main_buttons .o_list_button_add, " +
            ".o_control_panel_main_buttons button.btn-outline-primary"
        );
        btns.forEach((btn) => {
            let foundText = false;
            Array.from(btn.childNodes).forEach((node) => {
                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                    node.textContent = "";
                    foundText = true;
                }
            });
            if (foundText || !btn.querySelector("i.fa-plus")) {
                btn.innerHTML = '<i class="fa fa-plus" style="font-size: 0.95rem !important; color: #ffffff !important; line-height: 1 !important; display: inline-block !important;"></i>';
            }
        });

        // Editable list Save button (Floppy disk icon)
        const saveBtns = document.querySelectorAll(
            ".o_control_panel_main_buttons .o_list_button_save, " +
            ".o_list_button_save"
        );
        saveBtns.forEach((btn) => {
            let foundText = false;
            Array.from(btn.childNodes).forEach((node) => {
                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                    node.textContent = "";
                    foundText = true;
                }
            });
            if (foundText || !btn.querySelector("i.fa-floppy-o")) {
                btn.innerHTML = '<i class="fa fa-floppy-o" style="font-size: 0.95rem !important; color: #ffffff !important; line-height: 1 !important; display: inline-block !important;"></i>';
            }
        });

        // Editable list Discard button (Times / Cross icon)
        const discardBtns = document.querySelectorAll(
            ".o_control_panel_main_buttons .o_list_button_discard, " +
            ".o_list_button_discard"
        );
        discardBtns.forEach((btn) => {
            let foundText = false;
            Array.from(btn.childNodes).forEach((node) => {
                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                    node.textContent = "";
                    foundText = true;
                }
            });
            if (foundText || !btn.querySelector("i.fa-times")) {
                btn.innerHTML = '<i class="fa fa-times" style="font-size: 0.95rem !important; color: #334155 !important; line-height: 1 !important; display: inline-block !important;"></i>';
            }
        });

        // Dedicated Import Screen Handling (Screen 1: Upload, Screen 2: Mapping)
        const isImportPage = !!document.querySelector("input[name='ufile'], .o_import_file, .o_import_panel, table.o_import_table, [name='sheet']") ||
            (document.querySelector(".o_last_breadcrumb_item")?.textContent?.toLowerCase().includes("import") ?? false);

        if (isImportPage) {
            document.body.classList.add("crm_import_active");

            // Check if on Mapping Screen (file is loaded and columns/options are shown)
            const isMappingScreen = !!document.querySelector(".o_import_panel, table.o_import_table, [name='sheet'], .o_import_data_side");

            const controlPanelBtns = document.querySelector(".o_control_panel_main_buttons");
            if (controlPanelBtns) {
                if (!isMappingScreen) {
                    // SCREEN 1: INITIAL UPLOAD SCREEN
                    // Button 1: Upload Data File (inside .o_file_input)
                    const uploadBtn = controlPanelBtns.querySelector(".o_file_input button, button.o_import_file");
                    if (uploadBtn) {
                        Array.from(uploadBtn.childNodes).forEach((n) => {
                            if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) n.textContent = "";
                        });
                        uploadBtn.setAttribute("title", "Upload Data File");
                        if (!uploadBtn.querySelector("i.fa-cloud-upload")) {
                            uploadBtn.innerHTML = '<i class="fa fa-cloud-upload" style="font-size: 0.95rem !important; color: #ffffff !important; line-height: 1 !important; display: inline-block !important;"></i>';
                        }
                    }

                    // Button 2: Cancel button
                    const cancelBtns = Array.from(controlPanelBtns.querySelectorAll("button")).filter((b) => {
                        const t = b.textContent.trim().toLowerCase();
                        return t === "cancel" || b.title === "Cancel" || b.classList.contains("o_import_cancel");
                    });
                    cancelBtns.forEach((btn, idx) => {
                        if (idx === 0) {
                            Array.from(btn.childNodes).forEach((n) => {
                                if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) n.textContent = "";
                            });
                            btn.setAttribute("title", "Cancel");
                            if (!btn.querySelector("i.fa-times")) {
                                btn.innerHTML = '<i class="fa fa-times" style="font-size: 0.95rem !important; color: #475569 !important; line-height: 1 !important; display: inline-block !important;"></i>';
                            }
                            btn.style.setProperty("display", "inline-flex", "important");
                        } else {
                            btn.style.setProperty("display", "none", "important");
                        }
                    });
                } else {
                    // SCREEN 2: MAPPING SCREEN
                    // 1. Hide the redundant .o_file_input trigger completely
                    const fileInput = controlPanelBtns.querySelector(".o_file_input");
                    if (fileInput) {
                        fileInput.style.setProperty("display", "none", "important");
                    }

                    // 2. Identify Test, Import, and Cancel buttons
                    const allBtns = Array.from(controlPanelBtns.querySelectorAll("button"));

                    // Test Button: primary button or text 'test'
                    const testBtn = allBtns.find((b) => {
                        const t = b.textContent.trim().toLowerCase();
                        return t === "test" || b.title === "Test" || b.classList.contains("btn-primary") || b.classList.contains("o_import_test");
                    });
                    if (testBtn) {
                        Array.from(testBtn.childNodes).forEach((n) => {
                            if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) n.textContent = "";
                        });
                        testBtn.setAttribute("title", "Test");
                        if (!testBtn.querySelector("i.fa-check")) {
                            testBtn.innerHTML = '<i class="fa fa-check" style="font-size: 0.95rem !important; color: #ffffff !important; line-height: 1 !important; display: inline-block !important;"></i>';
                        }
                    }

                    // Import Button: secondary button with text 'import' or o_import_import
                    const importBtn = allBtns.find((b) => {
                        const t = b.textContent.trim().toLowerCase();
                        return (t === "import" || b.title === "Import" || b.classList.contains("o_import_import")) && b !== testBtn;
                    });
                    if (importBtn) {
                        Array.from(importBtn.childNodes).forEach((n) => {
                            if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) n.textContent = "";
                        });
                        importBtn.setAttribute("title", "Import");
                        if (!importBtn.querySelector("i.fa-download")) {
                            importBtn.innerHTML = '<i class="fa fa-download" style="font-size: 0.95rem !important; color: #ffffff !important; line-height: 1 !important; display: inline-block !important;"></i>';
                        }
                    }

                    // Cancel Button: strictly ONE button
                    const cancelBtns = allBtns.filter((b) => {
                        const t = b.textContent.trim().toLowerCase();
                        return (t === "cancel" || b.title === "Cancel" || b.classList.contains("o_import_cancel")) && b !== testBtn && b !== importBtn;
                    });
                    cancelBtns.forEach((btn, idx) => {
                        if (idx === 0) {
                            Array.from(btn.childNodes).forEach((n) => {
                                if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) n.textContent = "";
                            });
                            btn.setAttribute("title", "Cancel");
                            if (!btn.querySelector("i.fa-times")) {
                                btn.innerHTML = '<i class="fa fa-times" style="font-size: 0.95rem !important; color: #475569 !important; line-height: 1 !important; display: inline-block !important;"></i>';
                            }
                            btn.style.setProperty("display", "inline-flex", "important");
                        } else {
                            btn.style.setProperty("display", "none", "important");
                        }
                    });
                }
            }

            // Hide Help & FAQ & Template section on both screens
            const helpTargets = document.querySelectorAll(
                "a[href*='faq'], a[href*='FAQ'], .o_import_template_link, [class*='import_template']"
            );
            helpTargets.forEach((el) => {
                const parent = el.closest(".mb-3, .mb-4, .mt-3, .mt-4, .text-muted, div:not(.o_action_manager):not(.o_content):not(.o_control_panel)") || el;
                parent.style.setProperty("display", "none", "important");
            });
            document.querySelectorAll("h5, p, span").forEach((el) => {
                const text = el.textContent?.trim().toLowerCase() || "";
                if (text === "help" || text.startsWith("need help?")) {
                    const parent = el.closest(".mb-3, .mb-4, .mt-3, .mt-4, div:not(.o_action_manager):not(.o_content):not(.o_control_panel)") || el;
                    parent.style.setProperty("display", "none", "important");
                }
            });
        } else {
            document.body.classList.remove("crm_import_active");
        }
    };

    const navObserver = new MutationObserver(() => {
        cleanNewButtonsGlobally();
    });

    if (document.body) {
        navObserver.observe(document.body, { childList: true, subtree: true });
        cleanNewButtonsGlobally();
    } else {
        document.addEventListener("DOMContentLoaded", () => {
            navObserver.observe(document.body, { childList: true, subtree: true });
            cleanNewButtonsGlobally();
        });
    }
}
