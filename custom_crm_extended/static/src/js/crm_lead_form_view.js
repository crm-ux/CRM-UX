/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";

const WIZARD_ACTION = "custom_crm_extended.action_crm_lead_wizard";

export class CrmLeadFormController extends FormController {
    async create() {
        const dirty = await this.model.root.isDirty();
        if (dirty) {
            const saved = await this.model.root.save({
                onError: this.onSaveError.bind(this),
            });
            if (!saved) {
                return;
            }
        }
        await this.env.services.action.doAction(WIZARD_ACTION);
    }
}

registry.category("views").add("crm_lead_form", {
    ...formView,
    Controller: CrmLeadFormController,
});
