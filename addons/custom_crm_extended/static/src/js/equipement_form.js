/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";

export class EquipmentFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel === "equipment.master") {
            const reorderToolbar = () => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (container && breadcrumb && statusIndicator) {
                    if (statusIndicator.nextElementSibling !== breadcrumb) {
                        container.insertBefore(statusIndicator, breadcrumb);
                    }
                }
            };

            onMounted(() => {
                reorderToolbar();

                // Universal prevention of focus/navigation auto-scroll for ALL fields (current & future)
                const scrollContainers = [
                    document.querySelector(".o_content"),
                    document.querySelector(".o_form_sheet_bg"),
                    document.querySelector(".o_form_view")
                ].filter(Boolean);

                this._preventAutoScroll = (ev) => {
                    // Check if focused element is any form field, dropdown, input, or select
                    if (ev.target.closest(".o_field_widget") || ev.target.closest(".o_input") || ev.target.closest(".o_select_menu")) {
                        const savedPositions = scrollContainers.map(el => ({ el, top: el.scrollTop }));

                        // Lock scroll position across animation frames
                        requestAnimationFrame(() => {
                            savedPositions.forEach(({ el, top }) => {
                                if (el.scrollTop !== top) {
                                    el.scrollTop = top;
                                }
                            });
                        });
                    }
                };

                document.addEventListener("focusin", this._preventAutoScroll, true);
                document.addEventListener("keydown", (ev) => {
                    if (ev.key === "ArrowDown" || ev.key === "ArrowUp" || ev.key === "Enter") {
                        this._preventAutoScroll(ev);
                    }
                }, true);
            });

            onWillUnmount(() => {
                if (this._preventAutoScroll) {
                    document.removeEventListener("focusin", this._preventAutoScroll, true);
                }
            });
        }
    }
}

export const equipmentFormView = {
    ...formView,
    Controller: EquipmentFormController,
};

registry.category("views").add("equipment_form", equipmentFormView);
