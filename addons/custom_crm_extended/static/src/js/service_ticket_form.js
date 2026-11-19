/** @odoo-module **/

import { Component, xml, onMounted, onWillUnmount } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { BooleanField } from "@web/views/fields/boolean/boolean_field";
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
                const previewBtn = ev.target.closest(".o_voucher_bill_preview_btn, button[name='action_preview_bill']");
                if (!previewBtn) return;

                ev.preventDefault();
                ev.stopPropagation();

                let recId = previewBtn.dataset?.lineId ? parseInt(previewBtn.dataset.lineId) : null;
                if (!recId) {
                    const row = previewBtn.closest("tr, .o_data_row");
                    if (row) {
                        const allRows = Array.from(row.closest("tbody")?.querySelectorAll("tr.o_data_row") || []);
                        const rowIndex = allRows.indexOf(row);
                        const records = this.model?.root?.records || [];
                        const record = rowIndex >= 0 && rowIndex < records.length ? records[rowIndex] : null;
                        if (record) recId = record.resId;
                    }
                }

                if (recId) {
                    let previewOpened = false;
                    try {
                        const fetched = await this.env.services.orm.read(
                            "service.ticket.voucher.line",
                            [recId],
                            ["bill_attachment_ids", "bill_file", "bill_filename"],
                            { context: { bin_size: false } }
                        );
                        if (fetched && fetched.length > 0) {
                            let attId = null;
                            let fname = fetched[0].bill_filename || "";
                            let b64Data = fetched[0].bill_file || null;
                            if (fetched[0].bill_attachment_ids && fetched[0].bill_attachment_ids.length > 0) {
                                attId = fetched[0].bill_attachment_ids[0];
                                const attRead = await this.env.services.orm.read(
                                    "ir.attachment",
                                    [attId],
                                    ["name", "datas", "mimetype"],
                                    { context: { bin_size: false } }
                                );
                                if (attRead && attRead.length > 0) {
                                    fname = attRead[0].name || fname;
                                    b64Data = attRead[0].datas || b64Data;
                                }
                            }
                            if (b64Data || attId) {
                                fname = fname || "document.pdf";
                                let previewContent = null;
                                const isDocOrZipOrExcel = ["docx", "doc", "zip", "rar", "7z", "tar", "gz", "xlsx", "xls", "csv"].some((ext) =>
                                    fname.toLowerCase().endsWith("." + ext)
                                );
                                if (isDocOrZipOrExcel && b64Data) {
                                    try {
                                        previewContent = await this.env.services.orm.call(
                                            "equipment.master",
                                            "action_get_invoice_preview_content",
                                            [false, b64Data, fname],
                                            {}
                                        );
                                    } catch (pe) {
                                        console.error("Preview content fetch failed:", pe);
                                    }
                                }
                                const fileUrl = attId ? `/web/content/${attId}?download=false` : `/web/content?model=service.ticket.voucher.line&id=${recId}&field=bill_file&filename=${encodeURIComponent(fname)}&download=false`;
                                const dialog = this.env.services.dialog || this.dialogService;
                                if (dialog) {
                                    dialog.add(UniversalAttachmentPreviewDialog, {
                                        title: fname || _t("Document Preview"),
                                        fileUrl: fileUrl,
                                        fileData: b64Data,
                                        filename: fname,
                                        previewContent: previewContent,
                                    });
                                    previewOpened = true;
                                }
                            }
                        }
                    } catch (e) {
                        console.warn("Universal preview failed, falling back to server action:", e);
                    }

                    if (!previewOpened) {
                        try {
                            const action = await this.env.services.orm.call(
                                "service.ticket.voucher.line",
                                "action_preview_bill",
                                [[recId]]
                            );
                            if (action) {
                                if (!action.views) {
                                    action.views = [[action.view_id || false, "form"]];
                                }
                                return this.env.services.action.doAction(action);
                            }
                        } catch (err) {
                            console.error("Error executing action_preview_bill:", err);
                        }
                    }
                }
            };

            const handleVoucherDescriptionClick = async (ev) => {
                const target = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
                if (!target || !target.closest) return;
                const cell = target.closest("td[name='description']");
                if (!cell) return;

                ev.preventDefault();
                ev.stopPropagation();
                ev.stopImmediatePropagation();

                if (document.querySelector(".modal.show, .o_dialog, .o_technical_modal")) return;

                const row = cell.closest("tr, .o_data_row");
                if (!row) return;

                const allRows = Array.from(row.closest("tbody")?.querySelectorAll("tr.o_data_row") || []);
                const rowIndex = allRows.indexOf(row);
                const records = this.model?.root?.records || [];
                const record = rowIndex >= 0 && rowIndex < records.length ? records[rowIndex] : null;

                const descText = record?.data?.description || cell.innerText?.trim() || "";
                if (!descText) return;

                await this.env.services.action.doAction({
                    name: "Expense Description",
                    type: "ir.actions.act_window",
                    res_model: "service.ticket.voucher.desc.wizard",
                    views: [[false, "form"]],
                    target: "new",
                    context: {
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
    async openRecord(record) {
        if (
            this.model?.root?.resModel === "service.ticket.voucher.line" ||
            record?.resModel === "service.ticket.voucher.line" ||
            this.props?.resModel === "service.ticket.voucher.line"
        ) {
            return;
        }
        return super.openRecord(...arguments);
    },
});

// Prevent clicking on voucher line table rows from opening the sub-form view
patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        window.__odooVoucherEnv = this.env;
        if (
            this.props.list?.resModel === "service.ticket.voucher.line" ||
            this.model?.root?.resModel === "service.ticket.voucher.line"
        ) {
            window.__odooVoucherListRenderer = this;
        }
    },
    async onCellClicked(record, column, ev) {
        if (
            record?.resModel === "service.ticket.voucher.line" ||
            this.props.list?.resModel === "service.ticket.voucher.line"
        ) {
            if (ev?.target?.closest("button, a, input, select, .btn, .o_field_many2many_tags")) {
                return super.onCellClicked ? super.onCellClicked(...arguments) : undefined;
            }
            return;
        }
        return super.onCellClicked(...arguments);
    },
});

// Capture-phase listener to block raw cell clicks on voucher line tables from opening form
document.addEventListener(
    "click",
    (ev) => {
        // Do NOT block clicks inside modal dialogs / wizards (e.g. recovery wizard editable table)
        if (ev.target.closest(".modal, .o_dialog, .crm_batch_recovery_wizard_modal")) {
            return;
        }

        const row = ev.target.closest(
            ".o_voucher_card_list tr.o_data_row, div[name='line_ids'] tr.o_data_row, div[name='ticket_voucher_line_ids'] tr.o_data_row"
        );
        if (!row) return;
        // Allow buttons, links, tag chips, and inputs (like View Description, View Bill, Approve/Reject/Pay/Recovery buttons)
        if (ev.target.closest("button, a, input, select, textarea, .btn, .o_field_many2many_tags")) {
            return;
        }
        // Disallow row clicks on any data cell from opening record / breaking UI
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
    },
    true
);

// Enforce compact 13px size on voucher line checkbox buttons directly in DOM (ONLY on Voucher Manager page)
(function injectVoucherManagerCheckboxStyles() {
    if (typeof document === "undefined") return;
    const styleId = "crm_voucher_checkbox_head_style";
    let style = document.getElementById(styleId);
    if (!style) {
        style = document.createElement("style");
        style.id = styleId;
        (document.head || document.documentElement).appendChild(style);
    }
    style.textContent = `
        .o_service_ticket_voucher_batch_form .o_list_renderer .o_data_row td button[name='action_toggle_recovery_select'],
        .o_service_ticket_voucher_batch_form .o_list_renderer .o_data_row td .btn[name='action_toggle_recovery_select'],
        .o_service_ticket_voucher_batch_form button[name='action_toggle_recovery_select'] {
            width: 13px !important;
            height: 13px !important;
            min-width: 13px !important;
            max-width: 13px !important;
            min-height: 13px !important;
            max-height: 13px !important;
            box-sizing: border-box !important;
            border: 1.5px solid #0b3d91 !important;
            border-radius: 2px !important;
            padding: 0 !important;
            margin: 0 !important;
            font-size: 8px !important;
            line-height: 1 !important;
            overflow: hidden !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            vertical-align: middle !important;
            transition: none !important;
        }
        .o_service_ticket_voucher_batch_form button[name='action_toggle_recovery_select'].crm_checkbox_checked {
            background-color: #0b3d91 !important;
            border: 1.5px solid #0b3d91 !important;
            color: #ffffff !important;
        }
        .o_service_ticket_voucher_batch_form button[name='action_toggle_recovery_select'].crm_checkbox_unchecked {
            background-color: #ffffff !important;
            border: 1.5px solid #0b3d91 !important;
            color: transparent !important;
        }
        .o_service_ticket_voucher_batch_form button[name='action_toggle_recovery_select'] i,
        .o_service_ticket_voucher_batch_form button[name='action_toggle_recovery_select'] .o_button_icon {
            font-size: 8px !important;
            width: 8px !important;
            height: 8px !important;
            min-width: 8px !important;
            max-width: 8px !important;
            line-height: 8px !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        .o_service_ticket_voucher_batch_form button[name='action_toggle_recovery_select'].crm_checkbox_unchecked i,
        .o_service_ticket_voucher_batch_form button[name='action_toggle_recovery_select'].crm_checkbox_unchecked .o_button_icon {
            display: none !important;
            visibility: hidden !important;
        }
        /* Hide Claim Recovery by default, only show when at least 1 checkbox is checked */
        .o_statusbar_buttons button[name='action_claim_recovery'],
        .o_statusbar_buttons button[name='action_claim_recovery_batch'],
        .o_form_statusbar button[name='action_claim_recovery'],
        .o_form_statusbar button[name='action_claim_recovery_batch'],
        .o_service_ticket_voucher_batch_form header button[name='action_claim_recovery'],
        .o_service_ticket_voucher_batch_form header button[name='action_claim_recovery_batch'],
        .o_service_ticket_voucher_line_form header button[name='action_claim_recovery'],
        .o_service_ticket_voucher_line_form header button[name='action_claim_recovery_batch'],
        button[name='action_claim_recovery']:not(td button),
        button[name='action_claim_recovery_batch']:not(td button) {
            display: none !important;
        }
        body:has(button[name='action_toggle_recovery_select'].crm_checkbox_checked) .o_statusbar_buttons button[name='action_claim_recovery'],
        body:has(button[name='action_toggle_recovery_select'].crm_checkbox_checked) .o_statusbar_buttons button[name='action_claim_recovery_batch'],
        body:has(button[name='action_toggle_recovery_select'].crm_checkbox_checked) .o_form_statusbar button[name='action_claim_recovery'],
        body:has(button[name='action_toggle_recovery_select'].crm_checkbox_checked) .o_form_statusbar button[name='action_claim_recovery_batch'],
        body:has(button[name='action_toggle_recovery_select'].crm_checkbox_checked) header button[name='action_claim_recovery'],
        body:has(button[name='action_toggle_recovery_select'].crm_checkbox_checked) header button[name='action_claim_recovery_batch'],
        body:has(button[name='action_toggle_recovery_select'].crm_checkbox_checked) button[name='action_claim_recovery']:not(td button),
        body:has(button[name='action_toggle_recovery_select'].crm_checkbox_checked) button[name='action_claim_recovery_batch']:not(td button) {
            display: inline-block !important;
        }

        .crm_voucher_select_all_btn {
            width: 13px !important;
            height: 13px !important;
            min-width: 13px !important;
            max-width: 13px !important;
            min-height: 13px !important;
            max-height: 13px !important;
            box-sizing: border-box !important;
            border: 1.5px solid #0b3d91 !important;
            border-radius: 2px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            vertical-align: middle !important;
            margin: 0 auto !important;
            padding: 0 !important;
            line-height: 1 !important;
            overflow: hidden !important;
            cursor: pointer !important;
        }
        .crm_voucher_select_all_btn.crm_checkbox_checked {
            background-color: #0b3d91 !important;
            border: 1.5px solid #0b3d91 !important;
            color: #ffffff !important;
        }
        .crm_voucher_select_all_btn.crm_checkbox_checked i {
            font-size: 8px !important;
            width: 8px !important;
            height: 8px !important;
            line-height: 8px !important;
            color: #ffffff !important;
            display: block !important;
        }
        .crm_voucher_select_all_btn.crm_checkbox_unchecked {
            background-color: #ffffff !important;
            border: 1.5px solid #0b3d91 !important;
            color: transparent !important;
        }
        .crm_voucher_select_all_btn.crm_checkbox_unchecked i {
            display: none !important;
            visibility: hidden !important;
        }
    `;
})();

function getStatusColumnIndex(table) {
    if (!table) return -1;
    const ths = table.querySelectorAll("thead th");
    for (let i = 0; i < ths.length; i++) {
        if (ths[i].textContent.trim().toLowerCase() === "status") {
            return i;
        }
    }
    return -1;
}

function getRowStatusText(row) {
    if (!row) return "";
    // 1. Try cell with specific column name display_status / status
    const el = row.querySelector("td[data-name='display_status'], td[name='display_status'], td[data-name='status'], td[name='status']");
    if (el) return el.textContent.trim().toLowerCase();

    // 2. Try by column index matching header 'Status'
    const table = row.closest("table.o_list_table");
    const colIdx = getStatusColumnIndex(table);
    if (colIdx >= 0 && row.children[colIdx]) {
        return row.children[colIdx].textContent.trim().toLowerCase();
    }

    // 3. Fallback: check record in controller model if available
    const dataId = row.dataset.id;
    const controller = window.__odooCurrentFormController;
    const root = controller?.model?.root;
    const lineField = root?.data?.line_ids || root?.data?.ticket_voucher_line_ids;
    if (lineField?.records) {
        const match = lineField.records.find((r) => r.id === dataId);
        if (match?.data?.status) return (match.data.status || "").toLowerCase();
    }

    return "";
}

function isRowEligibleForRecovery(row) {
    const text = getRowStatusText(row);
    return text.includes("paid") && !text.includes("recovered");
}

function setRowCheckboxVisual(row, isChecked) {
    if (!row) return;
    const cellButtons = Array.from(row.querySelectorAll("button[name='action_toggle_recovery_select']"));
    if (cellButtons.length === 0) return;

    // Use the first button as the visible, single reliable checkbox
    const mainBtn = cellButtons[0];
    mainBtn.style.setProperty("display", "inline-flex", "important");
    mainBtn.style.setProperty("width", "13px", "important");
    mainBtn.style.setProperty("height", "13px", "important");
    mainBtn.style.setProperty("min-width", "13px", "important");
    mainBtn.style.setProperty("max-width", "13px", "important");
    mainBtn.style.setProperty("min-height", "13px", "important");
    mainBtn.style.setProperty("max-height", "13px", "important");
    mainBtn.style.setProperty("border", "1.5px solid #0b3d91", "important");
    mainBtn.style.setProperty("border-radius", "2px", "important");
    mainBtn.style.setProperty("padding", "0", "important");
    mainBtn.style.setProperty("margin", "0 auto", "important");
    mainBtn.style.setProperty("box-sizing", "border-box", "important");
    mainBtn.style.setProperty("cursor", "pointer", "important");
    mainBtn.style.setProperty("vertical-align", "middle", "important");
    mainBtn.classList.remove("d-none");

    const td = mainBtn.closest("td");
    if (td) {
        td.style.setProperty("width", "28px", "important");
        td.style.setProperty("max-width", "28px", "important");
        td.style.setProperty("padding-left", "4px", "important");
        td.style.setProperty("padding-right", "4px", "important");
        td.style.setProperty("text-align", "center", "important");
    }

    let icon = mainBtn.querySelector("i, .o_button_icon");
    if (!icon) {
        icon = document.createElement("i");
        icon.className = "fa fa-check o_button_icon";
        mainBtn.appendChild(icon);
    }
    icon.style.setProperty("font-size", "8px", "important");
    icon.style.setProperty("width", "8px", "important");
    icon.style.setProperty("height", "8px", "important");
    icon.style.setProperty("line-height", "8px", "important");
    icon.style.setProperty("color", "#ffffff", "important");

    if (isChecked) {
        mainBtn.classList.add("crm_checkbox_checked");
        mainBtn.classList.remove("crm_checkbox_unchecked");
        mainBtn.style.setProperty("background-color", "#0b3d91", "important");
        mainBtn.style.setProperty("color", "#ffffff", "important");
        icon.style.setProperty("display", "block", "important");
    } else {
        mainBtn.classList.remove("crm_checkbox_checked");
        mainBtn.classList.add("crm_checkbox_unchecked");
        mainBtn.style.setProperty("background-color", "#ffffff", "important");
        mainBtn.style.setProperty("color", "transparent", "important");
        icon.style.setProperty("display", "none", "important");
    }

    // Hide any duplicate button in the same cell so only 1 button is active
    for (let i = 1; i < cellButtons.length; i++) {
        cellButtons[i].style.setProperty("display", "none", "important");
        cellButtons[i].classList.add("d-none");
    }
}

function updateRecoverySelectionState() {
    const table = document.querySelector(".o_service_ticket_voucher_batch_form table.o_list_table, .o_service_ticket_voucher_line_form table.o_list_table, table.o_list_table:has(button[name='action_toggle_recovery_select'])");
    if (!table) return;

    const rows = table.querySelectorAll("tbody tr.o_data_row");
    let totalEligible = 0;
    let checkedEligible = 0;

    rows.forEach((row) => {
        if (!isRowEligibleForRecovery(row)) return;
        totalEligible++;

        const mainBtn = row.querySelector("button[name='action_toggle_recovery_select']:not([style*='display: none'])") || row.querySelector("button[name='action_toggle_recovery_select']");
        const isChecked = mainBtn && mainBtn.classList.contains("crm_checkbox_checked");
        if (isChecked) {
            checkedEligible++;
        }
    });

    // 1. Update Header Checkbox (Checked only if ALL eligible rows are checked)
    const selectAllBtn = table.querySelector("thead .crm_voucher_select_all_btn");
    if (selectAllBtn) {
        const isAllSelected = totalEligible > 0 && checkedEligible === totalEligible;
        selectAllBtn.style.setProperty("width", "13px", "important");
        selectAllBtn.style.setProperty("height", "13px", "important");
        selectAllBtn.style.setProperty("min-width", "13px", "important");
        selectAllBtn.style.setProperty("max-width", "13px", "important");
        selectAllBtn.style.setProperty("min-height", "13px", "important");
        selectAllBtn.style.setProperty("max-height", "13px", "important");
        selectAllBtn.style.setProperty("border", "1.5px solid #0b3d91", "important");
        selectAllBtn.style.setProperty("border-radius", "2px", "important");
        selectAllBtn.style.setProperty("display", "inline-flex", "important");

        const icon = selectAllBtn.querySelector("i");
        if (isAllSelected) {
            selectAllBtn.classList.remove("crm_checkbox_unchecked");
            selectAllBtn.classList.add("crm_checkbox_checked");
            selectAllBtn.style.setProperty("background-color", "#0b3d91", "important");
            selectAllBtn.style.setProperty("color", "#ffffff", "important");
            if (icon) icon.style.setProperty("display", "block", "important");
        } else {
            selectAllBtn.classList.remove("crm_checkbox_checked");
            selectAllBtn.classList.add("crm_checkbox_unchecked");
            selectAllBtn.style.setProperty("background-color", "#ffffff", "important");
            selectAllBtn.style.setProperty("color", "transparent", "important");
            if (icon) icon.style.setProperty("display", "none", "important");
        }
    }

    // 2. Update Header Claim Recovery Button (Show if ANY line is checked)
    const anyChecked = checkedEligible > 0;
    const claimBtns = document.querySelectorAll(
        ".o_statusbar_buttons button[name='action_claim_recovery'], .o_statusbar_buttons button[name='action_claim_recovery_batch'], .o_form_statusbar button[name='action_claim_recovery'], .o_form_statusbar button[name='action_claim_recovery_batch'], button[name='action_claim_recovery']:not(td button), button[name='action_claim_recovery_batch']:not(td button)"
    );
    claimBtns.forEach((cBtn) => {
        cBtn.style.setProperty("display", anyChecked ? "inline-block" : "none", "important");
    });
}

function formatVoucherCheckboxButtons() {
    const table = document.querySelector(".o_service_ticket_voucher_batch_form table.o_list_table, .o_service_ticket_voucher_line_form table.o_list_table, table.o_list_table:has(button[name='action_toggle_recovery_select'])");
    if (!table) return;

    const rows = table.querySelectorAll("tbody tr.o_data_row");
    rows.forEach((row) => {
        const checkedBtn = row.querySelector("button.crm_checkbox_checked:not(.d-none)");
        const isChecked = checkedBtn && checkedBtn.style.display !== "none";
        setRowCheckboxVisual(row, !!isChecked);
    });

    // Inject the "Select All" checkbox in the column header (<th>) if missing
    const firstTd = table.querySelector("tbody tr.o_data_row td:has(button[name='action_toggle_recovery_select'])") || table.querySelector("tbody tr.o_data_row td.o_list_button");
    if (firstTd) {
        const colIndex = Array.from(firstTd.parentElement.children).indexOf(firstTd);
        const headerRow = table.querySelector("thead tr");
        const th = headerRow && colIndex >= 0 ? headerRow.children[colIndex] : null;
        if (th) {
            th.style.setProperty("width", "28px", "important");
            th.style.setProperty("max-width", "28px", "important");
            th.style.setProperty("text-align", "center", "important");
            th.style.setProperty("vertical-align", "middle", "important");
            th.style.setProperty("padding-left", "4px", "important");
            th.style.setProperty("padding-right", "4px", "important");

            let selectAllBtn = th.querySelector(".crm_voucher_select_all_btn");
            if (!selectAllBtn) {
                th.innerHTML = "";
                selectAllBtn = document.createElement("button");
                selectAllBtn.type = "button";
                selectAllBtn.className = "btn p-0 crm_custom_blue_checkbox crm_voucher_select_all_btn crm_checkbox_unchecked";
                selectAllBtn.title = "Select / Deselect All Paid Lines";
                selectAllBtn.innerHTML = '<i class="fa fa-check"></i>';
                th.appendChild(selectAllBtn);
            }
        }
    }

    updateRecoverySelectionState();
}

// ── Capture-phase click listener for individual LINE checkboxes ──
// Instant 0ms toggle with zero flicker and silent background persistence
document.addEventListener("click", async (ev) => {
    const rowBtn = ev.target.closest("button[name='action_toggle_recovery_select']");
    if (!rowBtn) return;

    const row = rowBtn.closest("tr.o_data_row");
    if (!row) return;

    ev.preventDefault();
    ev.stopPropagation();

    // Determine current state
    const isCurrentlyChecked = rowBtn.classList.contains("crm_checkbox_checked") && !rowBtn.classList.contains("crm_checkbox_unchecked");
    const newState = !isCurrentlyChecked;

    // Check line eligibility ONLY when user attempts to check (select) an unpaid line.
    // Deselecting/unchecking is ALWAYS permitted!
    if (newState && !isRowEligibleForRecovery(row)) {
        const env = window.__odooEnv || window.__odooCurrentFormController?.env;
        if (env?.services?.notification) {
            const statusText = getRowStatusText(row);
            env.services.notification.add(
                `Recovery can only be claimed on Paid or Partially Paid expense lines. This line status is "${statusText || 'Draft'}".`,
                { title: "Cannot Select Expense", type: "warning" }
            );
        }
        return;
    }

    // Instant visual toggle on this row (0ms) - CAN NEVER DISAPPEAR
    setRowCheckboxVisual(row, newState);

    // Immediately update header checkbox (all checked vs not all) and Claim Recovery button
    updateRecoverySelectionState();

    // Silently sync to backend in background (no reload, no blink)
    try {
        const controller = window.__odooCurrentFormController;
        const env = window.__odooEnv || controller?.env || window.__odooVoucherEnv;
        const dataId = row.dataset.id;
        let resId = null;

        const root = controller?.model?.root;
        const lineField = root?.data?.line_ids || root?.data?.ticket_voucher_line_ids;
        if (lineField?.records) {
            const match = lineField.records.find((r) => r.id === dataId);
            if (match) resId = match.resId;
        }

        if (resId && env?.services?.orm) {
            await env.services.orm.write(
                "service.ticket.voucher.line",
                [resId],
                { is_selected_for_recovery: newState }
            );
        }
    } catch (err) {
        console.error("Line toggle sync error:", err);
    }
}, true);

// ── Capture-phase click listener for the header "Select All" checkbox ──
// Instant 0ms toggle for all lines with zero flicker and silent background persistence
document.addEventListener("click", async (ev) => {
    const allBtn = ev.target.closest(".crm_voucher_select_all_btn");
    if (!allBtn) return;
    ev.preventDefault();
    ev.stopPropagation();

    const isAllChecked = allBtn.classList.contains("crm_checkbox_checked");
    const targetState = !isAllChecked;

    const table = allBtn.closest("table.o_list_table");
    const rows = (table || document).querySelectorAll("tbody tr.o_data_row");

    let hasEligibleRows = false;

    // 1. Instant visual update for ALL rows (0ms) - CAN NEVER DISAPPEAR
    rows.forEach((row) => {
        if (!isRowEligibleForRecovery(row)) return;
        hasEligibleRows = true;
        setRowCheckboxVisual(row, targetState);
    });

    if (!hasEligibleRows) {
        const env = window.__odooEnv || window.__odooCurrentFormController?.env;
        if (env?.services?.notification) {
            env.services.notification.add(
                "No paid expenses are currently available for recovery on this voucher.",
                { title: "No Paid Expenses", type: "warning" }
            );
        }
        return;
    }

    // 2. Update Header Checkbox & Claim Recovery button immediately
    updateRecoverySelectionState();

    // 3. Silently sync backend in background (NO root.load() to avoid 1-sec blink!)
    try {
        const controller = window.__odooCurrentFormController;
        const env = window.__odooEnv || controller?.env || window.__odooVoucherEnv;
        const root = controller?.model?.root;
        const resModel = root?.resModel || (window.location.hash.includes("service.ticket.voucher.batch") ? "service.ticket.voucher.batch" : "service.ticket.voucher.line");
        const resId = root?.resId || parseInt(new URLSearchParams(window.location.hash.slice(1)).get("id"));

        if (resId && env?.services?.orm) {
            await env.services.orm.call(
                resModel,
                "action_toggle_select_all_recovery",
                [[resId]]
            );
        }
    } catch (err) {
        console.error("Select-all sync error:", err);
    }
}, true);

if (typeof window !== "undefined" && typeof MutationObserver !== "undefined") {
    const observer = new MutationObserver(() => {
        formatVoucherCheckboxButtons();
    });
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener("DOMContentLoaded", () => {
            if (document.body) {
                observer.observe(document.body, { childList: true, subtree: true });
            }
            formatVoucherCheckboxButtons();
        });
    }
}

// 2. Intercept "New" button in Detail Form View & capture current active form controller
patch(FormController.prototype, {
    setup() {
        super.setup();
        window.__odooCurrentFormController = this;
        window.__odooEnv = this.env;
    },
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
        const isTicketOrWizard = this.props.resModel === "service.ticket" || this.props.resModel === "service.ticket.wizard";
        if (isTicketOrWizard) {
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

            // Handle Eye Preview button on Voucher lines / Bill links
            const handleVoucherBillPreview = async (ev) => {
                const previewBtn = ev.target.closest(".o_voucher_bill_preview_btn, button[name='action_preview_bill']");
                if (!previewBtn) return;

                ev.preventDefault();
                ev.stopPropagation();

                let recId = previewBtn.dataset?.lineId ? parseInt(previewBtn.dataset.lineId) : null;
                if (!recId) {
                    const row = previewBtn.closest("tr, .o_data_row");
                    if (row) {
                        const record = this.model?.root;
                        const voucherList = record?.data?.voucher_line_ids || record?.data?.draft_voucher_line_ids || record?.data?.line_ids;
                        if (voucherList && voucherList.records) {
                            const allRows = Array.from(row.closest("tbody")?.querySelectorAll("tr.o_data_row") || []);
                            const rowIndex = allRows.indexOf(row);
                            if (rowIndex >= 0 && rowIndex < voucherList.records.length) {
                                recId = voucherList.records[rowIndex].resId;
                            }
                        }
                    }
                }

                if (recId) {
                    let previewOpened = false;
                    try {
                        const fetched = await this.env.services.orm.read(
                            "service.ticket.voucher.line",
                            [recId],
                            ["bill_attachment_ids", "bill_file", "bill_filename"],
                            { context: { bin_size: false } }
                        );
                        if (fetched && fetched.length > 0) {
                            let attId = null;
                            let fname = fetched[0].bill_filename || "";
                            let b64Data = fetched[0].bill_file || null;
                            if (fetched[0].bill_attachment_ids && fetched[0].bill_attachment_ids.length > 0) {
                                attId = fetched[0].bill_attachment_ids[0];
                                const attRead = await this.env.services.orm.read(
                                    "ir.attachment",
                                    [attId],
                                    ["name", "datas", "mimetype"],
                                    { context: { bin_size: false } }
                                );
                                if (attRead && attRead.length > 0) {
                                    fname = attRead[0].name || fname;
                                    b64Data = attRead[0].datas || b64Data;
                                }
                            }
                            if (b64Data || attId) {
                                fname = fname || "document.pdf";
                                let previewContent = null;
                                const isDocOrZipOrExcel = ["docx", "doc", "zip", "rar", "7z", "tar", "gz", "xlsx", "xls", "csv"].some((ext) =>
                                    fname.toLowerCase().endsWith("." + ext)
                                );
                                if (isDocOrZipOrExcel && b64Data) {
                                    try {
                                        previewContent = await this.env.services.orm.call(
                                            "equipment.master",
                                            "action_get_invoice_preview_content",
                                            [false, b64Data, fname],
                                            {}
                                        );
                                    } catch (pe) {
                                        console.error("Preview content fetch failed:", pe);
                                    }
                                }
                                const fileUrl = attId ? `/web/content/${attId}?download=false` : `/web/content?model=service.ticket.voucher.line&id=${recId}&field=bill_file&filename=${encodeURIComponent(fname)}&download=false`;
                                const dialog = this.env.services.dialog || this.dialogService;
                                if (dialog) {
                                    dialog.add(UniversalAttachmentPreviewDialog, {
                                        title: fname || _t("Document Preview"),
                                        fileUrl: fileUrl,
                                        fileData: b64Data,
                                        filename: fname,
                                        previewContent: previewContent,
                                    });
                                    previewOpened = true;
                                }
                            }
                        }
                    } catch (e) {
                        console.warn("Universal preview failed, falling back to server action:", e);
                    }

                    if (!previewOpened) {
                        try {
                            const action = await this.env.services.orm.call(
                                "service.ticket.voucher.line",
                                "action_preview_bill",
                                [[recId]]
                            );
                            if (action) {
                                if (!action.views) {
                                    action.views = [[action.view_id || false, "form"]];
                                }
                                return this.env.services.action.doAction(action);
                            }
                        } catch (err) {
                            console.error("Error executing action_preview_bill:", err);
                        }
                    }
                }
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

            // Scoped to Service Ticket: instant clear when user backspaces/deletes text in partner_id or equipment_id
            const handleTicketInputInstantClear = (ev) => {
                const target = ev.target;
                if (!target || target.tagName !== "INPUT") return;
                const fieldName = target.closest("[name='partner_id'], [name='equipment_id']")?.getAttribute("name");
                if (fieldName && target.value.trim() === "") {
                    if (this.model?.root?.update) {
                        if (fieldName === "partner_id") {
                            this.model.root.update({
                                partner_id: false,
                                equipment_id: false,
                                site_name: false,
                                contact_person: false,
                                contact_number: false,
                                email: false,
                                model_number: false,
                                serial_number: false,
                                part_number: false,
                                amc_id: false,
                            });
                        } else if (fieldName === "equipment_id") {
                            this.model.root.update({
                                equipment_id: false,
                                partner_id: false,
                                site_name: false,
                                contact_person: false,
                                contact_number: false,
                                email: false,
                                model_number: false,
                                serial_number: false,
                                part_number: false,
                                amc_id: false,
                            });
                        }
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
                document.removeEventListener("input", handleTicketInputInstantClear, true);
            });

            document.addEventListener("input", handleTicketInputInstantClear, true);
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
registry.category("views").add("service_ticket_wizard_form", serviceTicketFormView);

// Clean Owl reactivity for KM Based toggle: updates row values instantly in-place without page reload or DOM errors
patch(BooleanField.prototype, {
    async onChange(value) {
        await super.onChange(...arguments);
        if (this.props.name === "is_km_based" && this.props.record) {
            const rec = this.props.record;
            if (rec.resModel === "service.ticket.expense.type") {
                const isKm = Boolean(value);
                const updates = {};
                if (isKm) {
                    updates.calculation_type = "km";
                    updates.budget_limit_display = "-";
                    updates.km_rate_display = (rec.data.km_rate && rec.data.km_rate > 0) ? Number(rec.data.km_rate).toFixed(2) : "0.00";
                } else {
                    const calc = (rec.data.calculation_type && rec.data.calculation_type !== "km") ? rec.data.calculation_type : "daily";
                    updates.calculation_type = calc;
                    updates.km_rate_display = "-";
                    const suffix = calc === "daily" ? " / Day" : " / Visit";
                    updates.budget_limit_display = (rec.data.budget_limit && rec.data.budget_limit > 0)
                        ? `${rec.data.budget_limit.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${suffix}`
                        : "0.00";
                }
                try {
                    await rec.update(updates);
                    if (typeof rec.save === "function") {
                        await rec.save();
                    }
                } catch (e) {
                    console.warn("is_km_based reactive update error:", e);
                }
            }
        }
    },
});

// Dynamic cleanup for compact attachment pills: hide secondary extension tags (JPG, PDF, PNG, etc.)
if (typeof window !== "undefined") {
    const EXT_REGEX = /^(PDF|JPG|JPEG|PNG|DOC|DOCX|XLS|XLSX|CSV|ZIP|RAR|TXT|TIFF|BMP|WEBP|GIF|MP4|AVI)$/i;
    const TRAILING_EXT_REGEX = /\s+(PDF|JPG|JPEG|PNG|DOC|DOCX|XLS|XLSX|CSV|ZIP|RAR|TXT|TIFF|BMP|WEBP|GIF|MP4|AVI)\b/gi;
    let isCleaning = false;

    function cleanAttachmentChips() {
        if (isCleaning) return;
        isCleaning = true;
        try {
            const containers = document.querySelectorAll("div[name='new_voucher_bill_attachment_ids'], .crm_compact_attachments");
            containers.forEach((container) => {
                const chips = container.querySelectorAll(".o_attachment");
                chips.forEach((chip) => {
                    // 1. Remove separate extension badge tags
                    chip.querySelectorAll("small, span, div, b, em, strong").forEach((el) => {
                        if (el.tagName !== "A" && !el.classList.contains("fa") && !el.closest(".o_image_box") && !el.closest(".o_attachment_delete")) {
                            const txt = (el.textContent || "").trim();
                            if (EXT_REGEX.test(txt)) {
                                el.remove();
                            }
                        }
                    });

                    // 2. Clean <a> link text
                    const link = chip.querySelector("a");
                    if (link) {
                        Array.from(link.childNodes).forEach((node) => {
                            if (node.nodeType === Node.TEXT_NODE && TRAILING_EXT_REGEX.test(node.nodeValue)) {
                                node.nodeValue = node.nodeValue.replace(TRAILING_EXT_REGEX, "");
                            }
                        });
                    }

                    // 3. Clean direct text in caption
                    const caption = chip.querySelector(".caption");
                    if (caption) {
                        Array.from(caption.childNodes).forEach((node) => {
                            if (node.nodeType === Node.TEXT_NODE && TRAILING_EXT_REGEX.test(node.nodeValue)) {
                                node.nodeValue = node.nodeValue.replace(TRAILING_EXT_REGEX, "");
                            }
                        });
                    }
                });
            });
        } finally {
            isCleaning = false;
        }
    }

    const observer = new MutationObserver((mutations) => {
        if (isCleaning) return;
        // Only trigger if an attachment element was actually added or changed
        let shouldClean = false;
        for (const m of mutations) {
            if (m.target && (m.target.closest?.(".crm_compact_attachments") || m.target.closest?.("div[name='new_voucher_bill_attachment_ids']"))) {
                shouldClean = true;
                break;
            }
        }
        if (shouldClean) {
            cleanAttachmentChips();
        }
    });

    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener("DOMContentLoaded", () => {
            observer.observe(document.body, { childList: true, subtree: true });
        });
    }
}

// Line Reject Reason popup inside Recovery Wizard
document.addEventListener("click", function (ev) {
    const trigger = ev.target && ev.target.closest ? ev.target.closest("td[name='custom_reason'], [data-name='custom_reason'], .crm_line_reason_cell, button[name='action_open_line_reason_dialog'], .crm_btn_line_reason") : null;
    if (!trigger) return;

    // Only apply inside the recovery wizard modal
    if (!trigger.closest(".crm_batch_recovery_wizard_modal")) return;

    ev.preventDefault();
    ev.stopPropagation();

    const row = trigger.closest("tr");
    if (!row) return;

    const empName = row.querySelector("td[name='employee_id'], [data-name='employee_id']")?.textContent?.trim() || "Employee";
    const expType = row.querySelector("td[name='expense_type_id'], [data-name='expense_type_id']")?.textContent?.trim() || "Expense";

    const reasonCell = row.querySelector("td[name='custom_reason'], [data-name='custom_reason']") || trigger.closest("td");
    const reasonInput = reasonCell ? (reasonCell.querySelector("input, textarea") || reasonCell) : null;
    let currentVal = reasonInput ? (reasonInput.value !== undefined ? reasonInput.value : reasonInput.textContent.trim()) : "";
    if (currentVal === "+ Add Reason..." || currentVal === "Leave blank to use common reason...") {
        currentVal = "";
    }

    const existing = document.getElementById("crm_line_reason_modal_overlay");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.id = "crm_line_reason_modal_overlay";
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.45);z-index:99999;display:flex;align-items:center;justify-content:center;";

    overlay.innerHTML = `
        <div style="background:#fff;border-radius:6px;box-shadow:0 8px 20px rgba(0,0,0,0.22);width:88%;max-width:380px;overflow:hidden;border:1px solid #cbd5e1;font-family:inherit;">
            <div style="padding:8px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center;">
                <strong style="color:#0b3d91;font-size:13px;font-weight:600;">Reject Reason: ${empName} (${expType})</strong>
                <button type="button" id="crm_line_reason_close_x" style="background:none;border:none;font-size:16px;cursor:pointer;color:#64748b;line-height:1;padding:0 2px;">&times;</button>
            </div>
            <div style="padding:10px 12px;">
                <label style="display:block;font-size:11.5px;font-weight:600;color:#475569;margin-bottom:4px;">Detailed Line Reason / Remark:</label>
                <textarea id="crm_line_reason_textarea" rows="3" style="width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:4px;padding:6px 8px;font-size:12.5px;outline:none;resize:vertical;min-height:60px;" placeholder="Enter specific reason for this line...">${currentVal}</textarea>
            </div>
            <div style="padding:8px 12px;background:#f8fafc;border-top:1px solid #e2e8f0;display:flex;justify-content:flex-end;gap:6px;">
                <button type="button" id="crm_line_reason_cancel" style="padding:4px 10px;border:1px solid #cbd5e1;border-radius:4px;background:#fff;color:#334155;font-weight:500;cursor:pointer;font-size:12px;">Cancel</button>
                <button type="button" id="crm_line_reason_save" style="padding:4px 14px;border:none;border-radius:4px;background:#0b3d91;color:#fff;font-weight:600;cursor:pointer;font-size:12px;box-shadow:0 1px 2px rgba(0,0,0,0.08);">Save Reason</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const ta = document.getElementById("crm_line_reason_textarea");
    if (ta) {
        ta.focus();
        ta.selectionStart = ta.selectionEnd = ta.value.length;
    }

    function closeModal() {
        overlay.remove();
    }

    overlay.querySelector("#crm_line_reason_close_x").addEventListener("click", closeModal);
    overlay.querySelector("#crm_line_reason_cancel").addEventListener("click", closeModal);

    overlay.querySelector("#crm_line_reason_save").addEventListener("click", function () {
        const newVal = ta.value.trim();
        let targetInp = (reasonInput && reasonInput.tagName === "INPUT") ? reasonInput : (reasonCell ? reasonCell.querySelector("input") : null);
        if (targetInp) {
            targetInp.value = newVal;
            targetInp.title = newVal;
            targetInp.dispatchEvent(new Event("input", { bubbles: true }));
            targetInp.dispatchEvent(new Event("change", { bubbles: true }));
        }
        const btn = row.querySelector("button[name='action_open_line_reason_dialog'], .crm_btn_line_reason");
        if (btn) {
            btn.dataset.lineReason = newVal;
            if (newVal) {
                btn.title = newVal;
                btn.innerHTML = `<i class="fa fa-pencil text-crm-blue" style="font-size:15px;" title="${newVal}"></i>`;
            } else {
                btn.title = "Reject Reason";
                btn.innerHTML = `<i class="fa fa-plus-circle text-crm-blue" style="font-size:16px;"></i>`;
            }
        }
        closeModal();
    });
}, true);
