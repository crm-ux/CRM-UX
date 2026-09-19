/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";

const TARGET_MODELS = [
    "equipment.master",
    "service.ticket",
    "amc.contract",
];

patch(ListController.prototype, {
    /**
     * Override getCogMenu to add "Export All (All Fields)" for target models
     */
    getCogMenu() {
        const cogMenu = super.getCogMenu(...arguments);
        const resModel = this.model?.root?.resModel || this.props?.resModel;

        if (TARGET_MODELS.includes(resModel)) {
            cogMenu.push({
                Component: undefined,
                key: "export_all_form_fields",
                text: _t("Export All (All Fields)"),
                icon: "fa fa-download",
                sequence: 15,
                callback: () => this.exportAllFormFields(),
            });
        }
        return cogMenu;
    },

    /**
     * Native Odoo export using all fields defined in the Form View
     */
    async exportAllFormFields() {
        const resModel = this.model.root.resModel;

        // 1. Dynamically fetch the Form View fields
        const viewData = await this.model.orm.getViews({
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
            const fdef = viewData.models[resModel][fname];
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
                context: this.props.context,
                domain: this.model.root.domain,
                fields: formFields,
                groupby: [],
                ids: false,
                model: resModel,
            }),
        };

        this.env.services.ui.block();
        try {
            await download({
                url: "/web/export/xlsx",
                data: exportData,
            });
        } finally {
            this.env.services.ui.unblock();
        }
    },
});
