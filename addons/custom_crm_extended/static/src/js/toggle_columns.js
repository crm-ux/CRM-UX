/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    computeOptionalActiveFields() {
        const result = super.computeOptionalActiveFields(...arguments);
        try {
            const parentRecord = this.props?.list?.model?.root;
            if (parentRecord && parentRecord.resModel === 'sale.order') {
                const showGST = parentRecord.data?.x_gst_included ?? false;
                const showMargin = parentRecord.data?.x_show_cost_profit ?? false;
                if ('tax_ids' in result) {
                    result['tax_ids'] = showGST;
                }
                if ('x_cost' in result) {
                    result['x_cost'] = showMargin;
                    result['x_profit'] = showMargin;
                    result['x_profit_pct'] = showMargin;
                }
            }
        } catch (e) {}
        return result;
    },

    getSectionSubtotal(record) {
        const parentRecord = this.props?.list?.model?.root;
        if (parentRecord && parentRecord.resModel === 'sale.order') {
            return ""; // Completely stop calculating or showing any subtotal on section rows!
        }
        return super.getSectionSubtotal ? super.getSectionSubtotal(...arguments) : "";
    },

    async onDeleteRecord(record) {
        const parentRecord = this.props?.list?.model?.root;
        if (parentRecord && parentRecord.resModel === 'sale.order' && record.data?.display_type === 'line_section') {
            // When deleting a section header, only delete this 1 single record — NEVER delete products below it!
            await record.delete();
            return;
        }
        return super.onDeleteRecord ? super.onDeleteRecord(...arguments) : record.delete();
    },

    setup() {
        super.setup ? super.setup() : null;
        const parentRecord = this.props?.list?.model?.root;
        if (parentRecord && parentRecord.resModel === 'sale.order') {
            // Intercept click on the section options button to directly delete this single section row
            const handleSectionClick = async (ev) => {
                const btn = ev.target.closest("tr.o_is_line_section td.o_list_section_options button, tr.o_is_line_section .o_list_section_options");
                if (!btn) return;
                ev.preventDefault();
                ev.stopPropagation();
                ev.stopImmediatePropagation();

                const row = btn.closest("tr.o_is_line_section");
                const dataId = row?.getAttribute("data-id");
                if (dataId) {
                    const record = (this.props?.list?.records || []).find(r => r.id === dataId);
                    if (record) {
                        if (typeof this.props?.list?.delete === "function") {
                            await this.props.list.delete(record);
                        } else if (record.resId) {
                            await record.delete();
                        } else {
                            await record.delete();
                        }
                    }
                }
            };
            document.addEventListener("click", handleSectionClick, true);

            // Auto-align section row colspan to span across all columns up to the trash button
            const fixSectionColspan = () => {
                document.querySelectorAll(".o_sale_order tr.o_is_line_section").forEach(tr => {
                    const table = tr.closest("table");
                    const headerCols = table ? (table.querySelectorAll("thead th").length || 12) : 12;
                    const targetSpan = String(Math.max(1, headerCols - 2));
                    const td = tr.querySelector("td[name='product_id']");
                    if (td && td.getAttribute("colspan") !== targetSpan) {
                        td.setAttribute("colspan", targetSpan);
                    }
                });
            };
            setTimeout(fixSectionColspan, 50);
            document.addEventListener("click", () => setTimeout(fixSectionColspan, 50));
            document.addEventListener("mouseover", (e) => {
                if (e.target.closest("tr.o_is_line_section")) {
                    fixSectionColspan();
                }
            });
        }
    },
});
