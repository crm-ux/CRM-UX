/** @odoo-module **/

import { registry } from "@web/core/registry";

const formatters = registry.category("formatters");
const fields = registry.category("fields");

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

// 2. Patch Form view DateField & DateTimeField components via fields registry
const dateFieldDef = fields.get("date");
if (dateFieldDef && dateFieldDef.component) {
    const comp = dateFieldDef.component;
    Object.defineProperty(comp.prototype, "formattedValue", {
        get() {
            return toCustomDate(this.props.record.data[this.props.name]);
        },
        configurable: true,
    });
}

const dateTimeFieldDef = fields.get("datetime");
if (dateTimeFieldDef && dateTimeFieldDef.component) {
    const comp = dateTimeFieldDef.component;
    Object.defineProperty(comp.prototype, "formattedValue", {
        get() {
            return toCustomDateTime(this.props.record.data[this.props.name]);
        },
        configurable: true,
    });
}
