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
            let lastConfirmedDept = null;
            let lastConfirmedMgr = null;

            // Intercept Role Transfer, Department Change, and Manager Change Warnings
            const dialogService = this.env.services?.dialog;
            let origDialogAdd = null;
            if (dialogService && dialogService.add) {
                origDialogAdd = dialogService.add.bind(dialogService);
                dialogService.add = (Component, props, options) => {
                    const title = props?.title || "";
                    if (typeof title === "string" && (
                        title.includes("Role Transfer") ||
                        title.includes("Role Revocation") ||
                        title.includes("Department Change") ||
                        title.includes("Manager Change")
                    )) {
                        let confirmBtn = _t("Confirm");
                        if (title.includes("Role Transfer")) confirmBtn = _t("Transfer Role");
                        else if (title.includes("Role Revocation")) confirmBtn = _t("Revoke Role");
                        else if (title.includes("Department Change")) confirmBtn = _t("Change Department");
                        else if (title.includes("Manager Change")) confirmBtn = _t("Change Manager");

                        return origDialogAdd(ConfirmationDialog, {
                            title: props.title,
                            body: props.body || props.message,
                            confirmLabel: confirmBtn,
                            cancelLabel: _t("Close"),
                            confirm: () => {
                                const d = this.model?.root?.data;
                                if (title.includes("Role")) {
                                    const newJobName = Array.isArray(d?.crm_job_id) ? d.crm_job_id[1] : (d?.crm_job_id ? "new role" : "");
                                    lastConfirmedJob = Array.isArray(d?.crm_job_id) ? [...d.crm_job_id] : (d?.crm_job_id || false);
                                    this.env.services.notification?.add(
                                        _t(`Role transfer selected: ${newJobName || "New Role"}. Save the form to apply.`),
                                        { title: _t("Role Transfer Confirmed"), type: "success", sticky: false }
                                    );
                                } else if (title.includes("Department")) {
                                    const newDeptName = Array.isArray(d?.crm_department_id) ? d.crm_department_id[1] : "";
                                    lastConfirmedDept = Array.isArray(d?.crm_department_id) ? [...d.crm_department_id] : (d?.crm_department_id || false);
                                    this.env.services.notification?.add(
                                        _t(`Department changed to: ${newDeptName}. Save the form to apply.`),
                                        { title: _t("Department Confirmed"), type: "success", sticky: false }
                                    );
                                } else if (title.includes("Manager")) {
                                    const newMgrName = Array.isArray(d?.crm_manager_id) ? d.crm_manager_id[1] : "";
                                    lastConfirmedMgr = Array.isArray(d?.crm_manager_id) ? [...d.crm_manager_id] : (d?.crm_manager_id || false);
                                    this.env.services.notification?.add(
                                        _t(`Assigned manager changed to: ${newMgrName}. Save the form to apply.`),
                                        { title: _t("Manager Confirmed"), type: "success", sticky: false }
                                    );
                                }
                            },
                            cancel: async () => {
                                if (this.model?.root) {
                                    if (title.includes("Role")) {
                                        const oldJobName = Array.isArray(lastConfirmedJob) ? lastConfirmedJob[1] : "";
                                        if (lastConfirmedJob !== null) {
                                            await this.model.root.update({ crm_job_id: lastConfirmedJob });
                                        }
                                        this.env.services.notification?.add(
                                            _t(`Role transfer cancelled. Retained: ${oldJobName || "Current Role"}.`),
                                            { title: _t("Transfer Cancelled"), type: "info", sticky: false }
                                        );
                                    } else if (title.includes("Department")) {
                                        const oldDeptName = Array.isArray(lastConfirmedDept) ? lastConfirmedDept[1] : "";
                                        if (lastConfirmedDept !== null) {
                                            await this.model.root.update({ crm_department_id: lastConfirmedDept });
                                        }
                                        this.env.services.notification?.add(
                                            _t(`Department change cancelled. Retained: ${oldDeptName || "Current Department"}.`),
                                            { title: _t("Change Cancelled"), type: "info", sticky: false }
                                        );
                                    } else if (title.includes("Manager")) {
                                        const oldMgrName = Array.isArray(lastConfirmedMgr) ? lastConfirmedMgr[1] : "";
                                        if (lastConfirmedMgr !== null) {
                                            await this.model.root.update({ crm_manager_id: lastConfirmedMgr });
                                        }
                                        this.env.services.notification?.add(
                                            _t(`Manager change cancelled. Retained: ${oldMgrName || "Current Manager"}.`),
                                            { title: _t("Change Cancelled"), type: "info", sticky: false }
                                        );
                                    }
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
                if (this.model?.root?.data) {
                    const d = this.model.root.data;
                    lastConfirmedJob = Array.isArray(d.crm_job_id) ? [...d.crm_job_id] : (d.crm_job_id || false);
                    lastConfirmedDept = Array.isArray(d.crm_department_id) ? [...d.crm_department_id] : (d.crm_department_id || false);
                    lastConfirmedMgr = Array.isArray(d.crm_manager_id) ? [...d.crm_manager_id] : (d.crm_manager_id || false);
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
