/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export const crmLiveToastService = {
    dependencies: ["bus_service", "notification", "action"],
    start(env, { bus_service, notification, action }) {
        if (!bus_service) return;

        const seenNotifs = new Map();

        const handleNotification = (notif) => {
            if (!notif) return;
            const type = notif.type;
            const payload = notif.payload || {};

            if (type === "crm_notification") {
                const key = `${payload.title || ""}_${payload.message || ""}`;
                const now = Date.now();
                if (seenNotifs.has(key) && (now - seenNotifs.get(key)) < 2500) {
                    return; // Ignore duplicate notification within 2.5 seconds
                }
                seenNotifs.set(key, now);

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
            } else if (type === "simple_notification") {
                // simple_notification is already displayed natively by Odoo core notification service.
                // We only reload active controller without duplicating the popup toast.
                const current = action.currentController;
                if (current && current.model && typeof current.model.load === "function") {
                    current.model.load().catch(() => {});
                } else if (current && current.model && current.model.root && typeof current.model.root.load === "function") {
                    current.model.root.load().catch(() => {});
                }
            }
        };

        // Odoo 17 EventBus Standard Listener
        try {
            if (typeof bus_service.addEventListener === "function") {
                bus_service.addEventListener("notification", ({ detail: notifications }) => {
                    for (const notif of (notifications || [])) {
                        handleNotification(notif);
                    }
                });
            }
        } catch (e) {}
    },
};

registry.category("services").add("crmLiveToastService", crmLiveToastService);


