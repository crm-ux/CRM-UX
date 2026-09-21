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

                // Move Configuration & Masters right below Lead & Quotation / Master Data
                const configH = Array.from(document.querySelectorAll(".o_horizontal_separator"))
                    .find(h => h.textContent.toUpperCase().includes("CONFIGURATION & MASTERS"));
                const leadH = Array.from(document.querySelectorAll(".o_horizontal_separator"))
                    .find(h => h.textContent.toUpperCase().includes("LEAD & QUOTATION"));

                // Convert every single dropdown in the Access Rights page into custom horizontal radio buttons
                document.querySelectorAll(".tab-pane:first-child .o_field_selection select, .tab-pane[name='access_rights'] .o_field_selection select").forEach(select => {
                    if (select.dataset.convertedToRadio) return;
                    select.dataset.convertedToRadio = "true";
                    select.style.display = "none";

                    const radioContainer = document.createElement("div");
                    radioContainer.className = "crm-custom-radios d-inline-flex align-items-center flex-wrap gap-3";

                    Array.from(select.options).forEach(opt => {
                        const label = document.createElement("label");
                        label.className = "d-inline-flex align-items-center gap-1 mb-0 me-3 cursor-pointer";

                        const input = document.createElement("input");
                        input.type = "radio";
                        input.name = select.name || select.id || Math.random();
                        input.value = opt.value;
                        input.checked = opt.selected;
                        input.className = "crm-radio-dot";

                        input.addEventListener("change", () => {
                            select.value = opt.value;
                            select.dispatchEvent(new Event("change", { bubbles: true }));
                        });

                        label.appendChild(input);
                        label.appendChild(document.createTextNode(" " + opt.text));
                        radioContainer.appendChild(label);
                    });

                    select.after(radioContainer);
                });

                if (configH && leadH) {
                    const configBox = configH.closest(".o_inner_group") || configH.closest(".o_group");
                    const leadBox = leadH.closest(".o_inner_group") || leadH.closest(".o_group");
                    if (configBox && leadBox && configBox.previousElementSibling !== leadBox) {
                        leadBox.after(configBox);
                    }
                }
            };

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
