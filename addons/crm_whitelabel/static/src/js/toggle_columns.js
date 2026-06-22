/** Auto show/hide Cost, Profit, Margin% columns based on Show Margin toggle */
import { patch } from "@web/core/utils/patch";
import { SaleOrderLineListRenderer } from "@sale/js/sale_order_line_renderer";

patch(SaleOrderLineListRenderer.prototype, {
    get optionalColumns() {
        const cols = super.optionalColumns;
        // Check if parent record has x_show_cost_profit
        const record = this.props.list?.model?.root;
        if (record) {
            const showMargin = record.data?.x_show_cost_profit;
            const marginCols = ['x_cost', 'x_profit', 'x_profit_pct'];
            return cols.map(col => {
                if (marginCols.includes(col.name)) {
                    return { ...col, optional: showMargin ? 'show' : 'hide' };
                }
                return col;
            });
        }
        return cols;
    }
});
