/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

export class ServiceTicketFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel === "service.ticket") {
            let observer = null;
            const reorderToolbar = () => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (container && breadcrumb && statusIndicator) {
                    if (breadcrumb.previousElementSibling !== statusIndicator) {
                        container.insertBefore(breadcrumb, statusIndicator.nextSibling);
                    }
                }
            };

            onMounted(() => {
                reorderToolbar();
                const panel = document.querySelector(".o_control_panel_breadcrumbs");
                if (panel) {
                    observer = new MutationObserver(() => reorderToolbar());
                    observer.observe(panel, { childList: true });
                }
            });

            onWillUnmount(() => {
                if (observer) observer.disconnect();
            });
        }
    }

    async discard() {
        if (this.props.resModel === "service.ticket") {
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
                this.actionService.doAction("custom_crm_extended.action_service_ticket", { clearBreadcrumbs: true });
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
            return;
        }
        return super.discard(...arguments);
    }
}

export const serviceTicketFormView = {
    ...formView,
    Controller: ServiceTicketFormController,
};

registry.category("views").add("service_ticket_form", serviceTicketFormView);
