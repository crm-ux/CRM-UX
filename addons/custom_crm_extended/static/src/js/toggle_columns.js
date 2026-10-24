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

    async onDeleteRecord(record) {
        const parentRecord = this.props?.list?.model?.root;
        if (parentRecord && parentRecord.resModel === 'sale.order' && record.data?.display_type === 'line_section') {
            // When deleting a section header, only delete the section header itself — NEVER delete products below it!
            await record.delete();
            return;
        }
        return super.onDeleteRecord ? super.onDeleteRecord(...arguments) : record.delete();
    },
});
