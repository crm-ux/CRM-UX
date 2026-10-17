/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

const STATUS_COLORS = {
    done: { bg: "#d1fae5", text: "#064e3b", border: "#10b981", accent: "#10b981" },
    pending: { bg: "#fef3c7", text: "#78350f", border: "#f59e0b", accent: "#f59e0b" },
    in_progress: { bg: "#e0f2fe", text: "#073656", border: "#0284c7", accent: "#0284c7" },
    complaint: { bg: "#fee2e2", text: "#7f1d1d", border: "#ef4444", accent: "#ef4444" },
};

function getStatusKey(text) {
    if (!text) return null;
    const lower = text.toLowerCase();
    if (lower.includes("in progress") || lower.includes("in_progress")) return "in_progress";
    if (lower.includes("pending")) return "pending";
    if (lower.includes("done")) return "done";
    if (lower.includes("issue") || lower.includes("complaint")) return "complaint";
    return null;
}

function applyPopoverColors(popoverEl) {
    if (!popoverEl) return;
    const statusKey = getStatusKey(popoverEl.textContent);
    if (!statusKey) return;

    const colorConfig = STATUS_COLORS[statusKey];
    const header = popoverEl.querySelector(".card-header, .popover-header, .o_cw_popover_header, [class*='header']");
    if (header) {
        header.style.setProperty("background-color", colorConfig.bg, "important");
        header.style.setProperty("background", colorConfig.bg, "important");
        header.style.setProperty("color", colorConfig.text, "important");
        header.style.setProperty("border-bottom", `1px solid ${colorConfig.border}`, "important");
        // Clear all background and borders from inner elements (badges, titles, spans)
        header.querySelectorAll("*").forEach((el) => {
            el.style.setProperty("color", colorConfig.text, "important");
            el.style.setProperty("background", "transparent", "important");
            el.style.setProperty("background-color", "transparent", "important");
            el.style.setProperty("border", "none", "important");
            el.style.setProperty("box-shadow", "none", "important");
        });
    }
}

// Keep track of active filters state
const activeFilters = {
    employees: {}, // name -> boolean
    statuses: {
        done: true,
        in_progress: true,
        pending: true,
        complaint: true,
    },
};

function filterCalendarEventsInDOM() {
    document.querySelectorAll(".o_calendar_view .fc-event, .o_calendar_view .fc-daygrid-event").forEach((eventEl) => {
        const text = eventEl.textContent || "";
        const statusKey = detectStatusKey(eventEl);

        let visible = true;

        // Check status filter
        if (statusKey && activeFilters.statuses[statusKey] === false) {
            visible = false;
        }

        // Check employee filter if any employee is toggled off
        const empKeys = Object.keys(activeFilters.employees);
        if (empKeys.length > 0) {
            const hasAnyFalse = empKeys.some(k => activeFilters.employees[k] === false);
            if (hasAnyFalse) {
                // If any employee name is mentioned in the event or if matched
                for (const empName of empKeys) {
                    if (text.toLowerCase().includes(empName.toLowerCase())) {
                        if (activeFilters.employees[empName] === false) {
                            visible = false;
                        }
                        break;
                    }
                }
            }
        }

        if (visible) {
            eventEl.style.removeProperty("display");
        } else {
            eventEl.style.setProperty("display", "none", "important");
        }
    });
}

function triggerNativeOdooFilter(filterText, shouldCheck) {
    // Search across all native Odoo filter items
    const nativeItems = document.querySelectorAll(".o_calendar_sidebar .o_calendar_filter .o_calendar_filter_item");
    for (const item of nativeItems) {
        const itemText = (item.textContent || "").trim();
        if (itemText.toLowerCase().includes(filterText.toLowerCase())) {
            const chk = item.querySelector("input[type='checkbox'], .form-check-input");
            const clickable = chk || item.querySelector("label") || item;
            if (clickable) {
                if (chk) {
                    if (chk.checked !== shouldCheck) {
                        clickable.click();
                    }
                } else {
                    clickable.click();
                }
            }
            break;
        }
    }
}

function renderCustomSidebarFilters() {
    const sidebar = document.querySelector(".o_calendar_sidebar");
    if (!sidebar) return;

    // Keep customPanel reference and update dynamic employees list
    let customPanel = sidebar.querySelector(".custom_calendar_filters_container");
    if (!customPanel) {
        customPanel = document.createElement("div");
        customPanel.className = "custom_calendar_filters_container";
        sidebar.appendChild(customPanel);
    }

    // Read real employee items from original Odoo DOM filters + visible events in calendar
    const empItems = [];
    const seenNames = new Set();
    const statusWords = ["done", "in progress", "pending", "issue", "complaint", "everyone", "all"];

    // 1. From native Odoo filters
    document.querySelectorAll(".o_calendar_sidebar .o_calendar_filter_item, .o_calendar_sidebar [data-name='assigned_to_id'] .o_calendar_filter_item").forEach((item) => {
        const titleEl = item.querySelector(".o_cw_filter_title, label, span:last-child");
        const chk = item.querySelector("input[type='checkbox'], .form-check-input");
        const name = titleEl ? titleEl.textContent.trim() : item.textContent.trim();
        const lowerName = name.toLowerCase();
        const isStatusWord = statusWords.some(w => lowerName.includes(w));

        if (name && !isStatusWord && !seenNames.has(name)) {
            seenNames.add(name);
            empItems.push({
                name: name,
                initial: name.charAt(0).toUpperCase(),
                checked: chk ? chk.checked : true,
            });
            activeFilters.employees[name] = true;
        }
    });

    // 2. Also dynamically collect any assigned employees from visible events on calendar
    document.querySelectorAll(".fc-event, .fc-daygrid-event").forEach(ev => {
        const title = ev.getAttribute("title") || ev.textContent || "";
        // If event contains employee name
        const match = title.match(/Assigned Employee[:\s]+([^\n\r]+)/i);
        if (match && match[1]) {
            const emp = match[1].trim();
            if (emp && !statusWords.includes(emp.toLowerCase()) && !seenNames.has(emp)) {
                seenNames.add(emp);
                empItems.push({ name: emp, initial: emp.charAt(0).toUpperCase(), checked: true });
                activeFilters.employees[emp] = true;
            }
        }
    });

    const finalEmployees = empItems;
    finalEmployees.forEach(emp => {
        if (activeFilters.employees[emp.name] === undefined) {
            activeFilters.employees[emp.name] = true;
        }
    });

    // Check if the rendered employees have changed; if not, don't destroy DOM
    const currentRenderedNames = Array.from(customPanel.querySelectorAll("#custom_emp_items .custom_filter_item")).map(el => el.dataset.emp);
    const newNames = finalEmployees.map(e => e.name);
    if (currentRenderedNames.length === newNames.length && currentRenderedNames.every((v, i) => v === newNames[i])) {
        return; // No changes, leave DOM as is!
    }

    // Status definitions with 100% matched color scheme
    const statuses = [
        { key: "done", label: "Done", color: "#10b981", checked: activeFilters.statuses.done !== false },
        { key: "in_progress", label: "In Progress", color: "#0284c7", checked: activeFilters.statuses.in_progress !== false },
        { key: "pending", label: "Pending", color: "#f59e0b", checked: activeFilters.statuses.pending !== false },
        { key: "complaint", label: "Issue / Complaint", color: "#ef4444", checked: activeFilters.statuses.complaint !== false },
    ];

    // Compute whether all are checked for master checkbox
    const allEmpChecked = finalEmployees.every(emp => activeFilters.employees[emp.name] !== false);
    const allStatusChecked = statuses.every(st => activeFilters.statuses[st.key] !== false);

    // Build Custom HTML structure
    customPanel.innerHTML = `
        <!-- 1. Assigned Employee Group -->
        <div class="custom_filter_group">
            <div class="custom_filter_header" id="custom_hdr_emp">
                <input type="checkbox" id="chk_all_emp" checked style="accent-color: #0b3d91 !important;" />
                <span>Assigned Employee</span>
            </div>
            <div class="custom_filter_items" id="custom_emp_items">
                ${finalEmployees.map(emp => `
                    <div class="custom_filter_item" data-emp="${emp.name}">
                        <input type="checkbox" checked style="accent-color: #0b3d91 !important;" />
                        <span>${emp.name}</span>
                    </div>
                `).join("")}
            </div>
        </div>

        <!-- 2. Status Group -->
        <div class="custom_filter_group mt-2">
            <div class="custom_filter_header" id="custom_hdr_status">
                <input type="checkbox" id="chk_all_status" checked style="accent-color: #0b3d91 !important;" />
                <span>Status</span>
            </div>
            <div class="custom_filter_items" id="custom_status_items">
                ${statuses.map(st => `
                    <div class="custom_filter_item status_${st.key}" data-status="${st.key}">
                        <input type="checkbox" checked style="accent-color: ${st.color} !important;" />
                        <span>${st.label}</span>
                    </div>
                `).join("")}
            </div>
        </div>
    `;

    // Explicitly guarantee every checkbox property is checked = true on DOM insertion
    customPanel.querySelectorAll("input[type='checkbox']").forEach(chk => {
        chk.checked = true;
    });

    // Master checkbox: Assigned Employee All
    const chkAllEmp = customPanel.querySelector("#chk_all_emp");
    chkAllEmp.addEventListener("change", () => {
        const isChecked = chkAllEmp.checked;
        customPanel.querySelectorAll("#custom_emp_items .custom_filter_item input[type='checkbox']").forEach(chk => {
            chk.checked = isChecked;
        });
        finalEmployees.forEach(emp => {
            activeFilters.employees[emp.name] = isChecked;
            triggerNativeOdooFilter(emp.name, isChecked);
        });
        filterCalendarEventsInDOM();
    });

    // Employee Individual Items
    customPanel.querySelectorAll("#custom_emp_items .custom_filter_item").forEach((itemEl, idx) => {
        const chk = itemEl.querySelector("input[type='checkbox']");
        const empName = finalEmployees[idx]?.name;
        itemEl.addEventListener("click", (e) => {
            if (e.target !== chk) {
                chk.checked = !chk.checked;
            }
            if (empName) {
                activeFilters.employees[empName] = chk.checked;
                triggerNativeOdooFilter(empName, chk.checked);
            }
            // Sync master header checkbox
            const anyUnchecked = finalEmployees.some(emp => activeFilters.employees[emp.name] === false);
            chkAllEmp.checked = !anyUnchecked;
            filterCalendarEventsInDOM();
        });
    });

    // Master checkbox: Status All
    const chkAllStatus = customPanel.querySelector("#chk_all_status");
    chkAllStatus.addEventListener("change", () => {
        const isChecked = chkAllStatus.checked;
        customPanel.querySelectorAll("#custom_status_items .custom_filter_item input[type='checkbox']").forEach(chk => {
            chk.checked = isChecked;
        });
        statuses.forEach(st => {
            activeFilters.statuses[st.key] = isChecked;
            triggerNativeOdooFilter(st.label, isChecked);
        });
        filterCalendarEventsInDOM();
    });

    // Status Individual Items
    customPanel.querySelectorAll("#custom_status_items .custom_filter_item").forEach((itemEl, idx) => {
        const chk = itemEl.querySelector("input[type='checkbox']");
        const st = statuses[idx];
        itemEl.addEventListener("click", (e) => {
            if (e.target !== chk) {
                chk.checked = !chk.checked;
            }
            if (st) {
                activeFilters.statuses[st.key] = chk.checked;
                triggerNativeOdooFilter(st.label, chk.checked);
            }
            // Sync master header checkbox
            const anyUnchecked = statuses.some(s => activeFilters.statuses[s.key] === false);
            chkAllStatus.checked = !anyUnchecked;
            filterCalendarEventsInDOM();
        });
    });
}

function detectStatusKey(eventEl) {
    if (!eventEl) return null;

    // 1. Direct class checks (matches model task_color 1, 2, 10, 9)
    const cls = eventEl.className || "";
    if (cls.includes("o_calendar_color_10")) return "done";
    if (cls.includes("o_calendar_color_1")) return "pending";
    if (cls.includes("o_calendar_color_2")) return "in_progress";
    if (cls.includes("o_calendar_color_9")) return "complaint";

    // 2. Textual matching
    const textKey = getStatusKey(eventEl.textContent);
    if (textKey) return textKey;

    // 3. Check child elements or badges
    const childBadges = eventEl.querySelectorAll(".badge, [class*='badge'], [class*='state'], [data-field='state']");
    for (const badge of childBadges) {
        const k = getStatusKey(badge.textContent);
        if (k) return k;
    }

    return null;
}

function syncCalendarElements() {
    renderCustomSidebarFilters();

    // Calendar Strips on Dates - Strict unified colors across every login
    document.querySelectorAll(".o_calendar_view .fc-event, .o_calendar_view .fc-daygrid-event").forEach((eventEl) => {
        const key = detectStatusKey(eventEl) || "pending";
        if (key && STATUS_COLORS[key]) {
            const cfg = STATUS_COLORS[key];
            eventEl.style.setProperty("background-color", cfg.bg, "important");
            eventEl.style.setProperty("background", cfg.bg, "important");
            eventEl.style.setProperty("border-color", cfg.border, "important");
            eventEl.style.setProperty("border", `1px solid ${cfg.border}`, "important");
            eventEl.style.setProperty("border-left", `1px solid ${cfg.border}`, "important");
            eventEl.querySelectorAll("*").forEach((el) => {
                el.style.setProperty("color", cfg.text, "important");
                el.style.setProperty("font-weight", "700", "important");
                el.style.setProperty("font-size", "inherit", "important");
                el.style.setProperty("background", "transparent", "important");
                el.style.setProperty("background-color", "transparent", "important");
            });
            // Remove any bullet, dot, time symbol, or avatar icon before the event title
            eventEl.querySelectorAll(".fc-daygrid-event-dot, .fc-event-dot, .fc-event-time, img, .o_avatar, .rounded-circle").forEach((dot) => {
                dot.style.setProperty("display", "none", "important");
                dot.remove();
            });

            // Ensure inner title elements have no left border or background artifacts
            const titleEl = eventEl.querySelector(".fc-event-title, .fc-event-main");
            if (titleEl) {
                titleEl.style.setProperty("border", "none", "important");
                titleEl.style.setProperty("border-left", "none", "important");
            }
        }
    });

    // Apply active filter show/hide
    filterCalendarEventsInDOM();

    // Render Bottom Collapsible Tray for tasks without deadline
    renderUnscheduledTasksTray();

    // Trigger auto-scheduler for all recurring tasks so all future occurrences exist in DB
    ensureAllRecurringTasksGenerated();

    // Popover Headers
    document.querySelectorAll(".popover, .o_cw_popover").forEach(applyPopoverColors);
}

let hasTriggeredRecurringSync = false;
async function ensureAllRecurringTasksGenerated() {
    if (hasTriggeredRecurringSync) return;
    hasTriggeredRecurringSync = true;
    try {
        const generated = await rpc("/web/dataset/call_kw", {
            model: "crm.task.management",
            method: "action_auto_generate_all_recurring",
            args: [[]],
            kwargs: {},
        });
        if (generated) {
            // Re-render or trigger active navigation to pull newly generated monthly tasks from DB
            const activeNav = document.querySelector(".o_calendar_navigation .active, .fc-button-active");
            if (activeNav) activeNav.click();
        }
    } catch (e) {
        // silent
    }
}

let isUnscheduledLoading = false;
let lastUnscheduledFetch = 0;

async function renderUnscheduledTasksTray() {
    // Idea 3: The bottom tray is removed so calendar dates and sidebar are never covered!
    const existingBottomTray = document.querySelector(".crm_unscheduled_tray");
    if (existingBottomTray) {
        existingBottomTray.remove();
    }

    // Refresh data at most once every 5 seconds
    const now = Date.now();
    if (isUnscheduledLoading || now - lastUnscheduledFetch < 5000) return;
    isUnscheduledLoading = true;
    lastUnscheduledFetch = now;

    try {
        const tasks = await rpc("/web/dataset/call_kw", {
            model: "crm.task.management",
            method: "search_read",
            args: [[["date_deadline", "=", false], ["state", "=", "pending"]]],
            kwargs: {
                fields: ["id"],
                limit: 100,
            },
        });

        window.__crm_unscheduled_count = tasks ? tasks.length : 0;
        const topBadge = document.querySelector(".crm_btn_unscheduled_tasks .badge");
        if (topBadge) {
            topBadge.textContent = window.__crm_unscheduled_count;
        }
    } catch (err) {
        console.warn("Could not fetch unscheduled count:", err);
    } finally {
        isUnscheduledLoading = false;
    }
}

// Global observer watching DOM updates
let syncTimeout = null;
function debouncedSync() {
    if (syncTimeout) clearTimeout(syncTimeout);
    syncTimeout = setTimeout(() => {
        syncCalendarElements();
    }, 100);
}

function initPopoverObserver() {
    if (typeof document === "undefined") return;
    const targetNode = document.body || document.documentElement;
    if (!targetNode) return;

    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node && node.nodeType === 1) {
                    if (node.classList?.contains("custom_calendar_filters_container")) {
                        continue;
                    }
                    if (
                        node.matches?.(".o_calendar_view, .o_calendar_sidebar, .popover, .fc-event") ||
                        node.querySelector?.(".o_calendar_view, .o_calendar_sidebar, .popover, .fc-event")
                    ) {
                        debouncedSync();
                        return;
                    }
                }
            }
        }
    });

    observer.observe(targetNode, { childList: true, subtree: true });
    debouncedSync();
}

// Auto-revert unauthorized drag and drop in Calendar view & ensure 100% database sync
function listenForUnauthorizedDropRevert() {
    function reloadCalendar() {
        // Trigger calendar reload so the calendar model and view are 100% refreshed from database
        const activeNav = document.querySelector(".o_calendar_navigation .active, .fc-button-active");
        if (activeNav) {
            activeNav.click();
        } else {
            const todayBtn = document.querySelector(".o_calendar_button_today, .fc-today-button");
            if (todayBtn) todayBtn.click();
        }
    }

    window.addEventListener("error", (e) => {
        if (e.message && (e.message.includes("not authorized to modify") || e.message.includes("earlier than"))) {
            reloadCalendar();
        }
    });

    // Observer to detect when the UserError modal closes, immediately reload the calendar to snap event back to original date
    const modalObserver = new MutationObserver((mutations) => {
        for (const m of mutations) {
            for (const node of m.addedNodes) {
                if (node && node.nodeType === 1 && (node.classList?.contains("o_dialog") || node.classList?.contains("modal"))) {
                    const text = node.textContent || "";
                    if (text.includes("not authorized to modify") || text.includes("earlier than") || text.includes("Cannot reschedule")) {
                        // User error appeared for drag & drop
                        const closeBtns = node.querySelectorAll("button, .btn-close, .btn");
                        closeBtns.forEach(btn => {
                            btn.addEventListener("click", () => {
                                setTimeout(reloadCalendar, 100);
                            });
                        });
                    }
                    // Clean up modal search bar: remove toggler dropdown and popup menu
                    node.querySelectorAll(".o_searchview_dropdown_toggler, button.o_dropdown_button, .o_search_bar_menu").forEach(el => {
                        el.remove();
                    });
                }
            }
        }
    });

    const targetNode = document.body || document.documentElement;
    if (targetNode) {
        modalObserver.observe(targetNode, { childList: true, subtree: true });
    }
}

/**
 * Universal Copy-Paste support for Task Attachments
 * Captures clipboard paste (Ctrl+V / Cmd+V) containing images, screenshots, or files
 * and dispatches them directly to the many2many_binary file upload input in both Form & Wizard!
 */
function initAttachmentPasteSupport() {
    window.addEventListener("paste", function (e) {
        // If user is focused on a text input/textarea that is not in the attachment zone, let normal text paste
        const activeEl = document.activeElement;
        const isTextInput = activeEl && (activeEl.tagName === "INPUT" && activeEl.type === "text" || activeEl.tagName === "TEXTAREA" || activeEl.isContentEditable);

        const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items;
        if (!items || !items.length) return;

        let pastedFiles = [];
        for (let i = 0; i < items.length; i++) {
            if (items[i].kind === "file") {
                const file = items[i].getAsFile();
                if (file) {
                    // If filename is generic image.png, give it a timestamped name
                    let finalFile = file;
                    if (file.name === "image.png") {
                        const nowStr = new Date().toISOString().replace(/[-:T.]/g, "").slice(0, 14);
                        finalFile = new File([file], `Pasted_Screenshot_${nowStr}.png`, { type: file.type });
                    }
                    pastedFiles.push(finalFile);
                }
            }
        }

        if (pastedFiles.length === 0) return;

        // Find the active modal wizard or main task form
        const activeModal = document.querySelector(".modal.show, .modal-dialog, .o_dialog");
        const scope = activeModal || document.querySelector(".crm-task-management-form, .o_form_view") || document;

        // Locate the file input inside many2many_binary widget
        const fileInput = scope.querySelector(".o_field_many2many_binary input[type='file'], [name='attachment_ids'] input[type='file'], .crm-wizard-dropzone input[type='file']");

        if (fileInput) {
            e.preventDefault();
            e.stopPropagation();

            const dataTransfer = new DataTransfer();
            pastedFiles.forEach(f => dataTransfer.items.add(f));
            fileInput.files = dataTransfer.files;

            // Trigger change event so Odoo's binary widget uploads the file(s)
            fileInput.dispatchEvent(new Event("change", { bubbles: true }));

            // Show a brief friendly toast/border feedback
            const dropzone = fileInput.closest(".crm-wizard-dropzone, .o_field_many2many_binary, .o_field_widget");
            if (dropzone) {
                dropzone.style.transition = "all 0.3s ease";
                dropzone.style.boxShadow = "0 0 0 3px rgba(11, 61, 145, 0.4)";
                setTimeout(() => {
                    dropzone.style.boxShadow = "";
                }, 1000);
            }
        }
    }, true);
}

/**
 * Bulk Multi-file Upload Bar injection for Task Attachment Table
 * Allows selecting 5, 10, or 20 files at once from file explorer
 */
function initTaskBulkUploadSupport() {
    function injectBulkBar() {
        const attachmentField = document.querySelector("[name='task_attachment_ids']");
        if (!attachmentField || attachmentField.querySelector(".crm_task_bulk_upload_wrap")) return;

        const wrap = document.createElement("div");
        wrap.className = "crm_task_bulk_upload_wrap";
        wrap.innerHTML = `
            <div style="font-size: 13px; color: #475569; display: flex; align-items: center; gap: 8px;">
                <i class="fa fa-cloud-upload" style="font-size: 1.25rem; color: #0b3d91;"></i>
                <span><strong>Multi-file Upload:</strong> Select or drag & drop 10-20 files at once</span>
            </div>
            <button type="button" class="crm_btn_bulk_upload">
                <i class="fa fa-folder-open-o"></i> Select Multiple Files
            </button>
            <input type="file" multiple style="display: none;" class="crm_bulk_hidden_input"/>
        `;

        const hiddenInput = wrap.querySelector(".crm_bulk_hidden_input");
        const btn = wrap.querySelector(".crm_btn_bulk_upload");

        btn.addEventListener("click", () => hiddenInput.click());

        hiddenInput.addEventListener("change", async (ev) => {
            const files = ev.target.files;
            if (!files || !files.length) return;

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const addLineBtn = attachmentField.querySelector(".o_field_x2many_list_row_add a");
                if (addLineBtn) {
                    addLineBtn.click();
                    await new Promise(r => setTimeout(r, 200));

                    const lastRow = attachmentField.querySelector(".o_data_row:last-child, tr:last-child");
                    if (lastRow) {
                        const nameInput = lastRow.querySelector("input[name='name']");
                        const fileInp = lastRow.querySelector("input[type='file']");
                        if (nameInput) {
                            nameInput.value = file.name;
                            nameInput.dispatchEvent(new Event("change", { bubbles: true }));
                        }
                        if (fileInp) {
                            const dt = new DataTransfer();
                            dt.items.add(file);
                            fileInp.files = dt.files;
                            fileInp.dispatchEvent(new Event("change", { bubbles: true }));
                        }
                    }
                }
            }
        });

        attachmentField.prepend(wrap);
    }

    const observer = new MutationObserver(() => {
        injectBulkBar();
    });

    const targetNode = document.body || document.documentElement;
    if (targetNode) {
        observer.observe(targetNode, { childList: true, subtree: true });
    }
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            initPopoverObserver();
            listenForUnauthorizedDropRevert();
            initAttachmentPasteSupport();
            initTaskBulkUploadSupport();
        });
    } else {
        initPopoverObserver();
        listenForUnauthorizedDropRevert();
        initAttachmentPasteSupport();
        initTaskBulkUploadSupport();
    }
}
