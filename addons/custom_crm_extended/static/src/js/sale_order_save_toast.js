/** @odoo-module **/
import { onMounted, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

const SALE_ORDER_MODEL = "sale.order";

patch(FormController.prototype, {
    setup() {
        super.setup();
        if (this.props.resModel === SALE_ORDER_MODEL) {
            let observer = null;
            const reorderToolbar = () => {
                const container = document.querySelector(".o_control_panel_breadcrumbs");
                const breadcrumb = document.querySelector(".o_control_panel_breadcrumbs > .o_breadcrumb");
                const statusIndicator = document.querySelector(".o_control_panel_breadcrumbs > .o_form_status_indicator");
                if (container && breadcrumb && statusIndicator) {
                    if (breadcrumb.previousElementSibling !== statusIndicator) {
                        container.insertBefore(breadcrumb, statusIndicator.nextSibling);
                    }
                }
            };
            onMounted(() => {
                reorderToolbar();
                const panel = document.querySelector(".o_control_panel_breadcrumbs");
                if (panel) {
                    observer = new MutationObserver(() => reorderToolbar());
                    observer.observe(panel, { childList: true, subtree: true });
                }
            });
            onWillUnmount(() => {
                if (observer) observer.disconnect();
            });
        }
    },

    async saveButtonClicked() {
        if (this.props.resModel === SALE_ORDER_MODEL) {
            const saved = await super.saveButtonClicked(...arguments);
            if (saved) {
                this.env.services.notification.add("Record saved successfully.", {
                    type: "success",
                });
            }
            return saved;
        }
        return super.saveButtonClicked(...arguments);
    },
    async discard() {
        if (this.props.resModel === SALE_ORDER_MODEL) {
            const result = await super.discard(...arguments);
            this.env.services.notification.add("Operation cancelled.", {
                type: "warning",
            });
            return result;
        }
        return super.discard(...arguments);
    },
});
