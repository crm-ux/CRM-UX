/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { setupUniversalAttachmentHandling, UniversalAttachmentPreviewDialog } from "./universal_attachment_preview";

const TICKET_MODEL = "service.ticket";
const WIZARD_ACTION = "custom_crm_extended.action_service_ticket_wizard";

async function openServiceTicketWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

// 1. Intercept "New" button in List / Tree View
patch(ListController.prototype, {
    async createRecord() {
        if (
            this.model?.root?.resModel === TICKET_MODEL ||
            this.props?.resModel === TICKET_MODEL
        ) {
            await openServiceTicketWizard(this.env);
            return;
        }
        return super.createRecord(...arguments);
    },
    async openNewRecord() {
        if (
            this.model?.root?.resModel === TICKET_MODEL ||
            this.props?.resModel === TICKET_MODEL
        ) {
            await openServiceTicketWizard(this.env);
            return;
        }
        return super.openNewRecord(...arguments);
    },
});

// 2. Intercept "New" button in Detail Form View
patch(FormController.prototype, {
    async create() {
        if (
            this.props?.resModel === TICKET_MODEL ||
            this.model?.root?.resModel === TICKET_MODEL
        ) {
            const dirty = await this.model?.root?.isDirty?.();
            if (dirty) {
                const saved = await this.model.root.save({
                    onError: this.onSaveError?.bind(this),
                });
                if (!saved) {
                    return;
                }
            }
            await openServiceTicketWizard(this.env);
            return;
        }
        return super.create(...arguments);
    },
});

export class ServiceTicketFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel === "service.ticket") {
            let observer = null;
            const reorderToolbar = () => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (container && breadcrumb && statusIndicator) {
                    // 1. Move breadcrumb (ID + Gear) right after buttons
                    if (breadcrumb.previousElementSibling !== statusIndicator) {
                        container.insertBefore(breadcrumb, statusIndicator.nextSibling);
                    }
                    // 2. Remove flex-grow and margin gap in JS directly
                    statusIndicator.style.setProperty("margin-right", "16px", "important");
                    statusIndicator.style.setProperty("flex-grow", "0", "important");
                    statusIndicator.style.setProperty("width", "auto", "important");
                    breadcrumb.style.setProperty("margin-left", "0", "important");
                    breadcrumb.style.setProperty("flex-grow", "0", "important");
                }
            };

            // Setup universal attachment handling for Service Report
            const cleanupAttachments = setupUniversalAttachmentHandling(this, [
                {
                    dataField: "report_attachment",
                    filenameField: "report_filename",
                    buttonName: "action_preview_service_report",
                    title: _t("Service Report Preview"),
                    boxSelector: '[name="report_number"]',
                },
            ]);

            // Cache for tracking newly picked bill files immediately in memory before saving
            const voucherFileCache = new Map();

            const handleVoucherFileInputChange = (e) => {
                const input = e.target;
                if (input.type === "file") {
                    const row = input.closest("tr, .o_data_row");
                    const isVoucherRow = row && (row.closest(".o_voucher_card_list") || row.closest("[name='voucher_line_ids']"));
                    const isQuickAdd = input.closest("[name='new_voucher_bill_file']");

                    const file = input.files && input.files[0];
                    if (file && (isVoucherRow || isQuickAdd)) {
                        const reader = new FileReader();
                        reader.onload = (loadEvt) => {
                            const b64 = loadEvt.target.result.split(",")[1];
                            if (isQuickAdd) {
                                voucherFileCache.set("quick_add", { data: b64, filename: file.name });
                            } else if (row) {
                                voucherFileCache.set(row, { data: b64, filename: file.name });
                            }
                        };
                        reader.readAsDataURL(file);
                    }
                }
            };

            // Handle Eye Preview button on Voucher lines (Custom preview dialog instead of opening a new browser tab)
            const handleVoucherBillPreview = async (ev) => {
                const previewBtn = ev.target.closest("button[name='action_preview_bill']");
                if (!previewBtn) return;

                ev.preventDefault();
                ev.stopPropagation();

                const row = previewBtn.closest("tr, .o_data_row");
                if (!row) return;

                let filename = "bill.png";
                let fileData = null;
                let recId = null;

                // 1. Check if user just selected a new file on this row (unsaved in memory)
                const cachedRowFile = voucherFileCache.get(row);
                if (cachedRowFile) {
                    fileData = cachedRowFile.data;
                    filename = cachedRowFile.filename;
                }

                // 2. Also check if file input in this row has a chosen file
                if (!fileData) {
                    const fileInp = row.querySelector("input[type='file']");
                    if (fileInp && fileInp.files && fileInp.files[0]) {
                        const localFile = fileInp.files[0];
                        filename = localFile.name || filename;
                        fileData = await new Promise((resolve) => {
                            const r = new FileReader();
                            r.onload = () => resolve(r.result.split(",")[1]);
                            r.readAsDataURL(localFile);
                        });
                        voucherFileCache.set(row, { data: fileData, filename: filename });
                    }
                }

                // 3. Match with voucher_line_ids in root record data
                const record = this.model?.root;
                const voucherList = record?.data?.voucher_line_ids;
                let voucherRecord = null;
                if (voucherList && voucherList.records) {
                    const allRows = Array.from(row.closest("tbody")?.querySelectorAll("tr.o_data_row") || []);
                    const rowIndex = allRows.indexOf(row);
                    if (rowIndex >= 0 && rowIndex < voucherList.records.length) {
                        voucherRecord = voucherList.records[rowIndex];
                    }
                }

                if (voucherRecord) {
                    recId = voucherRecord.resId || null;
                    // If no newly selected local file, take from current record
                    if (!fileData) {
                        filename = voucherRecord.data.bill_filename || filename;
                        fileData = voucherRecord.data.bill_file || null;
                    }
                }

                // 4. If fileData is a size string, fetch raw binary from server
                const isSizeString = typeof fileData === "string" && (
                    fileData.includes("bytes") || fileData.includes("Kb") || fileData.includes("Mb") || fileData.length < 50
                );
                if (recId && (!fileData || isSizeString)) {
                    try {
                        const res = await this.env.services.orm.read(
                            "service.ticket.voucher.line",
                            [recId],
                            ["bill_file", "bill_filename"],
                            { context: { bin_size: false } }
                        );
                        if (res && res[0]) {
                            fileData = res[0].bill_file || fileData;
                            if (res[0].bill_filename) filename = res[0].bill_filename;
                        }
                    } catch (readErr) {
                        console.warn("Could not read voucher bill_file:", readErr);
                    }
                }

                // For office documents/excel/zip, retrieve formatted preview content from server
                let previewContent = null;
                const isDocOrZipOrExcel = ["docx", "doc", "zip", "rar", "7z", "tar", "gz", "xlsx", "xls", "csv"].some((ext) =>
                    (filename || "").toLowerCase().endsWith("." + ext)
                );

                if (isDocOrZipOrExcel && fileData) {
                    try {
                        previewContent = await this.env.services.orm.call(
                            "equipment.master",
                            "action_get_invoice_preview_content",
                            [false, fileData, filename],
                            {}
                        );
                    } catch (callErr) {
                        console.error("Error retrieving voucher bill preview content:", callErr);
                    }
                }

                // If not yet saved or if user just selected a new file, don't use stale server URL
                const hasUnsavedNewFile = cachedRowFile || (fileData && !isSizeString && fileData.length > 100);
                const fileUrl = (!hasUnsavedNewFile && recId) ? `/web/content/service.ticket.voucher.line/${recId}/bill_file/${encodeURIComponent(filename)}?download=false` : null;

                this.dialogService.add(UniversalAttachmentPreviewDialog, {
                    title: filename || _t("Bill Preview"),
                    fileUrl: fileUrl,
                    fileData: fileData,
                    filename: filename,
                    previewContent: previewContent,
                });
            };

            document.addEventListener("change", handleVoucherFileInputChange, true);
            document.addEventListener("click", handleVoucherBillPreview, true);

            // Instant Client-side calculation: Total KM * Rate/KM = Amount
            const handleKmInstantCalc = (ev) => {
                const target = ev.target;
                if (!target) return;
                const kmField = target.closest("[name='new_voucher_total_km']");
                if (kmField) {
                    const bar = target.closest(".o_voucher_quick_add_bar");
                    if (!bar) return;
                    const kmVal = parseFloat(target.value) || 0.0;
                    
                    // Find rate value from .o_readonly_box or rate field
                    const rateBox = bar.querySelector("[name='new_voucher_rate_per_km']");
                    let rateVal = 0.0;
                    if (rateBox) {
                        const rateText = rateBox.innerText || rateBox.textContent || rateBox.value || "0";
                        rateVal = parseFloat(rateText.replace(/[^0-9.]/g, "")) || 0.0;
                    }

                    if (kmVal > 0 && rateVal > 0) {
                        const calculated = parseFloat((kmVal * rateVal).toFixed(2));
                        // 1. If Odoo model root is accessible, update record directly
                        if (this.model && this.model.root && this.model.root.update) {
                            this.model.root.update({ new_voucher_amount: calculated });
                        }
                        // 2. Also update DOM inside the readonly box or input
                        const amountField = bar.querySelector("[name='new_voucher_amount']");
                        if (amountField) {
                            const inp = amountField.querySelector("input, .o_input");
                            if (inp) {
                                inp.value = calculated.toFixed(2);
                                inp.dispatchEvent(new Event("input", { bubbles: true }));
                                inp.dispatchEvent(new Event("change", { bubbles: true }));
                            } else {
                                amountField.innerText = `₹ ${calculated.toFixed(2)}`;
                            }
                        }
                    }
                }
            };

            document.addEventListener("input", handleKmInstantCalc, true);
            document.addEventListener("change", handleKmInstantCalc, true);

            onMounted(() => {
                reorderToolbar();
                const panel = document.querySelector(".o_control_panel_breadcrumbs");
                if (panel) {
                    observer = new MutationObserver(() => reorderToolbar());
                    observer.observe(panel, { childList: true });
                }
            });

            onWillUnmount(() => {
                if (observer) observer.disconnect();
                if (cleanupAttachments) {
                    cleanupAttachments();
                }
                document.removeEventListener("change", handleVoucherFileInputChange, true);
                document.removeEventListener("click", handleVoucherBillPreview, true);
                document.removeEventListener("input", handleKmInstantCalc, true);
                document.removeEventListener("change", handleKmInstantCalc, true);
            });
        }
    }

    async discard() {
        if (this.props.resModel === "service.ticket") {
            const isDirty = this.model.root.isDirty ? await this.model.root.isDirty() : false;
            const goBack = async () => {
                await this.model.root.discard();
                const breadcrumbs = this.env.config?.breadcrumbs || [];
                if (breadcrumbs.length > 1) {
                    const prev = breadcrumbs[breadcrumbs.length - 2];
                    if (prev && prev.jsId) {
                        this.actionService.restore(prev.jsId);
                        return;
                    }
                }
                this.actionService.doAction("custom_crm_extended.action_service_ticket", { clearBreadcrumbs: true });
            };

            if (isDirty) {
                this.dialogService.add(ConfirmationDialog, {
                    title: _t("Discard changes?"),
                    body: _t("The changes you made will be lost. Do you want to discard them and go back?"),
                    confirmLabel: _t("Discard"),
                    cancelLabel: _t("Stay Here"),
                    confirm: goBack,
                    cancel: () => { },
                });
                return;
            }
            await goBack();
            return;
        }
        return super.discard(...arguments);
    }
}

export const serviceTicketFormView = {
    ...formView,
    Controller: ServiceTicketFormController,
};

registry.category("views").add("service_ticket_form", serviceTicketFormView);
