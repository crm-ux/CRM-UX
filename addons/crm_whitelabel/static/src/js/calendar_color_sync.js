/** @odoo-module **/

/**
 * Ensures Calendar popover header matches the task status color 100%:
 * - Done -> Emerald Green (#d1fae5, text #065f46)
 * - Pending -> Amber / Gold (#fef3c7, text #92400e)
 * - In Progress -> Vibrant Blue (#e0f2fe, text #0369a1)
 * - Issue / Complaint -> Crimson Red (#fee2e2, text #991b1b)
 */
const STATUS_COLORS = {
    done: { bg: "#d1fae5", text: "#065f46", border: "#a7f3d0" },
    pending: { bg: "#fef3c7", text: "#92400e", border: "#fde68a" },
    in_progress: { bg: "#e0f2fe", text: "#0369a1", border: "#bae6fd" },
    complaint: { bg: "#fee2e2", text: "#991b1b", border: "#fecaca" },
};

function applyPopoverHeaderColor(popoverEl) {
    if (!popoverEl) return;
    const textContent = popoverEl.textContent || "";
    let matchedColor = null;

    if (textContent.includes("In Progress")) {
        matchedColor = STATUS_COLORS.in_progress;
    } else if (textContent.includes("Pending")) {
        matchedColor = STATUS_COLORS.pending;
    } else if (textContent.includes("Done")) {
        matchedColor = STATUS_COLORS.done;
    } else if (textContent.includes("Issue") || textContent.includes("Complaint")) {
        matchedColor = STATUS_COLORS.complaint;
    }

    if (matchedColor) {
        const header = popoverEl.querySelector(".card-header, .popover-header, .o_cw_popover_header, [class*='header']");
        if (header) {
            header.style.setProperty("background-color", matchedColor.bg, "important");
            header.style.setProperty("background", matchedColor.bg, "important");
            header.style.setProperty("color", matchedColor.text, "important");
            header.style.setProperty("border-bottom-color", matchedColor.border, "important");
            header.querySelectorAll("*").forEach((el) => {
                el.style.setProperty("color", matchedColor.text, "important");
            });
        }
    }
}

// Global observer watching popovers when injected by Odoo / FullCalendar
if (typeof window !== "undefined") {
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeType === 1) {
                    if (node.matches && (node.matches(".popover") || node.matches(".o_cw_popover") || node.querySelector?.(".o_cw_popover"))) {
                        applyPopoverHeaderColor(node);
                    }
                }
            }
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
}
