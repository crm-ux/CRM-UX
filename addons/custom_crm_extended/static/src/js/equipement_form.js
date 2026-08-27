/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";

export class EquipmentFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel === "equipment.master") {
            let observer = null;
            const reorderToolbar = () => {
                const dashboardBtn = document.querySelector(".o_control_panel_breadcrumbs > button.ms-1");
                const mainButtons = document.querySelector(".o_control_panel_breadcrumbs > .o_control_panel_main_buttons");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");

                if (dashboardBtn) dashboardBtn.style.order = "1";
                if (mainButtons) mainButtons.style.order = "2";
                if (statusIndicator) statusIndicator.style.order = "3";
                if (breadcrumb) breadcrumb.style.order = "4";
            };

            onMounted(() => {
                reorderToolbar();
                const panel = document.querySelector(".o_control_panel_breadcrumbs");
                if (panel) {
                    observer = new MutationObserver((mutations) => {
                        for (const mutation of mutations) {
                            if (mutation.type === "childList") {
                                reorderToolbar();
                                break;
                            }
                        }
                    });
                    observer.observe(panel, { childList: true });
                }
            });

            onWillUnmount(() => {
                if (observer) observer.disconnect();
            });
        }
    }
}

export const equipmentFormView = {
    ...formView,
    Controller: EquipmentFormController,
};

registry.category("views").add("equipment_form", equipmentFormView);
