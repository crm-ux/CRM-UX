/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

if (Many2OneField) {
    patch(Many2OneField.prototype, {
        get useSelectCreateDialog() {
            return false;
        },
        openSearchMore() {
            if (this.env.isSmall) {
                return super.openSearchMore ? super.openSearchMore(...arguments) : undefined;
            }
            return super.openSearchMore(...arguments);
        },
    });
}

if (Many2XAutocomplete) {
    patch(Many2XAutocomplete.prototype, {
        get useSelectCreateDialog() {
            return false;
        },
        openMobileSearch() {
            return;
        },
        onInputClick(ev) {
            // Stop mobile modal trigger
            if (this.env.isSmall) {
                ev.stopPropagation();
            }
            if (super.onInputClick) {
                return super.onInputClick(...arguments);
            }
        },
    });
}

