/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { setupUniversalAttachmentHandling } from "./universal_attachment_preview";

export class CrmTaskManagementFormController extends FormController {
    setup() {
        super.setup();

        if (this.props.resModel === "crm.task.management") {
            const cleanupAttachments = setupUniversalAttachmentHandling(this, [
                {
                    dataField: "attachment_file",
                    filenameField: "attachment_name",
                    buttonName: "action_preview_task_attachment",
                    title: _t("Task Attachment Preview"),
                    boxSelector: '.crm_task_attachment_box',
                },
            ]);

            onWillUnmount(() => {
                if (cleanupAttachments) {
                    cleanupAttachments();
                }
            });
        }
    }
}

export const crmTaskManagementFormView = {
    ...formView,
    Controller: CrmTaskManagementFormController,
};

registry.category("views").add("crm_task_management_form", crmTaskManagementFormView);
