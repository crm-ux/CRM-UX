/** @odoo-module **/

import { Component, xml, onMounted, onWillUnmount } from "@odoo/owl";
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
const cogMenuRegistry = registry.category("cogMenu");

class ComplaintTypesCogMenuItem extends Component {
    static template = xml`
        <span class="dropdown-item d-flex align-items-center cursor-pointer" role="menuitem" t-on-click="onSelected">
            <i class="fa fa-tags me-2"/>
            <span>Complaint Types</span>
        </span>
    `;

    async onSelected() {
        await this.env.services.action.doAction({
            name: _t("Complaint Types"),
            type: "ir.actions.act_window",
            res_model: "service.ticket.complaint.type",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: false });
    }
}

cogMenuRegistry.add("service_ticket_complaint_types", {
    isDisplayed: (env) => {
        const resModel = env.config?.resModel || env.searchModel?.resModel || env.config?.action?.res_model;
        const viewType = env.config?.viewType;
        const isListOrTree = !viewType || viewType === "list" || viewType === "tree";
        return isListOrTree && resModel === TICKET_MODEL;
    },
    Component: ComplaintTypesCogMenuItem,
    groupNumber: 20,
    sequence: 30,
});

async function openServiceTicketWizard(env) {
    await env.services.action.doAction(WIZARD_ACTION);
}

// 1. Intercept "New" button in List / Tree View & enable Universal Preview on voucher lines
patch(ListController.prototype, {
    setup() {
        super.setup();
        if (
            this.model?.root?.resModel === "service.ticket.voucher.line" ||
            this.props?.resModel === "service.ticket.voucher.line"
        ) {
            const handleVoucherListBillPreview = async (ev) => {
                const previewBtn = ev.target.closest("button[name='action_preview_bill']");
                if (!previewBtn) return;

                ev.preventDefault();
                ev.stopPropagation();

                const row = previewBtn.closest("tr, .o_data_row");
                if (!row) return;

                const allRows = Array.from(row.closest("tbody")?.querySelectorAll("tr.o_data_row") || []);
                const rowIndex = allRows.indexOf(row);
                const records = this.model?.root?.records || [];
                const record = rowIndex >= 0 && rowIndex < records.length ? records[rowIndex] : null;

                const recId = record?.resId || null;
                let filename = record?.data?.bill_filename || "bill.png";
                let fileData = record?.data?.bill_file || null;

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

                const fileUrl = recId ? `/web/content/service.ticket.voucher.line/${recId}/bill_file/${encodeURIComponent(filename)}?download=false` : null;

                this.dialogService = this.dialogService || this.env.services.dialog;
                this.dialogService.add(UniversalAttachmentPreviewDialog, {
                    title: filename || _t("Bill Preview"),
                    fileUrl: fileUrl,
                    fileData: fileData,
                    filename: filename,
                    previewContent: previewContent,
                });
            };

            const handleVoucherDescriptionClick = async (ev) => {
                const target = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
                if (!target || !target.closest) return;
                const cell = target.closest("td[name='description']");
                if (!cell) return;

                ev.preventDefault();
                ev.stopPropagation();

                const row = cell.closest("tr, .o_data_row");
                if (!row) return;

                const allRows = Array.from(row.closest("tbody")?.querySelectorAll("tr.o_data_row") || []);
                const rowIndex = allRows.indexOf(row);
                const records = this.model?.root?.records || [];
                const record = rowIndex >= 0 && rowIndex < records.length ? records[rowIndex] : null;

                const descText = record?.data?.description || cell.innerText?.trim() || "";
                if (!descText) return;

                await this.env.services.action.doAction("custom_crm_extended.action_service_ticket_voucher_desc_wizard", {
                    additionalContext: {
                        default_description: descText,
                        default_voucher_line_id: record?.resId || false,
                    },
                });
            };

            // Completely block Odoo's popover tooltip service from triggering on description cells
            const handleVoucherDescriptionHoverBlock = (ev) => {
                const target = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
                if (!target || !target.closest) return;
                const cell = target.closest("td[name='description']");
                if (cell) {
                    ev.stopPropagation();
                    cell.removeAttribute("title");
                    cell.removeAttribute("data-tooltip");
                    const child = cell.firstElementChild;
                    if (child) {
                        child.removeAttribute("title");
                        child.removeAttribute("data-tooltip");
                    }
                }
            };

            document.addEventListener("click", handleVoucherListBillPreview, true);
            document.addEventListener("click", handleVoucherDescriptionClick, true);
            document.addEventListener("mouseover", handleVoucherDescriptionHoverBlock, true);
            document.addEventListener("mouseenter", handleVoucherDescriptionHoverBlock, true);
            document.addEventListener("pointerenter", handleVoucherDescriptionHoverBlock, true);
        }
    },
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
                // Style via CSS only without mutating DOM nodes directly to prevent Owl lifecycle crash
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                if (container) {
                    container.style.setProperty("display", "flex", "important");
                }
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (statusIndicator) {
                    statusIndicator.style.setProperty("order", "1", "important");
                    statusIndicator.style.setProperty("margin-right", "16px", "important");
                    statusIndicator.style.setProperty("flex-grow", "0", "important");
                }
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                if (breadcrumb) {
                    breadcrumb.style.setProperty("order", "2", "important");
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
                        if (this.model && this.model.root && this.model.root.update) {
                            this.model.root.update({ new_voucher_amount: calculated });
                        }
                    } else {
                        // When user backspaces or clears KM to 0/empty, immediately calculate Amount to 0.00
                        if (this.model && this.model.root && this.model.root.update) {
                            this.model.root.update({ new_voucher_amount: 0.0 });
                        }
                    }
                }
            };

            // Track spacebar keydown state for secret combo (Ctrl + Spacebar + Click)
            let isSpaceKeyDown = false;
            const handleKeyDown = (e) => {
                if (e.code === "Space" || e.key === " ") {
                    isSpaceKeyDown = true;
                }
            };
            const handleKeyUp = (e) => {
                if (e.code === "Space" || e.key === " ") {
                    isSpaceKeyDown = false;
                }
            };
            window.addEventListener("keydown", handleKeyDown, true);
            window.addEventListener("keyup", handleKeyUp, true);

            // Intercept Voucher tab click: require Ctrl + Spacebar + Click
            const handleVoucherTabClick = (ev) => {
                const tabLink = ev.target.closest("a.nav-link, [role='tab']");
                if (!tabLink) return;
                const tabText = (tabLink.innerText || tabLink.textContent || "").trim();
                if (tabText === "Voucher" || tabText.startsWith("Voucher")) {
                    const isSecretCombo = Boolean(ev.ctrlKey && isSpaceKeyDown);
                    // Always prevent default to stop browser from opening link in a new browser tab/window on Ctrl+Click
                    ev.preventDefault();
                    ev.stopPropagation();
                    ev.stopImmediatePropagation();

                    if (isSecretCombo) {
                        // Switch directly to the Voucher tab internally inside the same form
                        tabLink.focus();
                        tabLink.click();
                        // Also trigger bootstrap / Odoo tab show if available
                        if (window.bootstrap?.Tab) {
                            const tabInstance = window.bootstrap.Tab.getOrCreateInstance(tabLink);
                            if (tabInstance) tabInstance.show();
                        } else {
                            // Fallback: manually activate tab classes
                            const parentNav = tabLink.closest(".nav-tabs, .o_notebook_headers");
                            if (parentNav) {
                                parentNav.querySelectorAll("a.nav-link, [role='tab']").forEach((el) => {
                                    el.classList.remove("active");
                                    el.setAttribute("aria-selected", "false");
                                });
                            }
                            tabLink.classList.add("active");
                            tabLink.setAttribute("aria-selected", "true");
                            const targetSelector = tabLink.getAttribute("data-bs-target") || tabLink.getAttribute("href");
                            if (targetSelector && targetSelector.startsWith("#")) {
                                const targetPane = document.querySelector(targetSelector);
                                if (targetPane && targetPane.parentElement) {
                                    targetPane.parentElement.querySelectorAll(".tab-pane").forEach((pane) => {
                                        pane.classList.remove("active", "show");
                                    });
                                    targetPane.classList.add("active", "show");
                                }
                            }
                        }
                        return;
                    }

                    // Otherwise show Coming Soon notification
                    if (this.env?.services?.notification) {
                        this.env.services.notification.add(_t("Voucher Management is Coming Soon!"), {
                            title: _t("Coming Soon"),
                            type: "info",
                            sticky: false,
                        });
                    }
                }
            };
            document.addEventListener("click", handleVoucherTabClick, true);

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
                window.removeEventListener("keydown", handleKeyDown, true);
                window.removeEventListener("keyup", handleKeyUp, true);
                document.removeEventListener("click", handleVoucherTabClick, true);
                document.removeEventListener("change", handleVoucherFileInputChange, true);
                document.removeEventListener("click", handleVoucherBillPreview, true);
                document.removeEventListener("input", handleKmInstantCalc, true);
                document.removeEventListener("change", handleKmInstantCalc, true);
            });
        }
    }

    async discard() {
        return super.discard(...arguments);
    }

    async save() {
        const res = await super.save(...arguments);
        if (res && this.props.resModel === "service.ticket") {
            if (this.model && this.model.root && this.model.root.update) {
                this.model.root.update({
                    new_voucher_expense_type_id: false,
                    new_voucher_user_ids: [[5, 0, 0]],
                    new_voucher_total_km: 0.0,
                    new_voucher_amount: 0.0,
                    new_voucher_description: false,
                    new_voucher_bill_file: false,
                });
            }
        }
        return res;
    }
}

export const serviceTicketFormView = {
    ...formView,
    Controller: ServiceTicketFormController,
};

registry.category("views").add("service_ticket_form", serviceTicketFormView);
