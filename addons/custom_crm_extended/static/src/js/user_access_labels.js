/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.resModel === "res.users") {
            let lastConfirmedJob = null;

            // Intercept Role Transfer Warning to show 2 buttons: "Transfer Role" and "Close" (Cancel)
            const dialogService = this.env.services?.dialog;
            let origDialogAdd = null;
            if (dialogService && dialogService.add) {
                origDialogAdd = dialogService.add.bind(dialogService);
                dialogService.add = (Component, props, options) => {
                    const title = props?.title || "";
                    if (typeof title === "string" && (title.includes("Role Transfer") || title.includes("Role Revocation"))) {
                        const isRevoke = title.includes("Role Revocation");
                        return origDialogAdd(ConfirmationDialog, {
                            title: props.title,
                            body: props.body || props.message,
                            confirmLabel: isRevoke ? _t("Revoke Role") : _t("Transfer Role"),
                            cancelLabel: _t("Close"),
                            confirm: () => {
                                // Transfer/Revoke confirmed: update lastConfirmedJob
                                const newJobName = Array.isArray(this.model?.root?.data?.crm_job_id)
                                    ? this.model.root.data.crm_job_id[1]
                                    : (this.model?.root?.data?.crm_job_id ? "new role" : "");
                                if (this.model?.root?.data?.crm_job_id) {
                                    lastConfirmedJob = Array.isArray(this.model.root.data.crm_job_id)
                                        ? [...this.model.root.data.crm_job_id]
                                        : this.model.root.data.crm_job_id;
                                } else {
                                    lastConfirmedJob = false;
                                }
                                if (isRevoke) {
                                    this.env.services.notification?.add(
                                        _t("Role revocation selected. Save the form to apply."),
                                        { title: _t("Role Revocation"), type: "warning", sticky: false }
                                    );
                                } else {
                                    this.env.services.notification?.add(
                                        _t(`Role transfer selected: ${newJobName || "New Role"}. Save the form to apply.`),
                                        { title: _t("Role Transfer Confirmed"), type: "success", sticky: false }
                                    );
                                }
                            },
                            cancel: async () => {
                                // User cancelled or clicked Close: REVERT back to previous role!
                                const oldJobName = Array.isArray(lastConfirmedJob) ? lastConfirmedJob[1] : "";
                                if (lastConfirmedJob && this.model?.root) {
                                    await this.model.root.update({ crm_job_id: lastConfirmedJob });
                                }
                                this.env.services.notification?.add(
                                    _t(`Role transfer cancelled. Retained current position: ${oldJobName || "Original Role"}.`),
                                    { title: _t("Transfer Cancelled"), type: "info", sticky: false }
                                );
                            },
                        }, options);
                    }
                    return origDialogAdd(Component, props, options);
                };
            }

            const labelMap = {
                "Sales": "Lead & Quotation",
                "Products": "Product Catalog",
                "Contact": "Contact Creation",
                "Export": "Excel Export",
            };

            const relabel = () => {
                document.querySelectorAll("label.o_form_label").forEach((lbl) => {
                    // Match the label text directly
                    const firstText = Array.from(lbl.childNodes)
                        .filter(node => node.nodeType === Node.TEXT_NODE)
                        .map(node => node.textContent.trim())
                        .join("");

                    if (labelMap[firstText]) {
                        // Replace only the text node, keep the tooltip '?' icon intact
                        for (let node of lbl.childNodes) {
                            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() === firstText) {
                                node.textContent = labelMap[firstText] + " ";
                                break;
                            }
                        }
                    }
                });

                document.querySelectorAll(".o_horizontal_separator").forEach((h) => {
                    const txt = h.textContent.trim().toUpperCase();
                    if (txt === "SALES") {
                        h.textContent = "Lead & Quotation";
                    } else if (txt === "MASTER DATA") {
                        // Completely hide standard MASTER DATA group/column
                        const masterBox = h.closest(".o_inner_group") || h.closest(".o_group");
                        if (masterBox) {
                            masterBox.style.setProperty("display", "none", "important");
                        } else {
                            h.style.setProperty("display", "none", "important");
                        }
                    }
                });
            };

            let observer = null;
            let isRelabeling = false;
            const safeRelabel = () => {
                if (isRelabeling) return;
                isRelabeling = true;
                try {
                    relabel();
                } finally {
                    isRelabeling = false;
                }
            };

            onMounted(() => {
                if (this.model?.root?.data?.crm_job_id) {
                    lastConfirmedJob = Array.isArray(this.model.root.data.crm_job_id)
                        ? [...this.model.root.data.crm_job_id]
                        : this.model.root.data.crm_job_id;
                }
                safeRelabel();
                observer = new MutationObserver(() => {
                    if (!isRelabeling) safeRelabel();
                });
                observer.observe(document.body, { childList: true, subtree: true });
            });

            onPatched(safeRelabel);

            onWillUnmount(() => {
                if (observer) observer.disconnect();
                if (dialogService && origDialogAdd) {
                    dialogService.add = origDialogAdd;
                }
            });
        }
    },
});
