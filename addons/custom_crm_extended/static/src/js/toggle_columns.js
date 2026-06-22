/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        // Watch for changes in parent record
        owl.useEffect(() => {
            try {
                const parentRecord = this.props?.list?.model?.root;
                if (!parentRecord || parentRecord.resModel !== 'sale.order') return;
                const showGST = parentRecord.data?.x_gst_included ?? false;
                const showMargin = parentRecord.data?.x_show_cost_profit ?? false;
                if (this.optionalActiveFields) {
                    if ('tax_ids' in this.optionalActiveFields) {
                        this.optionalActiveFields['tax_ids'] = showGST;
                    }
                    if ('x_cost' in this.optionalActiveFields) {
                        this.optionalActiveFields['x_cost'] = showMargin;
                        this.optionalActiveFields['x_profit'] = showMargin;
                        this.optionalActiveFields['x_profit_pct'] = showMargin;
                    }
                }
            } catch(e) {}
        });
    }
});
