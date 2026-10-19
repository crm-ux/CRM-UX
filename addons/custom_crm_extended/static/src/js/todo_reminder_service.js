/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export const todoReminderService = {
    dependencies: ["bus_service", "notification", "action"],
    start(env, { bus_service, notification, action }) {
        const shownReminders = new Set();

        const showToast = (todoId, title, message) => {
            if (shownReminders.has(todoId)) return;
            shownReminders.add(todoId);

            notification.add(message || "You have a task scheduled for now.", {
                title: title || "Personal To-Do Reminder",
                type: "info",
                className: "todo-reminder-toast",
                sticky: false,
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
        };

        // 1. Instant live check loop directly from the browser (runs every 15 seconds)
        const checkLiveReminders = async () => {
            try {
                const dueTodos = await rpc("/web/dataset/call_kw", {
                    model: "crm.personal.todo",
                    method: "get_live_due_reminders",
                    args: [],
                    kwargs: {},
                });
                if (Array.isArray(dueTodos) && dueTodos.length > 0) {
                    for (const item of dueTodos) {
                        showToast(item.id, item.title, item.message);
                    }
                }
            } catch (e) {
                // Ignore transient errors
            }
        };

        // Run immediate check on load, then every 15 seconds for instant live alerts
        setTimeout(checkLiveReminders, 2000);
        setInterval(checkLiveReminders, 15000);

        // 2. Bus listener for server-push events
        if (bus_service) {
            bus_service.subscribe("crm.personal.todo/reminder", (payload) => {
                if (!payload) return;
                showToast(payload.todo_id, payload.title, payload.message);
            });
        }
    },
};

registry.category("services").add("todoReminderService", todoReminderService);

