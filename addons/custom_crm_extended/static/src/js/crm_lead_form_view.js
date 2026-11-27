/** @odoo-module **/

import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { listView } from "@web/views/list/list_view";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

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

    async save() {
        if (this.props.resModel === "crm.lead") {
            const assignToField = this.model.root.data.x_assign_to_id;
            const currentUserId = user.userId;
            const isAssignedToOther = assignToField && assignToField[0] && assignToField[0] !== currentUserId;

            if (isAssignedToOther && !user.isAdmin) {
                // Determine the previous controller/view where the user clicked this lead from
                const breadcrumbs = this.env.config?.breadcrumbs || [];
                const prev = breadcrumbs.length > 1 ? breadcrumbs[breadcrumbs.length - 2] : null;

                const saved = await this.model.root.save({
                    reload: false,
                    onError: this.onSaveError.bind(this),
                });
                if (saved) {
                    this.env.services.notification?.add(
                        _t("Lead was successfully assigned and transferred."),
                        { type: "success" }
                    );
                    if (prev && prev.jsId) {
                        try {
                            await this.actionService.restore(prev.jsId);
                            return;
                        } catch (e) {
                            // fallback below
                        }
                    }
                    if (window.history.length > 1) {
                        window.history.back();
                    } else {
                        this.actionService.doAction(
                            { type: "ir.actions.client", tag: "crm_dashboard" },
                            { clearBreadcrumbs: true }
                        );
                    }
                }
                return;
            }
        }
        return super.save(...arguments);
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


// Patch sol_product_many2one so line_section rows render & save multi-line (\n) natively
// via record.update({ name }) without HTMLInputElement stripping newlines.
const solField = registry.category("fields").get("sol_product_many2one");
if (solField && solField.component) {
    patch(solField.component.prototype, {
        setup() {
            super.setup(...arguments);
            const syncSection = () => {
                if (this.props.record?.data?.display_type !== "line_section") {
                    return;
                }
                const el = this.__owl__?.bdom?.el;
                if (!el) return;
                const cell = el.querySelector(".o_field_product_label_section_and_note_cell") || el;
                cell.style.setProperty("height", "auto", "important");
                cell.style.setProperty("white-space", "pre-wrap", "important");

                const val = this.props.record.data.name || "";
                const input = cell.querySelector("input.o_input");
                if (input) {
                    input.classList.add("d-none");
                    input.style.setProperty("display", "none", "important");

                    let ta = cell.querySelector("textarea.crm-section-ta");
                    if (!ta) {
                        ta = document.createElement("textarea");
                        ta.className = "o_input text-wrap border-0 w-100 fw-bolder crm-section-ta";
                        ta.placeholder = input.placeholder || "Enter a description";
                        ta.style.cssText =
                            "width:100%;resize:none;overflow:hidden;white-space:pre-wrap;min-height:21px;line-height:1.4;background:transparent;outline:none;box-shadow:none;padding:0;margin:0;";

                        const autoResize = () => {
                            ta.rows = Math.max(1, (ta.value || "").split("\n").length);
                            ta.style.height = "";
                        };

                        ta.addEventListener("input", () => {
                            autoResize();
                        });
                        ta.addEventListener("change", () => {
                            this.props.record.update({ name: ta.value });
                        });
                        ta.addEventListener("blur", () => {
                            this.props.record.update({ name: ta.value });
                        });
                        ta.addEventListener("keydown", (ev) => {
                            if (ev.key === "Enter" && !ev.ctrlKey && !ev.metaKey) {
                                ev.stopPropagation();
                            }
                        });

                        input.parentNode.insertBefore(ta, input.nextSibling);
                    }
                    if (document.activeElement !== ta && ta.value !== val) {
                        ta.value = val;
                    }
                    ta.rows = Math.max(1, (ta.value || "").split("\n").length);
                    ta.style.height = "";
                } else {
                    // Read-only display: preserve \n line breaks
                    const span = cell.querySelector("span") || cell;
                    span.style.setProperty("white-space", "pre-wrap", "important");
                    if (span.textContent !== val) {
                        span.textContent = val;
                    }
                }
            };
            onMounted(syncSection);
            onPatched(syncSection);
        },
    });
}


// Align .o_we_power_buttons on the exact same vertical line as .o-we-hint in Product Internal Notes
(function () {
    function alignPowerButtons() {
        const field = document.querySelector('.o_field_html[name="description"]');
        if (!field) return;
        const btns = field.querySelector(".o_we_power_buttons") || document.querySelector(".o_we_power_buttons");
        const hint = field.querySelector(".o-we-hint");
        if (!btns || !hint || !btns.parentElement) return;
        const overlayRect = btns.parentElement.getBoundingClientRect();
        const hintRect = hint.getBoundingClientRect();
        const btnsHeight = btns.offsetHeight || 28;
        const targetTop = Math.round(hintRect.top - overlayRect.top + (hintRect.height - btnsHeight) / 2);
        const curTop = parseFloat(btns.style.top || "0");
        if (Math.abs(curTop - targetTop) > 2) {
            btns.style.setProperty("top", targetTop + "px", "important");
        }
    }
    const obs = new MutationObserver(() => requestAnimationFrame(alignPowerButtons));
    if (document.body) {
        obs.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class"] });
    }
})();
