/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
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

    const modelFields = viewData.views?.form?.fields || viewData.models?.[resModel] || {};
    for (const node of fieldNodes) {
        const fname = node.getAttribute("name");
        if (!fname || ignoredNames.includes(fname) || formFields.some((f) => f.name === fname)) {
            continue;
        }
        const fdef = modelFields[fname];
        // Only export fields that actually exist on the model and are not binary or relational lists
        if (fdef && !ignoredTypes.includes(fdef.type)) {
            formFields.push({
                name: fname,
                label: node.getAttribute("string") || fdef.string || fname,
            });
        }
    }

    // 2. Call Odoo's native /web/export/xlsx
    const exportData = {
        data: JSON.stringify({
            import_compat: false,
            context: env.searchModel?.context || {},
            domain: env.searchModel?.domain || [],
            fields: formFields,
            groupby: [],
            ids: [],
            model: resModel,
        }),
    };

    const cleanName = MODEL_NAMES[resModel] || resModel;
    const filename = `${cleanName}.xlsx`;

    env.services.ui.block();
    try {
        await download({
            url: "/web/export/xlsx",
            data: exportData,
            filename: filename,
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

