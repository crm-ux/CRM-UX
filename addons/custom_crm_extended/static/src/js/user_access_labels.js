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
            const dialogService = this.env.services?.dialog;
            const notificationService = this.env.services?.notification;
            let isBypassingGuard = false;

            const wrapRootUpdate = () => {
                const root = this.model?.root;
                if (!root || root._crmGuarded) return;
                root._crmGuarded = true;

                const origUpdate = root.update.bind(root);
                root.update = (changes, ...args) => {
                    if (isBypassingGuard || !root.resId || !changes || typeof changes !== "object") {
                        return origUpdate(changes, ...args);
                    }

                    // 1. JOB POSITION CHANGE
                    if ("crm_job_id" in changes) {
                        const currentVal = root.data?.crm_job_id;
                        const currentId = currentVal ? (Array.isArray(currentVal) ? currentVal[0] : currentVal) : false;
                        const currentName = currentVal ? (Array.isArray(currentVal) ? currentVal[1] : "Unassigned") : "Unassigned";

                        const newVal = changes.crm_job_id;
                        const newId = newVal ? (Array.isArray(newVal) ? newVal[0] : newVal) : false;
                        const newName = newVal ? (Array.isArray(newVal) ? newVal[1] : "Unassigned") : "Unassigned";

                        if (currentId !== newId) {
                            dialogService?.add(ConfirmationDialog, {
                                title: _t("Role Transfer Warning"),
                                body: _t(
                                    `This employee is currently assigned to '${currentName}'.\n\n` +
                                    `Changing to '${newName}' will transfer their position, update their Department, ` +
                                    `and update their access permissions upon saving.\n\n` +
                                    `Click 'Transfer Role' to confirm, or click 'Close' to keep them in '${currentName}'.`
                                ),
                                confirmLabel: _t("Transfer Role"),
                                cancelLabel: _t("Close"),
                                confirm: async () => {
                                    isBypassingGuard = true;
                                    try {
                                        await origUpdate(changes, ...args);
                                        notificationService?.add(
                                            _t(`Role transfer selected: ${newName}. Save the form to apply.`),
                                            { title: _t("Role Transfer Confirmed"), type: "success", sticky: false }
                                        );
                                    } finally {
                                        isBypassingGuard = false;
                                    }
                                },
                                cancel: () => {
                                    notificationService?.add(
                                        _t(`Role transfer cancelled. Retained current position: ${currentName}.`),
                                        { title: _t("Transfer Cancelled"), type: "info", sticky: false }
                                    );
                                },
                            });
                            return Promise.resolve();
                        }
                    }

                    // 2. ASSIGNED MANAGER CHANGE
                    if ("crm_manager_id" in changes) {
                        const currentVal = root.data?.crm_manager_id;
                        const currentId = currentVal ? (Array.isArray(currentVal) ? currentVal[0] : currentVal) : false;
                        const currentName = currentVal ? (Array.isArray(currentVal) ? currentVal[1] : "None") : "None";

                        const newVal = changes.crm_manager_id;
                        const newId = newVal ? (Array.isArray(newVal) ? newVal[0] : newVal) : false;
                        const newName = newVal ? (Array.isArray(newVal) ? newVal[1] : "None") : "None";

                        if (currentId !== newId) {
                            dialogService?.add(ConfirmationDialog, {
                                title: _t("Manager Change Warning"),
                                body: _t(
                                    `This employee currently reports to '${currentName}'.\n\n` +
                                    `Changing reporting manager to '${newName}' will update their reporting line and hierarchy.\n\n` +
                                    `Click 'Change Manager' to confirm, or click 'Close' to keep reporting to '${currentName}'.`
                                ),
                                confirmLabel: _t("Change Manager"),
                                cancelLabel: _t("Close"),
                                confirm: async () => {
                                    isBypassingGuard = true;
                                    try {
                                        await origUpdate(changes, ...args);
                                        notificationService?.add(
                                            _t(`Assigned manager changed to: ${newName}. Save the form to apply.`),
                                            { title: _t("Manager Confirmed"), type: "success", sticky: false }
                                        );
                                    } finally {
                                        isBypassingGuard = false;
                                    }
                                },
                                cancel: () => {
                                    notificationService?.add(
                                        _t(`Manager change cancelled. Retained current manager: ${currentName}.`),
                                        { title: _t("Change Cancelled"), type: "info", sticky: false }
                                    );
                                },
                            });
                            return Promise.resolve();
                        }
                    }

                    return origUpdate(changes, ...args);
                };
            };

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
                wrapRootUpdate();
                safeRelabel();
                observer = new MutationObserver(() => {
                    if (!isRelabeling) safeRelabel();
                });
                observer.observe(document.body, { childList: true, subtree: true });
            });

            onPatched(() => {
                wrapRootUpdate();
                safeRelabel();
            });

            onWillUnmount(() => {
                if (observer) observer.disconnect();
            });
        }
    },
});
