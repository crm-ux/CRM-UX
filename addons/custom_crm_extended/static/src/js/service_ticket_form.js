/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

const TICKET_MODEL = "service.ticket";
const WIZARD_ACTION = "custom_crm_extended.action_service_ticket_wizard";

async function openServiceTicketWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

// 1. Intercept "New" button in List View
patch(ListController.prototype, {
    async createRecord() {
        if (
            this.model?.root?.resModel === TICKET_MODEL ||
            this.props?.resModel === TICKET_MODEL
        ) {
            await openServiceTicketWizard(this.env);
            return;
        }
        return super.createRecord(...arguments);
    },
    async openNewRecord() {
        if (
            this.model?.root?.resModel === TICKET_MODEL ||
            this.props?.resModel === TICKET_MODEL
        ) {
            await openServiceTicketWizard(this.env);
            return;
        }
        return super.openNewRecord(...arguments);
    },
});

// 2. Intercept "New" button in Detail Form View
patch(FormController.prototype, {
    async create() {
        if (
            this.props?.resModel === TICKET_MODEL ||
            this.model?.root?.resModel === TICKET_MODEL
        ) {
            const dirty = await this.model?.root?.isDirty?.();
            if (dirty) {
                const saved = await this.model.root.save({
                    onError: this.onSaveError?.bind(this),
                });
                if (!saved) {
                    return;
                }
            }
            await openServiceTicketWizard(this.env);
            return;
        }
        return super.create(...arguments);
    },
});

export class ServiceTicketFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel === TICKET_MODEL) {
            let observer = null;
            const reorderToolbar = () => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (container && breadcrumb && statusIndicator) {
                    if (breadcrumb.previousElementSibling !== statusIndicator) {
                        container.insertBefore(breadcrumb, statusIndicator.nextSibling);
                    }
                    statusIndicator.style.setProperty("margin-right", "16px", "important");
                    statusIndicator.style.setProperty("flex-grow", "0", "important");
                    statusIndicator.style.setProperty("width", "auto", "important");
                    breadcrumb.style.setProperty("margin-left", "0", "important");
                    breadcrumb.style.setProperty("flex-grow", "0", "important");
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
        if (this.props.resModel === TICKET_MODEL) {
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
