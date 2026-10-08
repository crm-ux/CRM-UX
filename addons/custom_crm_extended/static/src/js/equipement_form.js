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
            <div class="p-0 text-center bg-dark" style="min-height: 75vh; max-height: 85vh; overflow: hidden; display: flex; align-items: center; justify-content: center;">
                <t t-if="isImage">
                    <img t-att-src="props.fileUrl" class="img-fluid" style="max-height: 80vh; object-fit: contain; border-radius: 4px;" alt="Invoice Preview"/>
                </t>
                <t t-else="">
                    <iframe t-att-src="props.fileUrl" style="width: 100%; height: 80vh; border: none;" title="Invoice Document"/>
                </t>
            </div>
            <t t-set-slot="footer">
                <!-- No download button and no extra close button - only top-right cross icon -->
            </t>
        </Dialog>
    `;
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        fileUrl: { type: String },
        filename: { type: String, optional: true },
        close: { type: Function },
    };

    get isImage() {
        const fn = (this.props.filename || "").toLowerCase();
        return fn.endsWith(".png") || fn.endsWith(".jpg") || fn.endsWith(".jpeg") || fn.endsWith(".webp") || fn.endsWith(".gif");
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
                const handlePreviewClick = (e) => {
                    const btn = e.target.closest('button[name="action_preview_invoice"]');
                    if (btn) {
                        e.preventDefault();
                        e.stopPropagation();
                        const record = this.model?.root;
                        const resId = record?.resId;
                        const filename = record?.data?.invoice_filename || "invoice.pdf";
                        if (resId) {
                            const url = `/web/content/equipment.master/${resId}/invoice_attachment/${filename}?download=false`;
                            this.dialogService.add(InvoicePreviewDialog, {
                                title: _t("Invoice Preview"),
                                fileUrl: url,
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
