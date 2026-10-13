/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

// Globally disable full-screen mobile search view for all Many2One/Many2X dropdowns on mobile
// so the dropdown opens directly inline (just like in web view) across all pages!
if (Many2XAutocomplete) {
    patch(Many2XAutocomplete.prototype, {
        openMobileSearch() {
            // By doing nothing here, Odoo skips the full-screen mobile search modal
            // and opens the normal inline autocomplete dropdown list directly under the input field!
            return;
        },
    });
}
