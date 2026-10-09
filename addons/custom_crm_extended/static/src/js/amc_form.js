/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { setupUniversalAttachmentHandling } from "./universal_attachment_preview";

export class AmcFormController extends FormController {
    setup() {
        super.setup();

        let interval = null;

        // Clean, declarative configuration for all attachments on AMC Form
        const cleanupAttachments = setupUniversalAttachmentHandling(this, [
            {
                dataField: "po_attachment",
                filenameField: "po_filename",
                buttonName: "action_preview_amc_po",
                title: _t("PO Preview"),
                boxSelector: '[name="po_number"]',
            },
            {
                dataField: "invoice_attachment",
                filenameField: "invoice_filename",
                buttonName: "action_preview_amc_invoice",
                title: _t("Invoice Preview"),
                boxSelector: '[name="invoice_number"]',
            },
        ]);

        onMounted(() => {
            interval = setInterval(() => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (container && breadcrumb && statusIndicator) {
                    if (breadcrumb.previousElementSibling !== statusIndicator) {
                        container.insertBefore(breadcrumb, statusIndicator.nextSibling);
                    }
                    statusIndicator.classList.remove("me-auto");
                    statusIndicator.style.removeProperty("margin-right");
                    breadcrumb.style.removeProperty("margin-left");
                }
            }, 100);
        });

        onWillUnmount(() => {
            if (interval) {
                clearInterval(interval);
            }
            if (cleanupAttachments) {
                cleanupAttachments();
            }
        });
    }
}

export const amcFormView = {
    ...formView,
    Controller: AmcFormController,
};

registry.category("views").add("amc_form", amcFormView);

