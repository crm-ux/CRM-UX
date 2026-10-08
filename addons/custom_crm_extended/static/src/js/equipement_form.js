/** @odoo-module **/

import { Component, xml, onMounted, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";

class InvoicePreviewDialog extends Component {
    static template = xml`
        <Dialog title="props.title" size="'xl'">
            <div class="p-0 text-center" style="background-color: #1e1e1e; min-height: 75vh; max-height: 85vh; overflow: auto; display: flex; align-items: center; justify-content: center;">
                <!-- 1. Image Viewer -->
                <t t-if="isImage">
                    <img t-att-src="fileSource" class="img-fluid p-2" style="max-height: 80vh; max-width: 100%; object-fit: contain; border-radius: 6px;" alt="Invoice Preview"/>
                </t>
                
                <!-- 2. PDF Viewer (Native PDF Viewer in iframe with data URL / object) -->
                <t t-elif="isPdf">
                    <object t-att-data="fileSource" type="application/pdf" style="width: 100%; height: 80vh; border: none;">
                        <iframe t-att-src="fileSource" style="width: 100%; height: 80vh; border: none;" title="Invoice PDF"/>
                    </object>
                </t>

                <!-- 3. ZIP / Archive / Other Documents (Clean Modern Inspector Card - 0 Download) -->
                <t t-else="">
                    <div class="card border-0 text-white p-4 mx-auto my-5 shadow-lg" style="background-color: #2b2b2b; max-width: 520px; border-radius: 12px;">
                        <div class="card-body text-center">
                            <div class="mb-3">
                                <t t-if="isArchive">
                                    <i class="fa fa-file-archive-o text-warning" style="font-size: 4.5rem;"></i>
                                </t>
                                <t t-elif="isOffice">
                                    <i class="fa fa-file-word-o text-primary" style="font-size: 4.5rem;"></i>
                                </t>
                                <t t-else="">
                                    <i class="fa fa-file-text-o text-info" style="font-size: 4.5rem;"></i>
                                </t>
                            </div>
                            <h4 class="fw-bold mb-2 text-break" t-esc="props.filename || 'Attached Invoice'"/>
                            <p class="text-white-50 small mb-3">
                                <span class="badge bg-secondary px-2 py-1 me-1 text-uppercase" t-esc="fileExtension || 'DOCUMENT'"/>
                                <span>Attached to Equipment Record</span>
                            </p>
                            <div class="alert alert-secondary text-white-50 small border-0 mb-0 py-2" style="background-color: #383838;">
                                <i class="fa fa-shield me-1 text-success"></i>
                                <span>File is securely attached and stored in the database.</span>
                            </div>
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
        close: { type: Function },
    };

    get fileExtension() {
        const fn = (this.props.filename || "").toLowerCase();
        const parts = fn.split(".");
        return parts.length > 1 ? parts.pop() : "";
    }

    get mimeType() {
        const ext = this.fileExtension;
        const mimeMap = {
            pdf: "application/pdf",
            png: "image/png",
            jpg: "image/jpeg",
            jpeg: "image/jpeg",
            webp: "image/webp",
            gif: "image/gif",
            bmp: "image/bmp",
            svg: "image/svg+xml",
        };
        return mimeMap[ext] || "application/octet-stream";
    }

    get fileSource() {
        if (this.props.fileData) {
            // Raw base64 data URI
            return `data:${this.mimeType};base64,${this.props.fileData}`;
        }
        return this.props.fileUrl;
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
                            const url = resId ? `/web/content/equipment.master/${resId}/invoice_attachment/${filename}?download=false` : null;
                            this.dialogService.add(InvoicePreviewDialog, {
                                title: _t("Invoice Preview"),
                                fileUrl: url,
                                fileData: fileData,
                                filename: filename,
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
