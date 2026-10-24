/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DateField } from "@web/views/fields/date/date_field";
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";
import { registry } from "@web/core/registry";

const formatters = registry.category("formatters");

/**
 * Helper to format Luxon DateTime or string to dd/MM/yyyy
 */
function toCustomDate(val) {
    if (!val) return "";
    if (typeof val.toFormat === "function") {
        return val.toFormat("dd/MM/yyyy");
    }
    const str = String(val);
    const m = str.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) {
        return `${m[3]}/${m[2]}/${m[1]}`;
    }
    return str;
}

/**
 * Helper to format Luxon DateTime or string to dd/MM/yyyy HH:mm (no seconds)
 */
function toCustomDateTime(val) {
    if (!val) return "";
    if (typeof val.toFormat === "function") {
        return val.toFormat("dd/MM/yyyy HH:mm");
    }
    const str = String(val);
    const m = str.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
    if (m) {
        return `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}`;
    }
    return str;
}

// 1. Override standard formatters used by List views, Kanban & Exports
if (formatters.contains("date")) {
    formatters.add("date", (value) => toCustomDate(value), { force: true });
}
if (formatters.contains("datetime")) {
    formatters.add("datetime", (value) => toCustomDateTime(value), { force: true });
}

// 2. Patch Form view DateField component
if (DateField) {
    patch(DateField.prototype, {
        get formattedValue() {
            return toCustomDate(this.props.record.data[this.props.name]);
        },
    });
}

// 3. Patch Form view DateTimeField component
if (DateTimeField) {
    patch(DateTimeField.prototype, {
        get formattedValue() {
            return toCustomDateTime(this.props.record.data[this.props.name]);
        },
    });
}
