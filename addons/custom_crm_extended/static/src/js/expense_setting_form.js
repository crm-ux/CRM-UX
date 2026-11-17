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
                    let itemsHtml = "";

                    if (diff.appointments && diff.appointments.length > 0) {
                        for (const app of diff.appointments) {
                            itemsHtml += `
                            <div style="margin-bottom: 5px; color: #15803d; font-size: 13.5px; display: flex; align-items: baseline; gap: 6px;">
                                <span style="font-weight: 700;">+</span>
                                <div>
                                    <strong style="color: #0f172a;">${app.badge}:</strong> ${app.name} 
                                    <span style="font-size: 12px; color: #166534; background: #dcfce7; padding: 1px 6px; border-radius: 4px; margin-left: 4px; font-weight: 600;">${app.action}</span>
                                </div>
                            </div>`;
                        }
                    }

                    if (diff.revocations && diff.revocations.length > 0) {
                        for (const rev of diff.revocations) {
                            itemsHtml += `
                            <div style="margin-bottom: 5px; color: #b91c1c; font-size: 13.5px; display: flex; align-items: baseline; gap: 6px;">
                                <span style="font-weight: 700;">&minus;</span>
                                <div>
                                    <strong style="color: #0f172a;">${rev.badge}:</strong> ${rev.name} 
                                    <span style="font-size: 12px; color: #991b1b; background: #fee2e2; padding: 1px 6px; border-radius: 4px; margin-left: 4px; font-weight: 600;">${rev.action}</span>
                                </div>
                            </div>`;
                        }
                    }

                    const html = `
                    <div class="crm-manager-confirm-box" style="font-size: 13.5px; color: #0f172a; line-height: 1.5; margin: 0; padding: 0;">
                        <div style="margin-bottom: 12px; padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;">
                            ${itemsHtml}
                        </div>
                        <div style="color: #334155; font-size: 13px; font-weight: 500; line-height: 1.45;">
                            Please review the manager updates above. Do you want to apply these changes and notify the appointed and revoked users?
                        </div>
                    </div>`;

                    this.env.services.dialog.add(ConfirmationDialog, {
                        title: _t("Confirm Voucher Manager Changes"),
                        body: markup(html),
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
