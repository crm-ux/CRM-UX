/** @odoo-module **/

import { onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { InvoicePreviewDialog } from "./equipement_form";

export class AmcFormController extends FormController {
    setup() {
        super.setup();

        let interval = null;

        const SUPPORTED_EXTS = ["pdf", "png", "jpg", "jpeg", "webp", "gif", "bmp", "svg", "docx", "doc", "xlsx", "xls", "csv", "txt", "zip", "rar", "7z", "tar", "gz"];

        const validateAttachmentFile = (filename) => {
            const ext = (filename || "").toLowerCase().split(".").pop();
            if (["exe", "bat", "cmd", "sh", "bin", "msi", "com", "scr", "vbs", "js", "py"].includes(ext)) {
                this.env.services.notification.add(
                    _t("Executable files (.%s) are strictly prohibited for security reasons!").replace("%s", ext),
                    { type: "danger", title: _t("File Upload Blocked") }
                );
                return false;
            }
            if (!SUPPORTED_EXTS.includes(ext)) {
                this.env.services.notification.add(
                    _t("File format not supported! Only PDF, Images, Word (DOCX), Excel (XLSX, CSV), and Archives (ZIP, RAR) are allowed."),
                    { type: "danger", title: _t("Invalid File Format") }
                );
                return false;
            }
            return true;
        };

        // File input validation
        const handleFileInputChange = (e) => {
            const input = e.target;
            if (input.type === "file" && input.closest(".crm_invoice_field_box")) {
                const file = input.files && input.files[0];
                if (file && !validateAttachmentFile(file.name)) {
                    input.value = "";
                    e.preventDefault();
                    e.stopPropagation();
                }
            }
        };

        // Clipboard Paste: Paste into PO or Invoice box
        const handlePasteAttachment = async (e) => {
            const target = e.target;
            const poBox = target.closest('[name="po_number"]') || (target.closest('.crm_invoice_field_box') && target.closest('.crm_invoice_field_box').querySelector('[name="po_attachment"]'));
            const invBox = target.closest('[name="invoice_number"]') || (target.closest('.crm_invoice_field_box') && target.closest('.crm_invoice_field_box').querySelector('[name="invoice_attachment"]'));
            
            if (!poBox && !invBox) return;

            const clipboardData = e.clipboardData || window.clipboardData;
            if (!clipboardData || !clipboardData.items) return;

            for (let i = 0; i < clipboardData.items.length; i++) {
                const item = clipboardData.items[i];
                if (item.kind === "file") {
                    const file = item.getAsFile();
                    if (file) {
                        e.preventDefault();
                        if (!validateAttachmentFile(file.name)) return;
                        const reader = new FileReader();
                        reader.onload = async (uploadEvent) => {
                            const base64Data = uploadEvent.target.result.split(",")[1];
                            const ext = file.type.split("/")[1] || "png";
                            if (this.model?.root) {
                                if (poBox) {
                                    await this.model.root.update({
                                        po_attachment: base64Data,
                                        po_filename: file.name || `po_pasted_${Date.now()}.${ext}`,
                                    });
                                } else {
                                    await this.model.root.update({
                                        invoice_attachment: base64Data,
                                        invoice_filename: file.name || `invoice_pasted_${Date.now()}.${ext}`,
                                    });
                                }
                            }
                        };
                        reader.readAsDataURL(file);
                        break;
                    }
                }
            }
        };

        // Intercept Preview PO or Preview Invoice button click
        const handlePreviewClick = async (e) => {
            const btnPo = e.target.closest('button[name="action_preview_amc_po"]');
            const btnInv = e.target.closest('button[name="action_preview_amc_invoice"]');
            
            if (!btnPo && !btnInv) return;

            e.preventDefault();
            e.stopPropagation();

            const isPo = Boolean(btnPo);
            const record = this.model?.root;
            const resId = record?.resId;

            const fieldDataName = isPo ? "po_attachment" : "invoice_attachment";
            const fieldFileName = isPo ? "po_filename" : "invoice_filename";
            const title = isPo ? _t("PO Preview") : _t("Invoice Preview");

            let filename = record?.data?.[fieldFileName];
            let fileData = record?.data?.[fieldDataName];

            const isSizeString = typeof fileData === "string" && (fileData.includes("bytes") || fileData.includes("Kb") || fileData.includes("Mb") || fileData.length < 50);

            // Fetch real raw base64 if needed
            if (resId && (!fileData || !filename || isSizeString)) {
                try {
                    const fetchedList = await this.env.services.orm.read(
                        "amc.contract",
                        [resId],
                        [fieldDataName, fieldFileName],
                        { context: { bin_size: false } }
                    );
                    if (fetchedList && fetchedList.length > 0) {
                        fileData = fetchedList[0][fieldDataName];
                        if (!filename) filename = fetchedList[0][fieldFileName];
                    }
                } catch (err) {
                    console.error(`Error reading ${fieldDataName}:`, err);
                }
            }

            filename = filename || (isPo ? "po_document.pdf" : "invoice.pdf");

            if (resId || fileData) {
                let previewContent = null;
                const isDocOrZipOrExcel = ["docx", "doc", "zip", "rar", "7z", "tar", "gz", "xlsx", "xls", "csv"].some((ext) =>
                    (filename || "").toLowerCase().endsWith("." + ext)
                );

                if (isDocOrZipOrExcel) {
                    try {
                        previewContent = await this.env.services.orm.call(
                            "amc.contract",
                            "action_get_amc_preview_content",
                            [resId || false, fileData || false, filename || false, fieldDataName],
                            {}
                        );
                    } catch (callErr) {
                        console.error("Error retrieving AMC preview content:", callErr);
                    }
                }

                const url = resId ? `/web/content/amc.contract/${resId}/${fieldDataName}/${filename}?download=false` : null;
                this.dialogService.add(InvoicePreviewDialog, {
                    title: title,
                    fileUrl: url,
                    fileData: fileData,
                    filename: filename,
                    previewContent: previewContent,
                });
            }
        };

        onMounted(() => {
            interval = setInterval(() => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (container && breadcrumb && statusIndicator) {
                    if (breadcrumb.previousElementSibling !== statusIndicator) {
                        container.insertBefore(breadcrumb, statusIndicator.nextSibling);
                    }
                    statusIndicator.classList.remove("me-auto");
                    statusIndicator.style.removeProperty("margin-right");
                    breadcrumb.style.removeProperty("margin-left");
                }
            }, 100);

            document.addEventListener("change", handleFileInputChange, true);
            document.addEventListener("paste", handlePasteAttachment);
            document.addEventListener("click", handlePreviewClick, true);
        });

        onWillUnmount(() => {
            if (interval) {
                clearInterval(interval);
            }
            document.removeEventListener("change", handleFileInputChange, true);
            document.removeEventListener("paste", handlePasteAttachment);
            document.removeEventListener("click", handlePreviewClick, true);
        });
    }
}

export const amcFormView = {
    ...formView,
    Controller: AmcFormController,
};

registry.category("views").add("amc_form", amcFormView);

