/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

// Centralized Handler for ALL Models: Default & Custom Entities
function missingRecordErrorHandler(env, error) {
    const errorName = error?.data?.name || "";
    const errorMsg = error?.message || error?.data?.message || "";

    // Detect any MissingRecord / Non-existent ID error globally
    if (errorName === "odoo.exceptions.MissingError" ||
        errorMsg.includes("MissingError") ||
        errorMsg.includes("cannot be found") ||
        errorMsg.includes("does not exist")) {

        env.services.dialog.add(ConfirmationDialog, {
            title: _t("Record Not Found"),
            body: _t("The requested record does not exist or may have been deleted."),
            confirmLabel: _t("OK"),
            confirm: () => {
                if (window.history.length > 1) {
                    window.history.back();
                } else {
                    env.services.action.doAction(435, { clearBreadcrumbs: true });
                }
            },
            cancel: () => { },
        });
        return true; // Stop unhandled exception from leaving a blank white page
    }
}

registry.category("error_handlers").add("missing_record_handler", missingRecordErrorHandler);

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
