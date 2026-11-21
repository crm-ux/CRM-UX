/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export const crmLiveToastService = {
    dependencies: ["bus_service", "notification", "action"],
    start(env, { bus_service, notification, action }) {
        if (!bus_service) return;

        const handleNotification = (notif) => {
            if (!notif) return;
            const type = notif.type;
            const payload = notif.payload || {};

            if (type === "crm_notification" || type === "simple_notification") {
                notification.add(payload.message || "", {
                    title: payload.title || _t("Notification"),
                    type: payload.type || "info",
                    sticky: payload.sticky || false,
                });

                // Auto reload active controller if applicable
                const current = action.currentController;
                if (current && current.model && typeof current.model.load === "function") {
                    current.model.load().catch(() => {});
                } else if (current && current.model && current.model.root && typeof current.model.root.load === "function") {
                    current.model.root.load().catch(() => {});
                }
            }
        };

        // 1. Odoo 17 EventBus Standard Listener
        try {
            if (typeof bus_service.addEventListener === "function") {
                bus_service.addEventListener("notification", ({ detail: notifications }) => {
                    for (const notif of (notifications || [])) {
                        handleNotification(notif);
                    }
                });
            }
        } catch (e) {}

        // 2. Legacy / Fallback Subscribe Listener
        try {
            if (typeof bus_service.subscribe === "function") {
                bus_service.subscribe("crm_notification", (payload) => {
                    handleNotification({ type: "crm_notification", payload });
                });
                bus_service.subscribe("simple_notification", (payload) => {
                    handleNotification({ type: "simple_notification", payload });
                });
            }
        } catch (e) {}
    },
};

registry.category("services").add("crmLiveToastService", crmLiveToastService);


