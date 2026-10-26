/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { AutoComplete } from "@web/core/autocomplete/autocomplete";

export class ResPartnerFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel === "res.partner") {
            let observer = null;
            let clickHandler = null;

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
        if (this.props.resModel === "res.partner") {
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
                // Fallback: return to Customers list
                this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: "Customers",
                    res_model: "res.partner",
                    views: [[false, "list"], [false, "form"]],
                    domain: [["customer_rank", ">", 0]],
                }, { clearBreadcrumbs: true });
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

export const resPartnerFormView = {
    ...formView,
    Controller: ResPartnerFormController,
};

registry.category("views").add("res_partner_form", resPartnerFormView);

// Force child contacts under existing company to always open in clean modal dialog wizard

if (X2ManyField) {
    patch(X2ManyField.prototype, {
        async openRecord(record) {
            if (this.props.name === "child_ids" && typeof this.openDialog === "function") {
                return this.openDialog({ resId: record.resId });
            }
            return super.openRecord(...arguments);
        },
    });
}

// Intercept AutoComplete to strip out external partner suggestions & "Searching Autocomplete..." spinner
if (AutoComplete) {
    patch(AutoComplete.prototype, {
        get options() {
            const list = super.options;
            if (!Array.isArray(list)) return list;
            return list.filter(item => {
                const label = (item.label || "").toString().toLowerCase();
                if (label.includes("searching autocomplete")) return false;
                if (item.classList && item.classList.includes("o_partner_autocomplete")) return false;
                if (item.is_autocomplete || item.autocomplete_data) return false;
                return true;
            });
        },
    });
}
