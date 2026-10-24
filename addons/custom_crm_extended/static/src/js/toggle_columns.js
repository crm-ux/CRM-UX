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
            // Listen for clicks on section delete icon
            const originalOnSectionDelete = this.onSectionDelete;
            if (originalOnSectionDelete) {
                this.onSectionDelete = async (record) => {
                    // Only delete the section row itself!
                    await record.delete();
                };
            }
        }
    },
});
