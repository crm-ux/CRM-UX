/** @odoo-module **/
import { onMounted, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";

const SALE_ORDER_MODEL = "sale.order";

patch(FormController.prototype, {
    setup() {
        super.setup();
        if (this.props.resModel === SALE_ORDER_MODEL) {
            let observer = null;
            const reorderToolbar = () => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const mainButtons = document.querySelector(".o_control_panel_breadcrumbs > .o_control_panel_main_buttons");
                if (!container || !breadcrumb || !mainButtons) {
                    return;
                }
                const statusBarButtons = Array.from(document.querySelectorAll(".o_form_statusbar button"));
                const saveBtn = statusBarButtons.find((b) => b.textContent.trim() === "Save");
                const cancelBtn = statusBarButtons.find((b) => b.textContent.trim() === "Cancel");

                if (cancelBtn && !cancelBtn.dataset.customBound) {
                    cancelBtn.dataset.customBound = "true";
                    cancelBtn.addEventListener("click", (ev) => {
                        ev.preventDefault();
                        ev.stopPropagation();
                        this.discard();
                    });
                }
                if (saveBtn && !saveBtn.dataset.customBound) {
                    saveBtn.dataset.customBound = "true";
                    saveBtn.addEventListener("click", (ev) => {
                        ev.preventDefault();
                        ev.stopPropagation();
                        this.saveButtonClicked();
                    });
                }

                if (saveBtn && saveBtn.parentElement !== container) {
                    container.insertBefore(saveBtn, mainButtons.nextSibling);
                }
                if (cancelBtn && cancelBtn.parentElement !== container) {
                    container.insertBefore(cancelBtn, breadcrumb);
                }
                if (breadcrumb.previousElementSibling !== cancelBtn && breadcrumb.previousElementSibling !== saveBtn) {
                    const ref = cancelBtn || saveBtn;
                    if (ref) container.insertBefore(breadcrumb, ref.nextSibling);
                }
            };
            onMounted(() => {
                reorderToolbar();
                const panel = document.querySelector(".o_control_panel_breadcrumbs");
                if (panel) {
                    observer = new MutationObserver(() => reorderToolbar());
                    observer.observe(panel, { childList: true, subtree: true });
                }
            });
            onWillUnmount(() => {
                if (observer) observer.disconnect();
            });
        }
    },

    async saveButtonClicked() {
        if (this.props.resModel === SALE_ORDER_MODEL) {
            const saved = await super.saveButtonClicked(...arguments);
            if (saved) {
                this.env.services.notification.add("Record saved successfully.", {
                    type: "success",
                });
            }
            return saved;
        }
        return super.saveButtonClicked(...arguments);
    },

    async discard() {
        if (this.props.resModel === SALE_ORDER_MODEL) {
            await this.model.root.discard();
            const breadcrumbs = this.env.config?.breadcrumbs || [];
            if (breadcrumbs.length > 1) {
                const prev = breadcrumbs[breadcrumbs.length - 2];
                if (prev && prev.jsId) {
                    this.actionService.restore(prev.jsId);
                    return;
                }
            }
            try {
                await this.actionService.doAction(
                    {
                        type: "ir.actions.act_window",
                        name: "Quotations",
                        res_model: "sale.order",
                        views: [[false, "list"], [false, "form"]],
                    },
                    { clearBreadcrumbs: true }
                );
            } catch (e) {
                console.error("Cancel redirect failed:", e);
            }
            return;
        }
        return super.discard(...arguments);
    },

    async duplicateRecord() {
        if (this.props.resModel === SALE_ORDER_MODEL) {
            const resId = this.model.root.resId;
            if (resId) {
                // Trigger our custom duplicate wizard
                return this.actionService.doAction("custom_crm_extended.action_sale_order_duplicate_wizard", {
                    additionalContext: {
                        default_order_id: resId,
                        default_partner_id: this.model.root.data.partner_id ? this.model.root.data.partner_id[0] : false,
                        default_contact_person_id: this.model.root.data.x_contact_person_id ? this.model.root.data.x_contact_person_id[0] : false,
                        default_user_id: this.model.root.data.user_id ? this.model.root.data.user_id[0] : false,
                    },
                });
            }
        }
        return super.duplicateRecord(...arguments);
    },
});

// Also intercept Duplicate action from List / Tree View for sale.order and crm.lead
patch(ListController.prototype, {
    async duplicateRecords() {
        const actionService = this.actionService || this.env.services.action;
        const ormService = this.orm || this.env.services.orm;

        if (this.props.resModel === SALE_ORDER_MODEL) {
            const selectedResIds = await this.getSelectedResIds();
            if (selectedResIds && selectedResIds.length > 0) {
                const targetId = selectedResIds[0];
                return actionService.doAction("custom_crm_extended.action_sale_order_duplicate_wizard", {
                    additionalContext: {
                        default_order_id: targetId,
                    },
                });
            }
        } else if (this.props.resModel === "crm.lead") {
            const selectedResIds = await this.getSelectedResIds();
            if (selectedResIds && selectedResIds.length > 0) {
                const leadId = selectedResIds[0];
                // Check if this lead has a linked quotation
                const quotes = await ormService.searchRead(
                    "sale.order",
                    [["opportunity_id", "=", leadId]],
                    ["id"],
                    { order: "id desc", limit: 1 }
                );
                if (quotes && quotes.length > 0) {
                    return actionService.doAction("custom_crm_extended.action_sale_order_duplicate_wizard", {
                        additionalContext: {
                            default_order_id: quotes[0].id,
                        },
                    });
                } else {
                    // Lead without quotation: duplicate lead and open it directly
                    const newLeadId = await ormService.call("crm.lead", "copy", [leadId]);
                    return actionService.doAction({
                        type: "ir.actions.act_window",
                        res_model: "crm.lead",
                        res_id: newLeadId,
                        views: [[false, "form"]],
                        target: "current",
                    });
                }
            }
        }
        return super.duplicateRecords(...arguments);
    },
});

