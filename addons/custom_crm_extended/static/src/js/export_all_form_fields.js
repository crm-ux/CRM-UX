/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { Component } from "@odoo/owl";

const cogMenuRegistry = registry.category("cogMenu");

const TARGET_MODELS = [
    "equipment.master",
    "service.ticket",
    "amc.contract",
];

export async function exportAllFormFields(env) {
    const action = env.config?.action;
    const resModel = action?.res_model;
    if (!resModel) return;

    // 1. Dynamically fetch the Form View fields
    const viewData = await env.services.orm.getViews({
        res_model: resModel,
        views: [[false, "form"]],
    });

    const formFields = [];
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(viewData.views.form.arch, "text/xml");
    const fieldNodes = xmlDoc.querySelectorAll("field");

    const ignoredTypes = ["binary", "one2many"];
    const ignoredNames = ["message_follower_ids", "activity_ids", "message_ids"];

    for (const node of fieldNodes) {
        const fname = node.getAttribute("name");
        const fdef = viewData.models[resModel]?.[fname];
        if (
            fname &&
            fdef &&
            !ignoredNames.includes(fname) &&
            !ignoredTypes.includes(fdef.type) &&
            !formFields.some((f) => f.name === fname)
        ) {
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
            ids: false,
            model: resModel,
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
    static template = "web.DropdownItem";
    static components = { DropdownItem };

    async onSelected() {
        await exportAllFormFields(this.env);
    }
}

cogMenuRegistry.add("export_all_form_fields", {
    isDisplayed: (env) => {
        const resModel = env.searchModel?.resModel;
        return TARGET_MODELS.includes(resModel);
    },
    Component: ExportAllFieldsMenuItem,
    groupNumber: 20,
    sequence: 15,
});

