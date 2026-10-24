/** @odoo-module **/

import { registry } from "@web/core/registry";

// 1. Force Luxon globally to format all dates as dd/MM/yyyy and datetimes as dd/MM/yyyy HH:mm
const luxon = window.luxon;
if (luxon && luxon.DateTime) {
    const origToFormat = luxon.DateTime.prototype.toFormat;
    luxon.DateTime.prototype.toFormat = function (fmt, opts) {
        if (typeof fmt === "string") {
            // If it's a relative/smart month-day format like "MMM d" or "MMM d, yyyy"
            if (fmt.includes("MMM") || fmt.includes("MMMM")) {
                if (fmt.includes("h") || fmt.includes("H") || fmt.includes("t") || fmt.includes("T")) {
                    return origToFormat.call(this, "dd/MM/yyyy HH:mm", opts);
                }
                return origToFormat.call(this, "dd/MM/yyyy", opts);
            }
        }
        return origToFormat.apply(this, arguments);
    };

    const origToLocaleString = luxon.DateTime.prototype.toLocaleString;
    luxon.DateTime.prototype.toLocaleString = function (formatOpts, opts) {
        // If Luxon is asked for standard medium/short localized dates with month names
        if (formatOpts) {
            const hasTime = formatOpts.hour || formatOpts.minute || formatOpts.timeStyle;
            if (hasTime) {
                return origToFormat.call(this, "dd/MM/yyyy HH:mm", opts);
            }
            return origToFormat.call(this, "dd/MM/yyyy", opts);
        }
        return origToLocaleString.apply(this, arguments);
    };
}

// 2. Also ensure Odoo Formatters registry returns dd/MM/yyyy and dd/MM/yyyy HH:mm
const formatters = registry.category("formatters");
function toCustomDate(val) {
    if (!val) return "";
    if (typeof val.toFormat === "function") return val.toFormat("dd/MM/yyyy");
    const str = String(val);
    const m = str.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : str;
}

function toCustomDateTime(val) {
    if (!val) return "";
    if (typeof val.toFormat === "function") return val.toFormat("dd/MM/yyyy HH:mm");
    const str = String(val);
    const m = str.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
    return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : str;
}

if (formatters.contains("date")) {
    formatters.add("date", (val) => toCustomDate(val), { force: true });
}
if (formatters.contains("datetime")) {
    formatters.add("datetime", (val) => toCustomDateTime(val), { force: true });
}
