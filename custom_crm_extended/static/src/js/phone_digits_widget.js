/** @odoo-module **/
import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";

export class PhoneDigitsField extends CharField {
    onInput(ev) {
        let value = ev.target.value || "";
        // Strip non-digits
        value = value.replace(/\D/g, "");
        // Limit to 10 digits
        if (value.length > 10) {
            value = value.slice(0, 10);
        }
        if (value !== ev.target.value) {
            ev.target.value = value;
        }
        super.onInput(ev);
    }
    onKeydown(ev) {
        const allowedKeys = [
            "Backspace", "Delete", "Tab", "Escape", "Enter",
            "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"
        ];
        if (allowedKeys.includes(ev.key) || ev.ctrlKey || ev.metaKey) {
            return;
        }
        // Block non-digit characters
        if (!/^[0-9]$/.test(ev.key)) {
            ev.preventDefault();
            return;
        }
        // Block if already 10 digits
        const current = ev.target.value.replace(/\D/g, "");
        if (current.length >= 10) {
            ev.preventDefault();
        }
    }
}

registry.category("fields").add("phone_digits", PhoneDigitsField);
