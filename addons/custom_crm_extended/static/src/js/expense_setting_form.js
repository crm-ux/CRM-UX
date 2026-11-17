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
                    let html = `<div class="crm-manager-confirm-box" style="font-size: 0.88rem; color: #0f172a; margin: 0; padding: 0;">`;

                    // Green Block: Appointments & Activations
                    if (diff.appointments && diff.appointments.length > 0) {
                        html += `
                        <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px;">
                            <div style="font-weight: 700; font-size: 0.88rem; color: #166534; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                                <i class="fa fa-user-plus"></i> Appointments &amp; Activations (${diff.appointments.length})
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 3px;">`;
                        for (const app of diff.appointments) {
                            html += `
                                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.84rem; padding: 3px 0; border-top: 1px solid #dcfce7;">
                                    <div style="color: #0f172a; font-weight: 600;">
                                        <span style="display: inline-block; padding: 2px 7px; font-size: 0.72rem; font-weight: 700; border-radius: 4px; background: #dcfce7; color: #15803d; margin-right: 6px;">${app.badge}</span>
                                        ${app.name}
                                    </div>
                                    <span style="color: #475569; font-size: 0.78rem;">${app.action}</span>
                                </div>`;
                        }
                        html += `</div></div>`;
                    }

                    // Red Block: Revocations & Deactivations
                    if (diff.revocations && diff.revocations.length > 0) {
                        html += `
                        <div style="background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px;">
                            <div style="font-weight: 700; font-size: 0.88rem; color: #991b1b; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
                                <i class="fa fa-user-times"></i> Revocations &amp; Deactivations (${diff.revocations.length})
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 3px;">`;
                        for (const rev of diff.revocations) {
                            html += `
                                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.84rem; padding: 3px 0; border-top: 1px solid #fee2e2;">
                                    <div style="color: #0f172a; font-weight: 600;">
                                        <span style="display: inline-block; padding: 2px 7px; font-size: 0.72rem; font-weight: 700; border-radius: 4px; background: #fee2e2; color: #b91c1c; margin-right: 6px;">${rev.badge}</span>
                                        ${rev.name}
                                    </div>
                                    <span style="color: #475569; font-size: 0.78rem;">${rev.action}</span>
                                </div>`;
                        }
                        html += `</div></div>`;
                    }

                    // Prompt text: Dark, high contrast, readable
                    html += `
                    <div style="color: #0f172a !important; font-weight: 600 !important; font-size: 0.90rem !important; line-height: 1.45 !important; padding-top: 4px;">
                        Please review the manager updates above. Do you want to apply these changes and notify the appointed and revoked users?
                    </div></div>`;

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
