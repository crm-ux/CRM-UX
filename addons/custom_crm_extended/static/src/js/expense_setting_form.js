/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { markup } from "@odoo/owl";

const EXPENSE_SETTING_MODEL = "expense.setting";

patch(FormController.prototype, {
    async saveButtonClicked(params = {}) {
        if (this.props.resModel === EXPENSE_SETTING_MODEL && !this._isConfirmingManagerSave) {
            try {
                // Extract Global Managers
                const authField = this.model.root.data.authorized_manager_ids;
                let authIds = [];
                if (authField && authField.records) {
                    authIds = authField.records.map((r) => r.resId);
                } else if (authField && authField.currentIds) {
                    authIds = authField.currentIds;
                }

                // Extract Department Approvers & Toggles
                const deptField = this.model.root.data.department_ids;
                let depts = [];
                if (deptField && deptField.records) {
                    depts = deptField.records.map((r) => {
                        const vMgr = r.data.voucher_manager_id;
                        let vMgrId = false;
                        if (Array.isArray(vMgr)) {
                            vMgrId = vMgr[0];
                        } else if (vMgr && typeof vMgr === "object" && vMgr.id) {
                            vMgrId = vMgr.id;
                        } else if (typeof vMgr === "number") {
                            vMgrId = vMgr;
                        }
                        return {
                            id: r.resId,
                            voucher_manager_id: vMgrId,
                            voucher_approval_active: Boolean(r.data.voucher_approval_active),
                        };
                    });
                }

                // Query Diff from Backend
                const diff = await this.model.orm.call(
                    EXPENSE_SETTING_MODEL,
                    "check_manager_changes",
                    [],
                    {
                        auth_manager_ids: authIds,
                        departments: depts,
                    }
                );

                if (diff && diff.has_changes) {
                    const changes = [];
                    if (diff.appointments && diff.appointments.length > 0) {
                        for (const app of diff.appointments) {
                            changes.push(`• ${app.badge}: ${app.name} (${app.action})`);
                        }
                    }
                    if (diff.revocations && diff.revocations.length > 0) {
                        for (const rev of diff.revocations) {
                            changes.push(`• ${rev.badge}: ${rev.name} (${rev.action})`);
                        }
                    }

                    const bodyContent = markup(`
                        <div class="crm-confirm-dialog-content" style="font-size: 14px;">
                            ${changes.length ? `<div class="mb-2" style="white-space: pre-line; line-height: 1.5; color: #1e293b;">${changes.join("\n")}</div>` : ""}
                            <div style="color: #475569; line-height: 1.45;">Please review the manager updates above. Do you want to apply these changes and notify the appointed and revoked users?</div>
                        </div>
                    `);

                    this.env.services.dialog.add(ConfirmationDialog, {
                        title: _t("Confirm Voucher Manager Changes"),
                        body: bodyContent,
                        confirmLabel: _t("Confirm & Save"),
                        cancelLabel: _t("Cancel"),
                        confirm: async () => {
                            this._isConfirmingManagerSave = true;
                            try {
                                await this.saveButtonClicked(params);
                            } finally {
                                this._isConfirmingManagerSave = false;
                            }
                        },
                        cancel: () => {},
                    });
                    return;
                }
            } catch (err) {
                console.warn("Voucher Manager confirmation check error:", err);
            }
        }
        return super.saveButtonClicked(...arguments);
    },
});
