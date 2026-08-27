/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";

export class EquipmentFormController extends FormController { }

export const equipmentFormView = {
    ...formView,
    Controller: EquipmentFormController,
};

registry.category("views").add("equipment_form", equipmentFormView);
