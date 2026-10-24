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
                if (container) {
                    container.style.setProperty("display", "flex", "important");
                }
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (statusIndicator) {
                    statusIndicator.style.setProperty("order", "1", "important");
                    statusIndicator.style.setProperty("margin-right", "16px", "important");
                    statusIndicator.style.setProperty("flex-grow", "0", "important");
                }
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                if (breadcrumb) {
                    breadcrumb.style.setProperty("order", "2", "important");
                    breadcrumb.style.setProperty("margin-left", "0", "important");
                    breadcrumb.style.setProperty("flex-grow", "0", "important");
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
                    try {
                        await this.actionService.restore(prev.jsId);
                        return;
                    } catch (restErr) {
                        console.warn("Could not restore previous controller, falling back:", restErr);
                    }
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

    async openRecord(record) {
        if (this.props.resModel === "crm.lead") {
            const leadId = record.resId;
            const orm = this.env.services.orm;
            const action = this.env.services.action;

            // Check stage sequence of the clicked lead
            const leadData = await orm.read("crm.lead", [leadId], ["stage_id"]);
            const stageId = leadData && leadData[0] && leadData[0].stage_id ? leadData[0].stage_id[0] : false;

            if (stageId) {
                const stages = await orm.read("crm.stage", [stageId], ["sequence"]);
                const seq = stages && stages[0] ? stages[0].sequence : 0;

                // If sequence is 30 or above (Quotes, Sent, Negotiation, Order Expected, Won)
                if (seq >= 30) {
                    const quotes = await orm.searchRead(
                        "sale.order",
                        [["opportunity_id", "=", leadId]],
                        ["id"],
                        { order: "id desc", limit: 1 }
                    );
                    if (quotes && quotes.length) {
                        return action.doAction({
                            type: "ir.actions.act_window",
                            name: "Quotation",
                            res_model: "sale.order",
                            res_id: quotes[0].id,
                            views: [[false, "form"]],
                        });
                    }
                }
            }
        }
        return super.openRecord(...arguments);
    }

    get actionMenuItems() {
        const menuItems = super.actionMenuItems;
        const count = this.model?.root?.selection?.length || 0;
        if (menuItems && menuItems.action) {
            if (count > 1) {
                // Hide Duplicate option when more than one record is selected
                menuItems.action = menuItems.action.filter(
                    (item) => item.key !== "duplicate" && item.description !== "Duplicate"
                );
            } else {
                for (const item of menuItems.action) {
                    if (item.key === "duplicate" || item.description === "Duplicate") {
                        item.callback = () => this.actionDuplicateQuote();
                    }
                }
            }
        }
        return menuItems;
    }

    async actionDuplicateQuote() {
        let selectedResIds = [];
        if (this.model?.root?.selection?.length) {
            selectedResIds = this.model.root.selection.map((r) => r.resId);
        } else if (typeof this.getSelectedResIds === "function") {
            selectedResIds = await this.getSelectedResIds();
        }
        if (selectedResIds && selectedResIds.length > 0) {
            const leadId = selectedResIds[0];
            const orm = this.env.services.orm;
            const action = this.env.services.action;

            // Check if this lead has a quotation
            const quotes = await orm.searchRead(
                "sale.order",
                [["opportunity_id", "=", leadId]],
                ["id"],
                { order: "id desc", limit: 1 }
            );

            if (quotes && quotes.length > 0) {
                return action.doAction("custom_crm_extended.action_sale_order_duplicate_wizard", {
                    additionalContext: {
                        default_order_id: quotes[0].id,
                    },
                });
            } else {
                // If lead has no quotation, duplicate the lead and open it
                const newLeadId = await orm.call("crm.lead", "copy", [leadId]);
                return action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "crm.lead",
                    res_id: newLeadId,
                    views: [[false, "form"]],
                    target: "current",
                });
            }
        }
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
