/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { Component, xml } from "@odoo/owl";

const cogMenuRegistry = registry.category("cogMenu");

const TARGET_MODELS = [
    "equipment.master",
    "service.ticket",
    "amc.contract",
];

const MODEL_NAMES = {
    "equipment.master": "Equipment Master",
    "service.ticket": "Service Ticket",
    "amc.contract": "AMC Contract",
};

/**
 * Format raw field names like 'model_number' -> 'Model Number'
 */
function formatCleanHeader(rawName) {
    if (!rawName) return "";
    return rawName
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase())
        .trim();
}

export async function exportAllFormFields(env) {
    const resModel = env.config?.resModel || env.searchModel?.resModel || env.config?.action?.res_model;
    if (!resModel) return;

    // 1. Dynamically fetch the Form View fields
    const viewData = await env.services.orm.call(
        resModel,
        "get_views",
        [[[false, "form"]]]
    );

    const formFields = [];
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(viewData.views.form.arch, "text/xml");
    const fieldNodes = xmlDoc.querySelectorAll("field");

    const ignoredTypes = ["binary", "one2many", "many2many"];
    const ignoredNames = ["message_follower_ids", "activity_ids", "message_ids", "customer_signature", "engineer_signature"];

    // Field dictionary
    const modelFields = viewData.views?.form?.fields || viewData.models?.[resModel] || {};

    for (const node of fieldNodes) {
        // Skip fields that are inside sub-tables (one2many child lists/trees)
        if (node.closest("list, tree")) {
            continue;
        }

        const fname = node.getAttribute("name");
        if (!fname || ignoredNames.includes(fname) || formFields.some((f) => f.name === fname)) {
            continue;
        }

        const fdef = modelFields[fname];
        // Ensure field is not binary or relational list
        if (!fdef || !ignoredTypes.includes(fdef.type)) {
            const rawLabel = node.getAttribute("string") || (fdef ? fdef.string : false) || fname;
            const cleanLabel = formatCleanHeader(rawLabel);

            formFields.push({
                name: fname,
                label: cleanLabel,
                type: fdef ? fdef.type : "char", // type is required by /web/export/xlsx
            });
        }
    }

    if (!formFields.length) {
        return;
    }

    // 2. Fetch record IDs (handles both multiple checkboxes and full list)
    const domain = env.searchModel?.domain || [];
    const selection = env.model?.root?.selection || [];
    let ids = [];

    if (selection.length > 0) {
        // User selected specific rows
        ids = selection.map((r) => r.resId);
    } else {
        // Export all records matching the active filter
        ids = await env.services.orm.search(resModel, domain);
    }

    if (!ids.length) {
        return;
    }


    const cleanName = MODEL_NAMES[resModel] || resModel;
    const filename = `${cleanName}.xlsx`;

    // 3. Call Odoo's native /web/export/xlsx
    const exportData = {
        data: JSON.stringify({
            import_compat: false,
            context: env.searchModel?.context || {},
            domain: domain,
            fields: formFields,
            groupby: [],
            ids: ids,
            model: resModel,
            custom_filename: filename
        }),
    };

    env.services.ui.block();
    try {
        await download({
            url: "/web/export/xlsx",
            data: exportData,
        });
    } finally {
        env.services.ui.unblock();
    }
}

class ExportAllFieldsMenuItem extends Component {
    static template = xml`
        <span class="dropdown-item d-flex align-items-center cursor-pointer" role="menuitem" t-on-click="onSelected">
            <i class="fa fa-download me-2"/>
            <span>Export All (All Fields)</span>
        </span>
    `;

    async onSelected() {
        await exportAllFormFields(this.env);
    }
}

cogMenuRegistry.add("export_all_form_fields", {
    isDisplayed: (env) => {
        const resModel = env.config?.resModel || env.searchModel?.resModel || env.config?.action?.res_model;
        const viewType = env.config?.viewType;
        const isListOrTree = !viewType || viewType === "list" || viewType === "tree";
        return isListOrTree && TARGET_MODELS.includes(resModel);
    },
    Component: ExportAllFieldsMenuItem,
    groupNumber: 20,
    sequence: 15,
});
