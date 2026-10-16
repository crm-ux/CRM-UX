/** @odoo-module **/

/**
 * Ensures Calendar popover header matches the task status color 100%:
 * - Done -> Emerald Green (#d1fae5, text #065f46)
 * - Pending -> Amber / Gold (#fef3c7, text #92400e)
 * - In Progress -> Vibrant Blue (#e0f2fe, text #0369a1)
 * - Issue / Complaint -> Crimson Red (#fee2e2, text #991b1b)
 */
const STATUS_COLORS = {
    done: { bg: "#d1fae5", text: "#065f46", border: "#10b981", accent: "#10b981" },
    pending: { bg: "#fef3c7", text: "#92400e", border: "#f59e0b", accent: "#f59e0b" },
    in_progress: { bg: "#e0f2fe", text: "#0369a1", border: "#0284c7", accent: "#0284c7" },
    complaint: { bg: "#fee2e2", text: "#991b1b", border: "#ef4444", accent: "#ef4444" },
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
        header.querySelectorAll("*").forEach((el) => {
            el.style.setProperty("color", colorConfig.text, "important");
        });
    }
}

function renderCustomSidebarFilters() {
    const sidebar = document.querySelector(".o_calendar_sidebar");
    if (!sidebar) return;

    // Check if custom panel already exists
    let customPanel = sidebar.querySelector(".custom_calendar_filters_container");
    if (!customPanel) {
        customPanel = document.createElement("div");
        customPanel.className = "custom_calendar_filters_container";
        sidebar.appendChild(customPanel);
    }

    // Read real employee items from original Odoo DOM filters
    const empItems = [];
    document.querySelectorAll(".o_calendar_sidebar .o_calendar_filter:first-child .o_calendar_filter_item, .o_calendar_sidebar .o_calendar_filter[data-name='assigned_to_id'] .o_calendar_filter_item").forEach((item) => {
        const titleEl = item.querySelector(".o_cw_filter_title, label, span:last-child");
        const chk = item.querySelector("input[type='checkbox'], .form-check-input");
        const name = titleEl ? titleEl.textContent.trim() : item.textContent.trim();
        if (name) {
            empItems.push({
                name: name,
                initial: name.charAt(0).toUpperCase(),
                checked: chk ? chk.checked : true,
                originalCheckbox: chk,
            });
        }
    });

    // Fallback employee list if DOM is loading
    const finalEmployees = empItems.length > 0 ? empItems : [
        { name: "Anurag", initial: "A", checked: true },
        { name: "Pratham", initial: "P", checked: true },
        { name: "Vishal", initial: "V", checked: true },
    ];

    // Status definitions with 100% matched color scheme
    const statuses = [
        { key: "done", label: "Done", color: "#10b981", checked: true },
        { key: "in_progress", label: "In Progress", color: "#0284c7", checked: true },
        { key: "pending", label: "Pending", color: "#f59e0b", checked: true },
        { key: "complaint", label: "Issue / Complaint", color: "#ef4444", checked: true },
    ];

    // Read existing status checked states
    document.querySelectorAll(".o_calendar_sidebar .o_calendar_filter:last-child .o_calendar_filter_item").forEach((item) => {
        const text = item.textContent || "";
        const chk = item.querySelector("input[type='checkbox'], .form-check-input");
        const key = getStatusKey(text);
        if (key && chk) {
            const match = statuses.find(s => s.key === key);
            if (match) {
                match.checked = chk.checked;
                match.originalCheckbox = chk;
            }
        }
    });

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
                        <input type="checkbox" ${emp.checked ? "checked" : ""} style="accent-color: #0b3d91 !important;" />
                        <span class="custom_emp_badge">${emp.initial}</span>
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
                        <input type="checkbox" ${st.checked ? "checked" : ""} style="accent-color: ${st.color} !important;" />
                        <span class="custom_status_dot ${st.key}"></span>
                        <span>${st.label}</span>
                    </div>
                `).join("")}
            </div>
        </div>
    `;

    // Hook click handlers to drive Odoo filter checkboxes under the hood
    // Employee Items
    customPanel.querySelectorAll("#custom_emp_items .custom_filter_item").forEach((itemEl, idx) => {
        const chk = itemEl.querySelector("input[type='checkbox']");
        itemEl.addEventListener("click", (e) => {
            if (e.target !== chk) {
                chk.checked = !chk.checked;
            }
            const orig = finalEmployees[idx]?.originalCheckbox;
            if (orig) {
                orig.checked = chk.checked;
                orig.dispatchEvent(new Event("change", { bubbles: true }));
            }
        });
    });

    // Status Items
    customPanel.querySelectorAll("#custom_status_items .custom_filter_item").forEach((itemEl, idx) => {
        const chk = itemEl.querySelector("input[type='checkbox']");
        itemEl.addEventListener("click", (e) => {
            if (e.target !== chk) {
                chk.checked = !chk.checked;
            }
            const orig = statuses[idx]?.originalCheckbox;
            if (orig) {
                orig.checked = chk.checked;
                orig.dispatchEvent(new Event("change", { bubbles: true }));
            }
        });
    });
}

function syncCalendarElements() {
    renderCustomSidebarFilters();

    // Calendar Strips on Dates
    document.querySelectorAll(".o_calendar_view .fc-event, .o_calendar_view .fc-daygrid-event").forEach((eventEl) => {
        const key = getStatusKey(eventEl.textContent);
        if (key && STATUS_COLORS[key]) {
            const cfg = STATUS_COLORS[key];
            eventEl.style.setProperty("background-color", cfg.bg, "important");
            eventEl.style.setProperty("background", cfg.bg, "important");
            eventEl.style.setProperty("border-color", cfg.border, "important");
            eventEl.style.setProperty("border-left", `4px solid ${cfg.border}`, "important");
            eventEl.querySelectorAll("*").forEach((el) => {
                el.style.setProperty("color", cfg.text, "important");
            });
        }
    });

    // Popover Headers
    document.querySelectorAll(".popover, .o_cw_popover").forEach(applyPopoverColors);
}

// Global observer watching DOM updates
function initPopoverObserver() {
    if (typeof document === "undefined") return;
    const targetNode = document.body || document.documentElement;
    if (!targetNode) return;

    const observer = new MutationObserver((mutations) => {
        let shouldSync = false;
        for (const mutation of mutations) {
            if (mutation.addedNodes.length > 0) {
                shouldSync = true;
                break;
            }
        }
        if (shouldSync) {
            syncCalendarElements();
        }
    });

    observer.observe(targetNode, { childList: true, subtree: true });
    syncCalendarElements();
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initPopoverObserver);
    } else {
        initPopoverObserver();
    }
}
