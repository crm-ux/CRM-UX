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
        async loadOptionsSource(request) {
            const options = await super.loadOptionsSource(...arguments);
            if (!Array.isArray(options)) return options;
            // Filter out external partner autocomplete suggestions
            return options.filter(opt => {
                if (opt.is_autocomplete || opt.classList?.includes("o_partner_autocomplete") || opt.classList?.includes("partner_autocomplete")) {
                    return false;
                }
                // Odoo's partner_autocomplete injects items with external ID or company metadata
                if (opt.isCompany || opt.autocomplete_data || opt.data?.is_autocomplete) {
                    return false;
                }
                return true;
            });
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

