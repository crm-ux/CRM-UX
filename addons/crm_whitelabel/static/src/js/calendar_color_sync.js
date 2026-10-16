/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
/* Ensures Calendar popover header matches the task status color 100%:
* - Done -> Emerald Green (#d1fae5, text #065f46)
* - Pending -> Amber / Gold (#fef3c7, text #92400e)
* - In Progress -> Vibrant Blue (#e0f2fe, text #0369a1)
* - Issue / Complaint -> Crimson Red (#fee2e2, text #991b1b)
*/
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

    // Check if custom panel already exists - do NOT re-render repeatedly!
    if (sidebar.querySelector(".custom_calendar_filters_container")) {
        return;
    }

    const customPanel = document.createElement("div");
    customPanel.className = "custom_calendar_filters_container";
    sidebar.appendChild(customPanel);

    // Read real employee items from original Odoo DOM filters
    const empItems = [];
    document.querySelectorAll(".o_calendar_sidebar .o_calendar_filter:first-child .o_calendar_filter_item, .o_calendar_sidebar .o_calendar_filter[data-name='assigned_to_id'] .o_calendar_filter_item").forEach((item) => {
        const titleEl = item.querySelector(".o_cw_filter_title, label, span:last-child");
        const chk = item.querySelector("input[type='checkbox'], .form-check-input");
        const name = titleEl ? titleEl.textContent.trim() : item.textContent.trim();
        if (name && !name.toLowerCase().includes("everyone") && !name.toLowerCase().includes("all")) {
            empItems.push({
                name: name,
                initial: name.charAt(0).toUpperCase(),
                checked: chk ? chk.checked : true,
            });
            activeFilters.employees[name] = true;
        }
    });

    // Fallback employee list if DOM is loading
    const defaultEmps = [
        { name: "Anurag", initial: "A", checked: true },
        { name: "Pratham", initial: "P", checked: true },
        { name: "Vishal", initial: "V", checked: true },
    ];
    const finalEmployees = empItems.length > 0 ? empItems : defaultEmps;
    // Ensure initial state: all employees and statuses default to true (checked)
    finalEmployees.forEach(emp => {
        if (activeFilters.employees[emp.name] === undefined) {
            activeFilters.employees[emp.name] = true;
        }
    });

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
            eventEl.style.setProperty("border-left", `4px solid ${cfg.border}`, "important");
            eventEl.querySelectorAll("*").forEach((el) => {
                el.style.setProperty("color", cfg.text, "important");
                el.style.setProperty("font-weight", "700", "important");
                el.style.setProperty("font-size", "12px", "important");
                el.style.setProperty("background", "transparent", "important");
                el.style.setProperty("background-color", "transparent", "important");
            });
            // Remove any bullet, dot or time symbol before the event title
            eventEl.querySelectorAll(".fc-daygrid-event-dot, .fc-event-dot, .fc-event-time").forEach((dot) => {
                dot.style.setProperty("display", "none", "important");
            });
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
    const calendarContainer = document.querySelector(".o_calendar_view") || document.querySelector(".o_view_controller:has(.o_calendar_widget)") || document.querySelector(".o_content:has(.o_calendar_widget)");
    if (!calendarContainer) return;

    let tray = document.querySelector(".crm_unscheduled_tray");
    if (!tray) {
        tray = document.createElement("div");
        tray.className = "crm_unscheduled_tray";
        tray.innerHTML = `
            <div class="crm_unscheduled_header">
                <div class="crm_unscheduled_title">
                    <i class="fa fa-tasks text-primary"></i>
                    <span>Unscheduled Tasks</span>
                    <span class="crm_unscheduled_badge" id="crm_unscheduled_count">...</span>
                    <span class="crm_unscheduled_hint">(Tasks without deadline)</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <span class="text-muted small" id="crm_unscheduled_toggle_text">Click to Expand</span>
                    <i class="fa fa-chevron-up text-muted" id="crm_unscheduled_icon" style="transition: transform 0.2s;"></i>
                </div>
            </div>
            <div class="crm_unscheduled_body" id="crm_unscheduled_cards">
                <div class="text-muted small py-2">Loading tasks without deadline...</div>
            </div>
        `;

        calendarContainer.appendChild(tray);

        // Header click toggles expand/collapse
        const header = tray.querySelector(".crm_unscheduled_header");
        header.addEventListener("click", () => {
            const isExpanded = tray.classList.toggle("expanded");
            const icon = tray.querySelector("#crm_unscheduled_icon");
            const toggleText = tray.querySelector("#crm_unscheduled_toggle_text");
            if (isExpanded) {
                icon.style.transform = "rotate(180deg)";
                toggleText.textContent = "Click to Collapse";
            } else {
                icon.style.transform = "rotate(0deg)";
                toggleText.textContent = "Click to Expand";
            }
        });
    }

    // Refresh data at most once every 5 seconds or when called
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
                fields: ["id", "name", "assigned_to_id", "state", "task_color", "date_assigned"],
                limit: 30,
            },
        });

        const countBadge = tray.querySelector("#crm_unscheduled_count");
        const cardsContainer = tray.querySelector("#crm_unscheduled_cards");

        if (countBadge) {
            countBadge.textContent = `${tasks.length} Pending Tasks`;
        }

        if (cardsContainer) {
            if (!tasks || tasks.length === 0) {
                cardsContainer.innerHTML = `<div class="text-muted small py-2"><i class="fa fa-check-circle text-success me-1"></i> No pending unscheduled tasks!</div>`;
            } else {
                cardsContainer.innerHTML = tasks.map(t => {
                    const empName = t.assigned_to_id ? t.assigned_to_id[1] : "Unassigned";
                    const stateLabel = "PENDING";
                    const borderColor = "#f59e0b"; // pending amber
                    const stateBg = "#fef3c7";
                    const stateColor = "#78350f";

                    return `
                        <div class="crm_unscheduled_card" data-task-id="${t.id}" style="border-left-color: ${borderColor};">
                            <div class="crm_unscheduled_card_title" title="${t.name}">
                                ${t.name}
                            </div>
                            <div class="crm_unscheduled_card_meta">
                                <span><i class="fa fa-user me-1 text-muted"></i>${empName}</span>
                                <span class="crm_unscheduled_card_badge" style="background: ${stateBg}; color: ${stateColor};">
                                    ${stateLabel}
                                </span>
                            </div>
                        </div>
                    `;
                }).join("");

                // Click on card opens the task form view directly
                cardsContainer.querySelectorAll(".crm_unscheduled_card").forEach(card => {
                    card.addEventListener("click", () => {
                        const taskId = parseInt(card.dataset.taskId, 10);
                        if (taskId) {
                            const env = odoo.__WOWL_DEBUG__?.root?.env;
                            if (env?.services?.action) {
                                env.services.action.doAction({
                                    type: "ir.actions.act_window",
                                    res_model: "crm.task.management",
                                    res_id: taskId,
                                    views: [[false, "form"]],
                                    target: "current",
                                });
                            } else {
                                window.location.href = `/web#id=${taskId}&model=crm.task.management&view_type=form`;
                            }
                        }
                    });
                });
            }
        }
    } catch (err) {
        console.warn("Could not load unscheduled tasks:", err);
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
                }
            }
        }
    });

    const targetNode = document.body || document.documentElement;
    if (targetNode) {
        modalObserver.observe(targetNode, { childList: true, subtree: true });
    }
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            initPopoverObserver();
            listenForUnauthorizedDropRevert();
        });
    } else {
        initPopoverObserver();
        listenForUnauthorizedDropRevert();
    }
}
