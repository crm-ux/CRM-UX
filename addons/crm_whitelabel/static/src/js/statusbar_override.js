/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";

patch(StatusBarField.prototype, {
    selectItem(item) {
        if (!item.isSelected) {
            return super.selectItem(item);
        }
    }
});

// White-label: replace "Odoo" in browser tab title
const CRM_TITLE = "YantraConnect CRM";
function updateTabTitle() {
    if (document.title.includes("Odoo")) {
        document.title = document.title.replace(/Odoo/g, CRM_TITLE);
    } else if (!document.title || document.title === "Odoo") {
        document.title = CRM_TITLE;
    }
}
updateTabTitle();
try {
    const titleEl = document.querySelector("title");
    if (titleEl) {
        const obs = new MutationObserver(updateTabTitle);
        obs.observe(titleEl, { subtree: true, characterData: true, childList: true });
    }
} catch (e) {}
