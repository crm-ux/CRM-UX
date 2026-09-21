/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.props.resModel === "res.users") {
            const labelMap = {
                "Sales": "Lead & Quotation",
                "Products": "Product Catalog",
                "Contact": "Contact Creation",
                "Export": "Excel Export",
            };

            const relabel = () => {
                document.querySelectorAll("label.o_form_label").forEach((lbl) => {
                    // Match the label text directly
                    const firstText = Array.from(lbl.childNodes)
                        .filter(node => node.nodeType === Node.TEXT_NODE)
                        .map(node => node.textContent.trim())
                        .join("");

                    if (labelMap[firstText]) {
                        // Replace only the text node, keep the tooltip '?' icon intact
                        for (let node of lbl.childNodes) {
                            if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() === firstText) {
                                node.textContent = labelMap[firstText] + " ";
                                break;
                            }
                        }
                    }
                });

                document.querySelectorAll(".o_horizontal_separator").forEach((h) => {
                    const txt = h.textContent.trim().toUpperCase();
                    if (txt === "SALES") {
                        h.textContent = "Lead & Quotation";
                    }
                });
            };

            // Move Configuration & Masters once right below Lead & Quotation (no scroll jump)
            const configH = Array.from(document.querySelectorAll(".o_horizontal_separator"))
                .find(h => h.textContent.toUpperCase().includes("CONFIGURATION & MASTERS"));
            const leadH = Array.from(document.querySelectorAll(".o_horizontal_separator"))
                .find(h => h.textContent.toUpperCase().includes("LEAD & QUOTATION"));

            if (configH && leadH) {
                const configBox = configH.closest(".o_inner_group") || configH.closest(".o_group");
                const leadBox = leadH.closest(".o_inner_group") || leadH.closest(".o_group");
                if (configBox && leadBox && !configBox.dataset.repositioned) {
                    leadBox.after(configBox);
                    configBox.dataset.repositioned = "true";
                }
            }

            let observer = null;
            onMounted(() => {
                relabel();
                observer = new MutationObserver(relabel);
                observer.observe(document.body, { childList: true, subtree: true });
            });

            onPatched(relabel);

            onWillUnmount(() => {
                if (observer) observer.disconnect();
            });
        }
    },
});
