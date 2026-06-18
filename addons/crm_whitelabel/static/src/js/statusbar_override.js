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
