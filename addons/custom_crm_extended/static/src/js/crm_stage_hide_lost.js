/** @odoo-module **/

function hideLostStagePill() {
    document.querySelectorAll(".o_statusbar_status button.o_arrow_button").forEach(btn => {
        const text = btn.textContent.replace(/\s+/g, " ").trim().toLowerCase();
        if (text.startsWith("lost")) {
            btn.style.setProperty("display", "none", "important");
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const observer = new MutationObserver(hideLostStagePill);
    observer.observe(document.body, { childList: true, subtree: true });
});
