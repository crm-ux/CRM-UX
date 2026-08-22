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
                const mainButtons = document.querySelector(".o_control_panel_breadcrumbs > .o_control_panel_main_buttons");
                if (!container || !breadcrumb || !mainButtons) {
                    return;
                }
                const statusBarButtons = Array.from(document.querySelectorAll(".o_form_statusbar button"));
                const saveBtn = statusBarButtons.find((b) => b.textContent.trim() === "Save");
                const cancelBtn = statusBarButtons.find((b) => b.textContent.trim() === "Cancel");

                if (cancelBtn && !cancelBtn.dataset.customBound) {
                    cancelBtn.dataset.customBound = "true";
                    cancelBtn.addEventListener("click", (ev) => {
                        ev.preventDefault();
                        ev.stopPropagation();
                        this.discard();
                    });
                }
                if (saveBtn && !saveBtn.dataset.customBound) {
                    saveBtn.dataset.customBound = "true";
                    saveBtn.addEventListener("click", (ev) => {
                        ev.preventDefault();
                        ev.stopPropagation();
                        this.saveButtonClicked();
                    });
                }

                if (saveBtn && saveBtn.parentElement !== container) {
                    container.insertBefore(saveBtn, mainButtons.nextSibling);
                }
                if (cancelBtn && cancelBtn.parentElement !== container) {
                    container.insertBefore(cancelBtn, breadcrumb);
                }
                if (breadcrumb.previousElementSibling !== cancelBtn && breadcrumb.previousElementSibling !== saveBtn) {
                    const ref = cancelBtn || saveBtn;
                    if (ref) container.insertBefore(breadcrumb, ref.nextSibling);
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
    // async discard() {
    //     if (this.props.resModel === SALE_ORDER_MODEL) {
    //         const breadcrumbs = this.env.config?.breadcrumbs || [];
    //         if (breadcrumbs.length > 1) {
    //             const result = await super.discard(...arguments);
    //             this.env.services.notification.add("Operation cancelled.", {
    //                 type: "warning",
    //             });
    //             return result;
    //         }
    //         try {
    //             await this.actionService.doAction(
    //                 {
    //                     type: "ir.actions.act_window",
    //                     name: "Quotations",
    //                     res_model: "sale.order",
    //                     views: [[false, "list"], [false, "form"]],
    //                 },
    //                 { clearBreadcrumbs: true }
    //             );
    //         } catch (e) {
    //             console.error("Cancel redirect failed:", e);
    //         }
    //         this.env.services.notification.add("Operation cancelled.", {
    //             type: "warning",
    //         });
    //         return;
    //     }
    //     return super.discard(...arguments);
    // },

    // async discard() {
    //     if (this.props.resModel === SALE_ORDER_MODEL) {
    //         await this.model.root.discard();
    //         const breadcrumbs = this.env.config?.breadcrumbs || [];
    //         if (breadcrumbs.length > 1) {
    //             const prev = breadcrumbs[breadcrumbs.length - 2];
    //             if (prev && prev.jsId) {
    //                 this.actionService.restore(prev.jsId);
    //                 this.env.services.notification.add("Operation cancelled.", {
    //                     type: "warning",
    //                 });
    //                 return;
    //             }
    //         }
    //         try {
    //             await this.actionService.doAction(
    //                 {
    //                     type: "ir.actions.act_window",
    //                     name: "Quotations",
    //                     res_model: "sale.order",
    //                     views: [[false, "list"], [false, "form"]],
    //                 },
    //                 { clearBreadcrumbs: true }
    //             );
    //         } catch (e) {
    //             console.error("Cancel redirect failed:", e);
    //         }
    //         this.env.services.notification.add("Operation cancelled.", {
    //             type: "warning",
    //         });
    //         return;
    //     }
    //     return super.discard(...arguments);
    // },

    async discard() {
        if (this.props.resModel === SALE_ORDER_MODEL) {
            await this.model.root.discard();
            const breadcrumbs = this.env.config?.breadcrumbs || [];
            if (breadcrumbs.length > 1) {
                const prev = breadcrumbs[breadcrumbs.length - 2];
                if (prev && prev.jsId) {
                    this.actionService.restore(prev.jsId);
                    return;
                }
            }
            try {
                await this.actionService.doAction(
                    {
                        type: "ir.actions.act_window",
                        name: "Quotations",
                        res_model: "sale.order",
                        views: [[false, "list"], [false, "form"]],
                    },
                    { clearBreadcrumbs: true }
                );
            } catch (e) {
                console.error("Cancel redirect failed:", e);
            }
            return;
        }
        return super.discard(...arguments);
    },
});
