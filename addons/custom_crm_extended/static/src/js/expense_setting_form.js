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
                    let html = `<div class="crm-manager-confirm-box" style="font-size: 0.92rem; color: #1e293b;">`;

                    // Green Block: Appointments & Activations
                    if (diff.appointments && diff.appointments.length > 0) {
                        html += `
                        <div class="mb-3 p-3 rounded-3" style="background:#f0fdf4; border:1px solid #bbf7d0;">
                            <div class="fw-bold mb-2 text-success" style="font-size:0.95rem;">
                                <i class="fa fa-user-plus me-1"></i> Appointments &amp; Activations (${diff.appointments.length})
                            </div>
                            <ul class="mb-0 ps-3" style="line-height: 1.6;">`;
                        for (const app of diff.appointments) {
                            html += `<li><strong>${app.badge}:</strong> ${app.name} &mdash; <span class="text-muted">${app.action}</span></li>`;
                        }
                        html += `</ul></div>`;
                    }

                    // Red Block: Revocations & Deactivations
                    if (diff.revocations && diff.revocations.length > 0) {
                        html += `
                        <div class="mb-3 p-3 rounded-3" style="background:#fef2f2; border:1px solid #fecaca;">
                            <div class="fw-bold mb-2 text-danger" style="font-size:0.95rem;">
                                <i class="fa fa-user-times me-1"></i> Revocations &amp; Deactivations (${diff.revocations.length})
                            </div>
                            <ul class="mb-0 ps-3" style="line-height: 1.6;">`;
                        for (const rev of diff.revocations) {
                            html += `<li><strong>${rev.badge}:</strong> ${rev.name} &mdash; <span class="text-muted">${rev.action}</span></li>`;
                        }
                        html += `</ul></div>`;
                    }

                    // User selected prompt
                    html += `
                    <div class="pt-2 fw-semibold text-secondary" style="font-size: 0.93rem;">
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
