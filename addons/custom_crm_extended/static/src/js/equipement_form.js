/** @odoo-module **/

import { Component, xml, useState, onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

class InvoicePreviewDialog extends Component {
    setup() {
        this.state = useState({
            activeSheetIndex: 0,
        });
        this.docxContainerRef = useRef("docxContainer");
        const injectHtml = () => {
            if (this.docxContainerRef?.el && this.docxHtml) {
                this.docxContainerRef.el.innerHTML = this.docxHtml;
            }
        };
        onMounted(injectHtml);
        onPatched(injectHtml);
    }

    setActiveSheet(index) {
        this.state.activeSheetIndex = index;
    }

    static template = xml`
        <Dialog title="props.title" size="'xl'">
            <div class="p-0 bg-light crm-invoice-preview-container" style="height: 82vh; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; overflow: hidden;">
                <!-- 1. Image Viewer -->
                <t t-if="isImage">
                    <div class="w-100 h-100 d-flex align-items-center justify-content-center p-3">
                        <img t-att-src="imageSource" class="img-fluid p-3 shadow-sm rounded" style="max-height: 80vh; max-width: 100%; object-fit: contain; background: #fff;" alt="Invoice Preview"/>
                    </div>
                </t>
                
                <!-- 2. PDF Viewer -->
                <t t-elif="isPdf">
                    <iframe t-att-src="pdfBlobUrl ? (pdfBlobUrl + '#toolbar=0&amp;navpanes=0') : ''" style="width: 100%; height: 80vh; border: none; background: #fff;" title="Invoice PDF"/>
                </t>

                <!-- 3. Word Document Content Preview (Rich HTML with Tables, Images & Formatting) -->
                <t t-elif="isOffice and docxHtml">
                    <div class="w-100 p-3 p-md-4" style="max-width: 900px;">
                        <div class="card shadow-sm border-0 bg-white p-4 p-md-5 my-2" style="border-radius: 10px;">
                            <div class="border-bottom pb-3 mb-4 d-flex align-items-center justify-content-between">
                                <div class="d-flex align-items-center gap-3">
                                    <div class="d-flex align-items-center justify-content-center rounded" style="width: 42px; height: 42px; background: #e8f0fe; color: #1a73e8;">
                                        <i class="fa fa-file-word-o fs-4"></i>
                                    </div>
                                    <div>
                                        <h5 class="fw-bold mb-0 text-dark" t-esc="props.filename"/>
                                        <small class="text-muted">Document Preview</small>
                                    </div>
                                </div>
                                <span class="badge px-3 py-2 fw-semibold" style="background-color: #0b3d91 !important; color: #ffffff !important; border-radius: 6px;">
                                    DOCX
                                </span>
                            </div>
                            <div t-ref="docxContainer" class="docx-body text-start border rounded p-4 bg-white" style="max-height: 68vh; overflow-y: auto; overflow-x: auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14.5px; line-height: 1.6; color: #202124;"/>
                        </div>
                    </div>
                </t>

                <!-- 4. Excel / Spreadsheet Preview (Scrollable Grid with Sheet Tabs) -->
                <t t-elif="isSpreadsheet and excelSheets">
                    <div class="w-100 p-2 p-md-3 d-flex flex-column" style="max-width: 1100px; height: 100%; overflow: hidden;">
                        <div class="card shadow-sm border-0 bg-white p-3 my-1 d-flex flex-column flex-grow-1" style="border-radius: 10px; overflow: hidden;">
                            <div class="border-bottom pb-2 mb-2 d-flex align-items-center justify-content-between flex-shrink-0">
                                <div class="d-flex align-items-center gap-3">
                                    <div class="d-flex align-items-center justify-content-center rounded" style="width: 38px; height: 38px; background: #e6f4ea; color: #137333;">
                                        <i class="fa fa-file-excel-o fs-5"></i>
                                    </div>
                                    <div>
                                        <h6 class="fw-bold mb-0 text-dark" t-esc="props.filename"/>
                                        <small class="text-muted"><t t-esc="excelSheets.length"/> Sheet(s) Available</small>
                                    </div>
                                </div>
                                <span class="badge px-3 py-1 fw-semibold" style="background-color: #137333 !important; color: #ffffff !important; border-radius: 6px;">
                                    EXCEL
                                </span>
                            </div>

                            <!-- Sheet Tabs if multiple sheets -->
                            <t t-if="excelSheets.length > 1">
                                <ul class="nav nav-tabs mb-2 flex-shrink-0">
                                    <t t-foreach="excelSheets" t-as="sheet" t-key="sheet_index">
                                        <li class="nav-item">
                                            <button type="button" class="nav-link py-1 px-3 small" t-att-class="{'active fw-bold': state.activeSheetIndex === sheet_index}" t-on-click="() => this.setActiveSheet(sheet_index)">
                                                <i class="fa fa-table me-1"></i><t t-esc="sheet.name"/>
                                            </button>
                                        </li>
                                    </t>
                                </ul>
                            </t>

                            <!-- Single Scrollable Spreadsheet Grid -->
                            <div class="table-responsive border rounded flex-grow-1" style="overflow-y: auto; overflow-x: auto; background: #fafafa; min-height: 200px;">
                                <table class="table table-bordered table-sm table-hover mb-0 text-dark align-middle" style="font-size: 13px;">
                                    <t t-if="activeSheetRows and activeSheetRows.length">
                                        <thead class="table-light sticky-top" style="z-index: 2;">
                                            <tr>
                                                <th class="text-center bg-light text-muted" style="width: 45px; border-color: #dee2e6;">#</th>
                                                <t t-foreach="activeSheetRows[0]" t-as="col" t-key="col_index">
                                                    <th class="fw-bold text-nowrap px-3 py-2 bg-light border" style="border-color: #dee2e6;" t-esc="col"/>
                                                </t>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <t t-foreach="activeSheetRows.slice(1)" t-as="row" t-key="row_index">
                                                <tr>
                                                    <td class="text-center text-muted small bg-light" t-esc="row_index + 1"/>
                                                    <t t-foreach="row" t-as="cell" t-key="cell_index">
                                                        <td class="px-3 py-1 text-nowrap border" style="border-color: #dee2e6;" t-esc="cell"/>
                                                    </t>
                                                </tr>
                                            </t>
                                        </tbody>
                                    </t>
                                    <t t-else="">
                                        <tbody>
                                            <tr>
                                                <td class="text-center text-muted py-4">No data found in this sheet.</td>
                                            </tr>
                                        </tbody>
                                    </t>
                                </table>
                            </div>
                        </div>
                    </div>
                </t>

                <!-- 5. ZIP Archive Content Preview (Clean 2-Column List, No Horizontal Scroll) -->
                <t t-elif="isArchive and zipFiles">
                    <div class="w-100 p-3 p-md-4" style="max-width: 850px;">
                        <div class="card shadow-sm border-0 bg-white p-4 my-2" style="border-radius: 8px;">
                            <div class="border-bottom pb-3 mb-3 d-flex align-items-center justify-content-between">
                                <div class="d-flex align-items-center gap-2">
                                    <i class="fa fa-file-archive-o text-warning fs-3"></i>
                                    <div>
                                        <h5 class="fw-bold mb-0 text-dark" t-esc="props.filename"/>
                                        <small class="text-muted"><t t-esc="zipFiles.length"/> Files inside package</small>
                                    </div>
                                </div>
                                <span class="badge bg-warning bg-opacity-25 text-dark px-3 py-2">ZIP ARCHIVE</span>
                            </div>
                            
                            <!-- Clean 2-Column Table, No Horizontal Scroll -->
                            <div class="border rounded" style="max-height: 60vh; overflow-y: auto; overflow-x: hidden;">
                                <table class="table table-hover table-striped mb-0 text-start align-middle" style="table-layout: fixed; width: 100%;">
                                    <thead class="table-light sticky-top">
                                        <tr>
                                            <th>File Name</th>
                                            <th class="text-end" style="width: 100px;">Size</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <t t-foreach="zipFiles" t-as="file" t-key="file_index">
                                            <tr>
                                                <td class="text-truncate" style="max-width: 100%;" t-att-title="file.name">
                                                    <t t-if="file.is_dir">
                                                        <i class="fa fa-folder text-warning me-2"></i>
                                                    </t>
                                                    <t t-else="">
                                                        <i class="fa fa-file-text-o text-secondary me-2"></i>
                                                    </t>
                                                    <span class="font-monospace text-truncate" t-esc="file.name"/>
                                                </td>
                                                <td class="text-end text-muted small text-nowrap">
                                                    <t t-if="file.is_dir">
                                                        <span class="badge bg-light text-muted">Folder</span>
                                                    </t>
                                                    <t t-else="">
                                                        <span t-esc="file.size"/> KB
                                                    </t>
                                                </td>
                                            </tr>
                                        </t>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </t>

                <!-- 5. Fallback -->
                <t t-else="">
                    <div class="card border border-2 border-secondary border-opacity-25 bg-white text-dark p-4 mx-auto my-5 shadow-sm" style="max-width: 520px; border-radius: 12px;">
                        <div class="card-body text-center">
                            <div class="mb-3">
                                <i class="fa fa-file-text-o text-secondary" style="font-size: 4.5rem;"></i>
                            </div>
                            <h4 class="fw-bold mb-2 text-dark text-break" t-esc="props.filename || 'Attached Invoice'"/>
                            <p class="text-muted small mb-3">
                                <span class="badge bg-secondary px-2 py-1 me-1 text-uppercase" t-esc="fileExtension || 'DOCUMENT'"/>
                                <span>Attached to Equipment Record</span>
                            </p>
                        </div>
                    </div>
                </t>
            </div>
            <t t-set-slot="footer">
                <!-- No download button and no extra close button - only top-right cross icon [X] -->
            </t>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        fileUrl: { type: String, optional: true },
        fileData: { type: String, optional: true },
        filename: { type: String, optional: true },
        previewContent: { type: Object, optional: true },
        close: { type: Function },
    };

    get docxHtml() {
        if (this.props.previewContent?.type === "docx_content") {
            return this.props.previewContent.html || null;
        }
        return null;
    }

    get excelSheets() {
        if (this.props.previewContent?.type === "excel_content") {
            return this.props.previewContent.sheets || [];
        }
        return [];
    }

    get activeSheetRows() {
        const sheets = this.excelSheets;
        if (sheets.length > 0) {
            const idx = Math.min(this.state.activeSheetIndex, sheets.length - 1);
            return sheets[idx]?.rows || [];
        }
        return [];
    }

    get zipFiles() {
        if (this.props.previewContent?.type === "zip_content") {
            return this.props.previewContent.files;
        }
        return null;
    }

    get isSpreadsheet() {
        return ["xlsx", "xls", "csv"].includes(this.fileExtension);
    }

    get fileExtension() {
        const fn = (this.props.filename || "").toLowerCase();
        const parts = fn.split(".");
        return parts.length > 1 ? parts.pop() : "";
    }

    get isImage() {
        return ["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(this.fileExtension);
    }

    get isPdf() {
        return this.fileExtension === "pdf";
    }

    get isOffice() {
        return ["docx", "doc", "xlsx", "xls", "pptx", "ppt"].includes(this.fileExtension);
    }

    get isArchive() {
        return ["zip", "rar", "7z", "tar", "gz"].includes(this.fileExtension);
    }

    get imageSource() {
        if (this.props.fileData) {
            const ext = this.fileExtension || "png";
            return `data:image/${ext === "svg" ? "svg+xml" : ext};base64,${this.props.fileData}`;
        }
        return this.props.fileUrl;
    }

    get pdfBlobUrl() {
        if (this.props.fileData) {
            try {
                const byteCharacters = atob(this.props.fileData);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: "application/pdf" });
                return URL.createObjectURL(blob);
            } catch (e) {
                console.error("Error creating PDF blob URL:", e);
            }
        }
        return this.props.fileUrl;
    }
}

const EQUIPMENT_MODEL = "equipment.master";
const WIZARD_ACTION = "custom_crm_extended.action_equipment_master_wizard";

async function openEquipmentWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

// 1. Intercept "New" button in List View
patch(ListController.prototype, {
    async createRecord() {
        if (
            this.model?.root?.resModel === EQUIPMENT_MODEL ||
            this.props?.resModel === EQUIPMENT_MODEL
        ) {
            await openEquipmentWizard(this.env);
            return;
        }
        return super.createRecord(...arguments);
    },
    async openNewRecord() {
        if (
            this.model?.root?.resModel === EQUIPMENT_MODEL ||
            this.props?.resModel === EQUIPMENT_MODEL
        ) {
            await openEquipmentWizard(this.env);
            return;
        }
        return super.openNewRecord(...arguments);
    },
});

// 2. Intercept "New" button in Detail Form View
patch(FormController.prototype, {
    async create() {
        if (
            this.props?.resModel === EQUIPMENT_MODEL ||
            this.model?.root?.resModel === EQUIPMENT_MODEL
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
            await openEquipmentWizard(this.env);
            return;
        }
        return super.create(...arguments);
    },
});

export class EquipmentFormController extends FormController {
    setup() {
        super.setup();
        if (this.props.resModel === "equipment.master") {
            let observer = null;
            const reorderToolbar = () => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (container && breadcrumb && statusIndicator) {
                    if (breadcrumb.previousElementSibling !== statusIndicator) {
                        container.insertBefore(breadcrumb, statusIndicator.nextSibling);
                    }
                }
            };

            // Auto-scroll when clicking on warranty dates
            const scrollForDate = (e) => {
                const fieldDiv = e.target.closest('[name="warranty_end_date"], [name="warranty_start_date"]');
                if (fieldDiv) {
                    setTimeout(() => {
                        const scroller = document.querySelector(".o_content") || document.querySelector(".o_form_view") || document.documentElement;
                        if (scroller) {
                            scroller.scrollBy({ top: 260, behavior: "smooth" });
                        }
                    }, 100);
                }
            };

            const SUPPORTED_EXTS = ["pdf", "png", "jpg", "jpeg", "webp", "gif", "bmp", "svg", "docx", "doc", "xlsx", "xls", "csv", "txt", "zip", "rar", "7z", "tar", "gz"];

            const validateInvoiceFile = (filename) => {
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

            // Intercept file input change in browser directly to block prohibited files immediately
            const handleFileInputChange = (e) => {
                const input = e.target;
                if (input.type === "file" && input.closest(".crm_invoice_field_box")) {
                    const file = input.files && input.files[0];
                    if (file && !validateInvoiceFile(file.name)) {
                        input.value = ""; // Clear file immediately
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }
            };

            // Clipboard Paste Handler: Paste image or document directly
            const handlePasteInvoice = async (e) => {
                const target = e.target;
                const invoiceBox = target.closest('.crm_invoice_field_box') || target.closest('[name="invoice_number"]');
                if (!invoiceBox) return;

                const clipboardData = e.clipboardData || window.clipboardData;
                if (!clipboardData || !clipboardData.items) return;

                for (let i = 0; i < clipboardData.items.length; i++) {
                    const item = clipboardData.items[i];
                    if (item.kind === "file") {
                        const file = item.getAsFile();
                        if (file) {
                            e.preventDefault();
                            if (!validateInvoiceFile(file.name)) return;
                            const reader = new FileReader();
                            reader.onload = async (uploadEvent) => {
                                const base64Data = uploadEvent.target.result.split(",")[1];
                                let filename = file.name || `invoice_pasted_${Date.now()}.${file.type.split("/")[1] || "png"}`;
                                if (this.model?.root) {
                                    await this.model.root.update({
                                        invoice_attachment: base64Data,
                                        invoice_filename: filename,
                                    });
                                }
                            };
                            reader.readAsDataURL(file);
                            break;
                        }
                    }
                }
            };

            // Intercept Preview Invoice click to open In-Page Dialog
            const handlePreviewClick = async (e) => {
                const btn = e.target.closest('button[name="action_preview_invoice"]');
                if (btn) {
                    e.preventDefault();
                    e.stopPropagation();
                    const record = this.model?.root;
                    let resId = record?.resId;
                    let filename = record?.data?.invoice_filename;
                    let fileData = record?.data?.invoice_attachment;

                    // On a saved record, binary data must be explicitly loaded with bin_size: false
                    if (resId && (!fileData || !filename)) {
                        try {
                            const fetchedList = await this.env.services.orm.read(
                                "equipment.master",
                                [resId],
                                ["invoice_attachment", "invoice_filename"],
                                { context: { bin_size: false } }
                            );
                            if (fetchedList && fetchedList.length > 0) {
                                if (!fileData) fileData = fetchedList[0].invoice_attachment;
                                if (!filename) filename = fetchedList[0].invoice_filename;
                            }
                        } catch (err) {
                            console.error("Error reading invoice_attachment:", err);
                        }
                    }

                    filename = filename || "invoice.pdf";

                    if (resId || fileData) {
                        let previewContent = null;
                        const isDocOrZipOrExcel = ["docx", "doc", "zip", "rar", "7z", "tar", "gz", "xlsx", "xls", "csv"].some((ext) =>
                            (filename || "").toLowerCase().endsWith("." + ext)
                        );

                        if (isDocOrZipOrExcel) {
                            try {
                                previewContent = await this.env.services.orm.call(
                                    "equipment.master",
                                    "action_get_invoice_preview_content",
                                    [],
                                    {
                                        res_id: resId || null,
                                        raw_b64: fileData || null,
                                        filename: filename,
                                    }
                                );
                            } catch (callErr) {
                                console.error("Error retrieving preview content:", callErr);
                            }
                        }

                        const url = resId ? `/web/content/equipment.master/${resId}/invoice_attachment/${filename}?download=false` : null;
                        this.dialogService.add(InvoicePreviewDialog, {
                            title: _t("Invoice Preview"),
                            fileUrl: url,
                            fileData: fileData,
                            filename: filename,
                            previewContent: previewContent,
                        });
                    }
                }
            };

            onMounted(() => {
                reorderToolbar();
                const panel = document.querySelector(".o_control_panel_breadcrumbs");
                if (panel) {
                    observer = new MutationObserver(() => reorderToolbar());
                    observer.observe(panel, { childList: true });
                }

                document.addEventListener("click", scrollForDate);
                document.addEventListener("focusin", scrollForDate);
                document.addEventListener("change", handleFileInputChange, true);
                document.addEventListener("paste", handlePasteInvoice);
                document.addEventListener("click", handlePreviewClick, true);
            });

            onWillUnmount(() => {
                if (observer) observer.disconnect();
                document.removeEventListener("click", scrollForDate);
                document.removeEventListener("focusin", scrollForDate);
                document.removeEventListener("change", handleFileInputChange, true);
                document.removeEventListener("paste", handlePasteInvoice);
                document.removeEventListener("click", handlePreviewClick, true);
            });
        }
    }

    async discard() {
        if (this.props.resModel === "equipment.master") {
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
                this.actionService.doAction("custom_crm_extended.action_equipment_master", { clearBreadcrumbs: true });
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

export const equipmentFormView = {
    ...formView,
    Controller: EquipmentFormController,
};

registry.category("views").add("equipment_form", equipmentFormView);
