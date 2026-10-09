/** @odoo-module **/

import { Component, xml, useState, onMounted, onPatched, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Universal Dialog for Previewing Attached Documents (DOCX, Excel, ZIP, PDF, Images)
 */
export class UniversalAttachmentPreviewDialog extends Component {
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
                        <img t-att-src="imageSource" class="img-fluid p-3 shadow-sm rounded" style="max-height: 80vh; max-width: 100%; object-fit: contain; background: #fff;" alt="File Preview"/>
                    </div>
                </t>
                
                <!-- 2. PDF Viewer -->
                <t t-elif="isPdf">
                    <iframe t-att-src="pdfBlobUrl ? (pdfBlobUrl + '#toolbar=0&amp;navpanes=0') : ''" style="width: 100%; height: 80vh; border: none; background: #fff;" title="Document PDF"/>
                </t>

                <!-- 3. Word Document Preview (Rich HTML with Tables, Images & Formatting) -->
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

                <!-- 5. ZIP Archive Preview (Clean 2-Column List, No Horizontal Scroll) -->
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

                <!-- 6. Generic Fallback -->
                <t t-else="">
                    <div class="card border border-2 border-secondary border-opacity-25 bg-white text-dark p-4 mx-auto my-5 shadow-sm" style="max-width: 520px; border-radius: 12px;">
                        <div class="card-body text-center">
                            <div class="mb-3">
                                <i class="fa fa-file-text-o text-secondary" style="font-size: 4.5rem;"></i>
                            </div>
                            <h4 class="fw-bold mb-2 text-dark text-break" t-esc="props.filename || 'Attached Document'"/>
                            <p class="text-muted small mb-3">
                                <span class="badge bg-secondary px-2 py-1 me-1 text-uppercase" t-esc="fileExtension || 'DOCUMENT'"/>
                                <span>Attached File</span>
                            </p>
                        </div>
                    </div>
                </t>
            </div>
            <t t-set-slot="footer">
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
        close: { type: Function, optional: true },
    };

    get docxHtml() {
        if (this.props.previewContent?.type === "docx_content" || this.props.previewContent?.type === "docx") {
            return this.props.previewContent.html || null;
        }
        return null;
    }

    get excelSheets() {
        if (this.props.previewContent?.type === "excel_content" || this.props.previewContent?.type === "spreadsheet") {
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
        if (this.props.previewContent?.type === "zip_content" || this.props.previewContent?.type === "zip") {
            return this.props.previewContent.files;
        }
        return null;
    }

    get fileExtension() {
        const fn = (this.props.filename || "").toLowerCase();
        const parts = fn.split(".");
        return parts.length > 1 ? parts.pop() : "";
    }

    get isPdf() {
        return this.fileExtension === "pdf";
    }

    get isImage() {
        return ["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(this.fileExtension);
    }

    get isOffice() {
        return ["docx", "doc", "xlsx", "xls", "pptx", "ppt"].includes(this.fileExtension);
    }

    get isSpreadsheet() {
        return ["xlsx", "xls", "csv"].includes(this.fileExtension);
    }

    get isArchive() {
        return ["zip", "rar", "7z", "tar", "gz"].includes(this.fileExtension);
    }

    get pdfBlobUrl() {
        if (!this.props.fileData) return this.props.fileUrl;
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
            return this.props.fileUrl;
        }
    }

    get imageSource() {
        if (this.props.fileData && this.props.fileData.length > 50) {
            const ext = (this.fileExtension || "png").toLowerCase();
            const mime = ext === "svg" ? "svg+xml" : (ext === "jpg" ? "jpeg" : ext);
            return `data:image/${mime};base64,${this.props.fileData}`;
        }
        return this.props.fileUrl || "";
    }
}

/**
 * Universal Attachment Helpers (Reusable across any Form Controller)
 */
export const SUPPORTED_ATTACHMENT_EXTENSIONS = [
    "pdf", "png", "jpg", "jpeg", "webp", "gif", "bmp", "svg",
    "docx", "doc", "xlsx", "xls", "csv", "txt", "zip", "rar", "7z", "tar", "gz"
];

export function validateAttachmentExtension(filename, notificationService) {
    const ext = (filename || "").toLowerCase().split(".").pop();
    if (["exe", "bat", "cmd", "sh", "bin", "msi", "com", "scr", "vbs", "js", "py"].includes(ext)) {
        if (notificationService) {
            notificationService.add(
                _t("Executable files (.%s) are strictly prohibited for security reasons!").replace("%s", ext),
                { type: "danger", title: _t("File Upload Blocked") }
            );
        }
        return false;
    }
    if (!SUPPORTED_ATTACHMENT_EXTENSIONS.includes(ext)) {
        if (notificationService) {
            notificationService.add(
                _t("File format not supported! Only PDF, Images, Word (DOCX), Excel (XLSX, CSV), and Archives (ZIP, RAR) are allowed."),
                { type: "danger", title: _t("Invalid File Format") }
            );
        }
        return false;
    }
    return true;
}

/**
 * Sets up universal attachment listeners (validation, paste, preview) for any Form Controller.
 */
export function setupUniversalAttachmentHandling(controller, fieldConfigs) {
    const resModel = controller.props.resModel;

    // File cache to hold newly picked files immediately in memory before save
    const fileCache = new Map();

    // 1. File Input Validation & In-Memory Cache
    const handleFileInputChange = (e) => {
        const input = e.target;
        if (input.type === "file" && input.closest(".crm_invoice_field_box")) {
            const file = input.files && input.files[0];
            if (file) {
                if (!validateAttachmentExtension(file.name, controller.env.services.notification)) {
                    input.value = "";
                    e.preventDefault();
                    e.stopPropagation();
                    return;
                }
                // Read and cache file data immediately in browser memory
                const matchedConfig = fieldConfigs.find((cfg) => {
                    return input.closest(`[name="${cfg.dataField}"]`) || (cfg.boxSelector && input.closest(cfg.boxSelector));
                });
                const key = matchedConfig ? matchedConfig.dataField : "last_file";
                const reader = new FileReader();
                reader.onload = (loadEvt) => {
                    const b64 = loadEvt.target.result.split(",")[1];
                    fileCache.set(key, { data: b64, filename: file.name });
                };
                reader.readAsDataURL(file);
            }
        }
    };

    // 2. Clipboard Paste Handler
    const handlePasteAttachment = async (e) => {
        const target = e.target;
        const matchedConfig = fieldConfigs.find((cfg) => {
            return (
                target.closest(`[name="${cfg.dataField}"]`) ||
                (cfg.boxSelector && target.closest(cfg.boxSelector)) ||
                (target.closest(".crm_invoice_field_box") && target.closest(".crm_invoice_field_box").querySelector(`[name="${cfg.dataField}"]`))
            );
        });

        if (!matchedConfig) return;

        const clipboardData = e.clipboardData || window.clipboardData;
        if (!clipboardData || !clipboardData.items) return;

        for (let i = 0; i < clipboardData.items.length; i++) {
            const item = clipboardData.items[i];
            if (item.kind === "file") {
                const file = item.getAsFile();
                if (file) {
                    e.preventDefault();
                    if (!validateAttachmentExtension(file.name, controller.env.services.notification)) return;
                    const reader = new FileReader();
                    reader.onload = async (uploadEvent) => {
                        const base64Data = uploadEvent.target.result.split(",")[1];
                        const ext = file.type.split("/")[1] || "png";
                        const filename = file.name || `${matchedConfig.dataField}_pasted_${Date.now()}.${ext}`;
                        fileCache.set(matchedConfig.dataField, { data: base64Data, filename: filename });
                        if (controller.model?.root) {
                            const updateObj = {};
                            updateObj[matchedConfig.dataField] = base64Data;
                            if (matchedConfig.filenameField) {
                                updateObj[matchedConfig.filenameField] = filename;
                            }
                            await controller.model.root.update(updateObj);
                        }
                    };
                    reader.readAsDataURL(file);
                    break;
                }
            }
        }
    };

    // 3. Preview Button Click Handler
    const handlePreviewClick = async (e) => {
        const matchedConfig = fieldConfigs.find((cfg) => {
            return e.target.closest(`button[name="${cfg.buttonName}"]`);
        });

        if (!matchedConfig) return;

        e.preventDefault();
        e.stopPropagation();

        const record = controller.model?.root;

        // Auto-save any pending changes first so Odoo saves the file to server
        const isDirty = record?.isDirty ? await record.isDirty() : false;
        if (isDirty) {
            try {
                await record.save();
            } catch (saveErr) {
                console.warn("Could not auto-save before preview:", saveErr);
            }
        }

        const resId = record?.resId;
        let filename = record?.data?.[matchedConfig.filenameField];
        let fileData = record?.data?.[matchedConfig.dataField];

        // Check if cached from recent file input / paste
        const cached = fileCache.get(matchedConfig.dataField);
        if (cached && (!fileData || fileData.length < 50)) {
            fileData = cached.data;
            if (!filename) filename = cached.filename;
        }

        const isSizeString = typeof fileData === "string" && (
            fileData.includes("bytes") || fileData.includes("Kb") || fileData.includes("Mb") || fileData.length < 50
        );

        if (resId && (!fileData || !filename || isSizeString)) {
            try {
                const readFields = [matchedConfig.dataField];
                if (matchedConfig.filenameField) readFields.push(matchedConfig.filenameField);
                const fetchedList = await controller.env.services.orm.read(
                    resModel,
                    [resId],
                    readFields,
                    { context: { bin_size: false } }
                );
                if (fetchedList && fetchedList.length > 0) {
                    fileData = fetchedList[0][matchedConfig.dataField];
                    if (matchedConfig.filenameField && !filename) {
                        filename = fetchedList[0][matchedConfig.filenameField];
                    }
                }
            } catch (err) {
                console.error(`Error reading ${matchedConfig.dataField}:`, err);
            }
        }

        filename = filename || "document.pdf";

        if (resId || fileData) {
            let previewContent = null;
            const isDocOrZipOrExcel = ["docx", "doc", "zip", "rar", "7z", "tar", "gz", "xlsx", "xls", "csv"].some((ext) =>
                (filename || "").toLowerCase().endsWith("." + ext)
            );

            if (isDocOrZipOrExcel) {
                try {
                    previewContent = await controller.env.services.orm.call(
                        "equipment.master",
                        "action_get_invoice_preview_content",
                        [false, fileData || false, filename || false],
                        {}
                    );
                } catch (callErr) {
                    console.error("Error retrieving preview content:", callErr);
                }
            }

            const url = resId ? `/web/content/${resModel}/${resId}/${matchedConfig.dataField}/${filename}?download=false` : null;
            controller.dialogService.add(UniversalAttachmentPreviewDialog, {
                title: matchedConfig.title || _t("Document Preview"),
                fileUrl: url,
                fileData: fileData,
                filename: filename,
                previewContent: previewContent,
            });
        }
    };

    document.addEventListener("change", handleFileInputChange, true);
    document.addEventListener("paste", handlePasteAttachment);
    document.addEventListener("click", handlePreviewClick, true);

    return () => {
        document.removeEventListener("change", handleFileInputChange, true);
        document.removeEventListener("paste", handlePasteAttachment);
        document.removeEventListener("click", handlePreviewClick, true);
    };
}
