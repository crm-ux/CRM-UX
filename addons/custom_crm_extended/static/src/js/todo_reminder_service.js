/** @odoo-module **/

import { registry } from "@web/core/registry";

export const todoReminderService = {
    dependencies: ["bus_service", "notification", "action"],
    start(env, { bus_service, notification, action }) {
        if (!bus_service) {
            return;
        }

        // Listen for real-time reminders dispatched by the Personal To-Do cron
        bus_service.subscribe("crm.personal.todo/reminder", (payload) => {
            if (!payload) return;
            const title = payload.title || "Personal To-Do Reminder";
            const message = payload.message || "You have a task scheduled for now.";
            const todoId = payload.todo_id;

            notification.add(message, {
                title: `🔔 ${title}`,
                type: "warning",
                className: "todo-reminder-toast",
                sticky: true,
                buttons: todoId ? [
                    {
                        name: "Open To-Do ↗",
                        primary: true,
                        onClick: () => {
                            action.doAction({
                                type: "ir.actions.act_window",
                                res_model: "crm.personal.todo",
                                res_id: todoId,
                                views: [[false, "form"]],
                                target: "current",
                            });
                        },
                    },
                ] : [],
            });
        });
    },
};

registry.category("services").add("todoReminderService", todoReminderService);
