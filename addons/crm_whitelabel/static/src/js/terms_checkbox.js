/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    async beforeExecuteActionButton(clickParams) {
        return super.beforeExecuteActionButton(...arguments);
    }
});

// Auto-check all terms when wizard opens
document.addEventListener('DOMContentLoaded', () => {
    const observer = new MutationObserver(() => {
        const checkboxes = document.querySelectorAll('.o_field_many2many_checkboxes input[type="checkbox"]');
        if (checkboxes.length > 0) {
            checkboxes.forEach(cb => {
                if (!cb.checked) cb.click();
            });
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
});
