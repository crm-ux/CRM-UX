/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.resModel === "res.users") {
            const relabel = () => {
                const labelMap = {
                    "Sales": "Lead & Quotation",
                    "Products": "Product Catalog",
                    "Contact": "Contact Creation",
                    "Export": "Excel Export",
                };
                const labels = document.querySelectorAll(".o_field_res_user_group_ids_privilege label, .o_cell.o_wrap_label label");
                labels.forEach((el) => {
                    const text = el.childNodes[0]?.textContent?.trim();
                    if (labelMap[text]) {
                        el.childNodes[0].textContent = labelMap[text];
                    }
                });
                // Also update the section headers if needed
                const headers = document.querySelectorAll(".o_horizontal_separator");
                headers.forEach((h) => {
                    if (h.textContent.trim().toUpperCase() === "SALES") {
                        h.textContent = "Lead & Quotation";
                    }
                });
            };
            onMounted(relabel);
            onPatched(relabel);
        }
    },
});
