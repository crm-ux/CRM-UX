/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { listView } from "@web/views/list/list_view";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

const WIZARD_ACTION = "custom_crm_extended.action_crm_lead_wizard";

async function openLeadWizard(env, ctx) {
    const additionalContext = {};
    if (ctx && ctx.default_x_lead_priority) {
        additionalContext.default_x_lead_priority = ctx.default_x_lead_priority;
    }
    await env.services.action.doAction(WIZARD_ACTION, { additionalContext });
}

export class CrmLeadFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel === "crm.lead") {
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

            const reorderTabs = () => {
                const productTabLink = document.querySelector('a[name="x_product_lines"]');
                const productTab = productTabLink?.parentElement;
                const navTabs = document.querySelector('.nav-tabs');
                if (productTab && navTabs) {
                    if (navTabs.firstElementChild !== productTab) {
                        navTabs.insertBefore(productTab, navTabs.firstChild);
                    }
                    if (!productTabLink.classList.contains('active')) {
                        productTabLink.click();
                        productTabLink.dispatchEvent(new Event('click', { bubbles: true }));
                    }
                }
            };


            onMounted(() => {
                reorderToolbar();
                reorderTabs();
                const panel = document.querySelector(".o_control_panel_breadcrumbs");
                if (panel) {
                    observer = new MutationObserver(() => reorderToolbar());
                    reorderTabs();
                    observer.observe(panel, { childList: true, subtree: true });
                }
            });
            onWillUnmount(() => {
                if (observer) observer.disconnect();
            });
        }
    }

    async create() {
        if (this.props.resModel === "crm.lead") {
            const dirty = await this.model.root.isDirty();
            if (dirty) {
                const saved = await this.model.root.save({
                    onError: this.onSaveError.bind(this),
                });
                if (!saved) {
                    return;
                }
            }
            await openLeadWizard(this.env, this.props.context);
            return;
        }
        return super.create(...arguments);
    }

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
            this.actionService.doAction(
                { type: "ir.actions.client", tag: "crm_dashboard" },
                { clearBreadcrumbs: true }
            );
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
}

export class CrmLeadListController extends ListController {
    async createRecord() {
        if (this.props.resModel === "crm.lead") {
            await openLeadWizard(this.env, this.props.context);
            return;
        }
        return super.createRecord(...arguments);
    }

    async openNewRecord() {
        if (this.props.resModel === "crm.lead") {
            await openLeadWizard(this.env, this.props.context);
            return;
        }
        return super.openNewRecord(...arguments);
    }
}

export class CrmLeadKanbanController extends KanbanController {
    async createRecord() {
        if (this.props.resModel === "crm.lead") {
            await openLeadWizard(this.env, this.props.context);
            return;
        }
        return super.createRecord(...arguments);
    }

    async openNewRecord() {
        if (this.props.resModel === "crm.lead") {
            await openLeadWizard(this.env, this.props.context);
            return;
        }
        return super.openNewRecord(...arguments);
    }
}

registry.category("views").add("crm_lead_form", {
    ...formView,
    Controller: CrmLeadFormController,
});

registry.category("views").add("crm_lead_list", {
    ...listView,
    Controller: CrmLeadListController,
});

registry.category("views").add("crm_lead_kanban", {
    ...kanbanView,
    Controller: CrmLeadKanbanController,
});
