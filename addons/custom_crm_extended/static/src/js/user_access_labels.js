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
            let lastConfirmedJob = this.model.root.data?.crm_job_id ? [...this.model.root.data.crm_job_id] : false;

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
                                lastConfirmedJob = this.model.root.data?.crm_job_id ? [...this.model.root.data.crm_job_id] : false;
                            },
                            cancel: async () => {
                                // User cancelled or clicked Close: REVERT back to previous role!
                                if (lastConfirmedJob && this.model.root) {
                                    await this.model.root.update({ crm_job_id: lastConfirmedJob });
                                }
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
