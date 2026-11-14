/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export const crmLiveToastService = {
    dependencies: ["bus_service", "notification", "action"],
    start(env, { bus_service, notification, action }) {
        if (!bus_service) return;

        // 1. Subscribe to standard Odoo notification toast channel
        try {
            bus_service.subscribe("simple_notification", (payload) => {
                if (!payload) return;
                notification.add(payload.message || "", {
                    title: payload.title || _t("Notification"),
                    type: payload.type || "info",
                    sticky: payload.sticky || false,
                });
                // Auto reload active controller if applicable
                const current = action.currentController;
                if (current && current.model && typeof current.model.load === "function") {
                    current.model.load().catch(() => {});
                }
            });
        } catch (e) {}

        // 2. Subscribe to custom CRM notification channel
        try {
            bus_service.subscribe("crm_notification", (payload) => {
                if (!payload) return;
                notification.add(payload.message || "", {
                    title: payload.title || _t("CRM Notice"),
                    type: payload.type || "warning",
                    sticky: false,
                });
                // Real-time live reload: automatically refresh list/kanban view without manual F5
                const current = action.currentController;
                if (current && current.model && typeof current.model.load === "function") {
                    current.model.load().catch(() => {});
                } else if (current && current.model && current.model.root && typeof current.model.root.load === "function") {
                    current.model.root.load().catch(() => {});
                }
            });
        } catch (e) {}
    },
};

registry.category("services").add("crmLiveToastService", crmLiveToastService);

