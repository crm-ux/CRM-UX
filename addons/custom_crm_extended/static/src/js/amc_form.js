/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";

export class AmcFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => {
            this.reorderAmcNavbar();
        });
    }

    reorderAmcNavbar() {
        const interval = setInterval(() => {
            const container = document.querySelector(".o_control_panel_breadcrumbs");
            const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
            const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
            if (container && breadcrumb && statusIndicator) {
                if (breadcrumb.previousElementSibling !== statusIndicator) {
                    container.insertBefore(breadcrumb, statusIndicator.nextSibling);
                }
            }
        }, 100);

        onWillUnmount(() => clearInterval(interval));
    }
}

export const amcFormView = {
    ...formView,
    Controller: AmcFormController,
};

registry.category("views").add("amc_form", amcFormView);
