/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

// Globally disable full-screen mobile search view for all Many2One/Many2X dropdowns on mobile
// so the dropdown opens directly inline (just like in web view) across all pages!
if (Many2XAutocomplete) {
    patch(Many2XAutocomplete.prototype, {
        get useSelectCreateDialog() {
            // In Odoo, if this is true on mobile, it opens the dialog list instead of autocomplete
            return false;
        },
        openMobileSearch() {
            // Do not open full-screen search view
            return;
        },
        onInputClick(ev) {
            // Force desktop dropdown behavior
            if (super.onInputClick) {
                return super.onInputClick(...arguments);
            }
        },
    });
}
