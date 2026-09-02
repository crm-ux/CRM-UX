/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { notificationService } from "@web/core/notifications/notification_service";

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
                                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:80vh; width:100%; text-align:center; padding:clamp(1.5rem, 4vh, 3rem); font-family:inherit; background-color:#ffffff; background-image:radial-gradient(circle at 50% 50%, rgba(254, 226, 226, 0.8) 0%, rgba(254, 202, 202, 0.4) 35%, transparent 65%), radial-gradient(circle at 50% 50%, #94a3b8 clamp(0.06rem, 0.1vw, 0.08rem), transparent clamp(0.06rem, 0.1vw, 0.08rem)); background-size:100% 100%, clamp(1.2rem, 2vw, 1.6rem) clamp(1.2rem, 2vw, 1.6rem);">
                                    <div style="font-size:clamp(2rem, 5vw, 3.5rem); font-weight:900; line-height:1; letter-spacing:0.04em; background:linear-gradient(135deg, #0284c7 0%, #38bdf8 60%, #0369a1 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:1.25rem; user-select:none; text-transform:uppercase;">
                                        404 NOT FOUND
                                    </div>
                                    <h1 style="font-size:2rem; font-weight:800; color:#0f172a; margin-bottom:0.5rem; letter-spacing:-0.03em;">
                                        Oops! Record Not Found
                                    </h1>
                                    <p style="color:#64748b; font-size:0.95rem; max-width:440px; margin-bottom:2rem; line-height:1.6;">
                                        We couldn't find the record you requested. It might have been deleted or the link is incorrect.
                                    </p>
                                    <div style="display:flex; gap:12px; align-items:center;">
                                        <button id="btn_crm_goback" style="background:#ffffff; color:#334155; border:1px solid #cbd5e1; padding:10px 22px; font-size:13.5px; font-weight:600; border-radius:8px; cursor:pointer; transition:all 0.2s; box-shadow:0 1px 2px rgba(0,0,0,0.05);">
                                            Go Back
                                        </button>
                                        <button id="btn_crm_dashboard" style="background:#0284c7; color:#ffffff; border:none; padding:10px 24px; font-size:13.5px; font-weight:600; border-radius:8px; cursor:pointer; box-shadow:0 2px 8px rgba(2,132,199,0.3); transition:all 0.2s;">
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
    },
    goDashboard() {
        this.action.doAction(435);
    }
});

patch(FormController.prototype, {
    async discard() {
        const isDirty = this.model.root.isDirty ? await this.model.root.isDirty() : false;
        const goBack = async () => {
            await this.model.root.discard();
            const breadcrumbs = this.env.config?.breadcrumbs || [];
            if (breadcrumbs.length > 1) {
                const prev = breadcrumbs[breadcrumbs.length - 2];
                if (prev && prev.jsId) {
                    this.actionService.restore(prev.jsId);
                    return;
                }
            }
            // Smart Fallbacks when opened without breadcrumbs stack
            if (this.props.resModel === "res.partner") {
                this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: "Customers",
                    res_model: "res.partner",
                    views: [[false, "list"], [false, "form"]],
                    domain: [["customer_rank", ">", 0]],
                }, { clearBreadcrumbs: true });
            } else if (this.props.resModel === "exhibition.contact") {
                this.actionService.doAction("exhibition_contacts.action_exhibition_contact", { clearBreadcrumbs: true });
            } else if (this.props.resModel === "product.template") {
                this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: "Products",
                    res_model: "product.template",
                    views: [[false, "list"], [false, "form"]],
                }, { clearBreadcrumbs: true });
            } else if (this.props.resModel === "res.users") {
                this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: "Users",
                    res_model: "res.users",
                    views: [[false, "list"], [false, "form"]],
                    domain: [["share", "=", false]],
                }, { clearBreadcrumbs: true });
            } else {
                this.actionService.doAction(435, { clearBreadcrumbs: true });
            }
        };

        if (isDirty) {
            this.dialogService.add(ConfirmationDialog, {
                title: _t("Discard changes?"),
                body: _t("The changes you made will be lost. Do you want to discard them and go back?"),
                confirmLabel: _t("Discard"),
                cancelLabel: _t("Stay Here"),
                confirm: goBack,
                cancel: () => { },
            });
            return;
        }
        await goBack();
    }
});
