/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { notificationService } from "@web/core/notifications/notification_service";

// Centralized Interceptor: Convert Missing Record error notifications into clean Modal Popup
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
                    const safeExit = () => {
                        // If path has a model like /app/res.partner/895 -> extract res.partner
                        const path = window.location.pathname || "";
                        const match = path.match(/\/app\/([a-zA-Z0-9._]+)\//);
                        const model = match ? match[1] : null;

                        if (model) {
                            env.services.action.doAction({
                                type: "ir.actions.act_window",
                                res_model: model,
                                views: [[false, "list"], [false, "form"]],
                            }, { clearBreadcrumbs: true });
                        } else {
                            env.services.action.doAction(435, { clearBreadcrumbs: true });
                        }
                    };

                    env.services.dialog.add(AlertDialog, {
                        title: _t("Record Not Found"),
                        body: _t("The requested record does not exist or has been deleted."),
                        confirmLabel: _t("OK"),
                        confirm: safeExit,
                    }, {
                        onClose: safeExit,
                    });

                    return () => { }; // Suppress standard red toast notification
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
