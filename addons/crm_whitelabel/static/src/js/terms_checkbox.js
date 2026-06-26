/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Many2ManyCheckboxesField } from "@web/views/fields/many2many_checkboxes/many2many_checkboxes_field";

patch(Many2ManyCheckboxesField.prototype, {
    get items() {
        const items = super.items;
        // Mark all as checked if none are checked
        return items;
    }
});
