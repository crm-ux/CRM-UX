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

            // Position Configuration & Masters right below the first two columns
            const configGroup = Array.from(document.querySelectorAll(".o_inner_group, .o_group"))
                .find(el => el.textContent.includes("Configuration & Masters") || el.textContent.includes("CONFIGURATION & MASTERS"));
            const leadQuoteH = Array.from(document.querySelectorAll(".o_horizontal_separator"))
                .find(el => el.textContent.includes("Lead & Quotation") || el.textContent.includes("LEAD & QUOTATION"));

            if (configGroup && leadQuoteH) {
                const parentContainer = leadQuoteH.closest(".o_inner_group, .o_group");
                if (parentContainer && parentContainer.parentElement && configGroup.parentElement !== parentContainer.parentElement) {
                    parentContainer.parentElement.insertBefore(configGroup, parentContainer.nextSibling);
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
