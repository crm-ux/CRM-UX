/** @odoo-module **/

import { Component, xml, onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
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
        this.docxContainerRef = useRef("docxContainer");
        const injectHtml = () => {
            if (this.docxContainerRef?.el && this.docxHtml) {
                this.docxContainerRef.el.innerHTML = this.docxHtml;
            }
        };
        onMounted(injectHtml);
        onPatched(injectHtml);
    }

    static template = xml`
        <Dialog title="props.title" size="'xl'">
            <div class="p-0 bg-light" style="min-height: 75vh; max-height: 85vh; overflow-y: auto; display: flex; flex-direction: column; align-items: center; justify-content: flex-start;">
                <!-- 1. Image Viewer -->
                <t t-if="isImage">
                    <div class="w-100 h-100 d-flex align-items-center justify-content-center p-3">
                        <img t-att-src="imageSource" class="img-fluid p-3 shadow-sm rounded" style="max-height: 80vh; max-width: 100%; object-fit: contain; background: #fff;" alt="Invoice Preview"/>
                    </div>
                </t>
                
                <!-- 2. PDF Viewer -->
                <t t-elif="isPdf">
                    <iframe t-att-src="pdfBlobUrl" style="width: 100%; height: 80vh; border: none; background: #fff;" title="Invoice PDF"/>
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

                <!-- 4. ZIP Archive Content Preview (Scrollable File List) -->
                <t t-elif="isArchive and zipFiles">
                    <div class="w-100 p-4" style="max-width: 850px;">
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
                            
                            <!-- Scrollable file table -->
                            <div class="table-responsive border rounded" style="max-height: 60vh; overflow-y: auto;">
                                <table class="table table-hover table-striped mb-0 text-start align-middle">
                                    <thead class="table-light sticky-top">
                                        <tr>
                                            <th style="width: 40px;">#</th>
                                            <th>File Name</th>
                                            <th class="text-end" style="width: 120px;">Size</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <t t-foreach="zipFiles" t-as="file" t-key="file_index">
                                            <tr>
                                                <td class="text-muted small" t-esc="file_index + 1"/>
                                                <td>
                                                    <t t-if="file.is_dir">
                                                        <i class="fa fa-folder text-warning me-2"></i>
                                                    </t>
                                                    <t t-else="">
                                                        <i class="fa fa-file-text-o text-secondary me-2"></i>
                                                    </t>
                                                    <span class="font-monospace" t-esc="file.name"/>
                                                </td>
                                                <td class="text-end text-muted small">
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

    get zipFiles() {
        if (this.props.previewContent?.type === "zip_content") {
            return this.props.previewContent.files;
        }
        return null;
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

            onMounted(() => {
                reorderToolbar();
                const panel = document.querySelector(".o_control_panel_breadcrumbs");
                if (panel) {
                    observer = new MutationObserver(() => reorderToolbar());
                    observer.observe(panel, { childList: true });
                }
                // Auto-scroll when clicking on warranty dates
                const scrollForDate = (e) => {
                    const fieldDiv = e.target.closest('[name="warranty_end_date"], [name="warranty_start_date"]');
                    if (fieldDiv) {
                        setTimeout(() => {
                            // Find whichever element is currently scrolling
                            const scroller = document.querySelector(".o_content") || document.querySelector(".o_form_view") || document.documentElement;
                            if (scroller) {
                                scroller.scrollBy({ top: 260, behavior: "smooth" });
                            }
                        }, 100);
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

                // Intercept Preview Invoice click to open In-Page Dialog (without download/close footer)
                const handlePreviewClick = async (e) => {
                    const btn = e.target.closest('button[name="action_preview_invoice"]');
                    if (btn) {
                        e.preventDefault();
                        e.stopPropagation();
                        const record = this.model?.root;
                        const resId = record?.resId;
                        const filename = record?.data?.invoice_filename || "invoice.pdf";
                        let fileData = record?.data?.invoice_attachment;

                        // If fileData is not loaded in current record cache, read directly via ORM
                        if (!fileData && resId) {
                            try {
                                const [fetched] = await this.env.services.orm.read(
                                    "equipment.master",
                                    [resId],
                                    ["invoice_attachment", "invoice_filename"]
                                );
                                if (fetched) {
                                    fileData = fetched.invoice_attachment;
                                }
                            } catch (err) {
                                console.error("Error reading invoice_attachment:", err);
                            }
                        }

                        if (resId || fileData) {
                            let previewContent = null;
                            const isDocOrZip = ["docx", "doc", "zip", "rar", "7z", "tar", "gz"].some((e) =>
                                (filename || "").toLowerCase().endsWith("." + e)
                            );

                            if (isDocOrZip) {
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

                document.addEventListener("click", scrollForDate);
                document.addEventListener("focusin", scrollForDate);
                document.addEventListener("paste", handlePasteInvoice);
                document.addEventListener("click", handlePreviewClick, true);
            });

            onWillUnmount(() => {
                if (observer) observer.disconnect();
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
