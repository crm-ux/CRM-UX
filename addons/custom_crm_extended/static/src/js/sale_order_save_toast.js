/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const SALE_ORDER_MODEL = "sale.order";

patch(FormController.prototype, {
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
            const result = await super.discard(...arguments);
            this.env.services.notification.add("Operation cancelled.", {
                type: "warning",
            });
            return result;
        }
        return super.discard(...arguments);
    },
});
