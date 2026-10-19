/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

let customToastContainer = null;

function getToastContainer() {
    if (!customToastContainer || !document.body.contains(customToastContainer)) {
        customToastContainer = document.createElement("div");
        customToastContainer.className = "todo-custom-toast-container";
        document.body.appendChild(customToastContainer);
    }
    return customToastContainer;
}

function createSmoothToast(todoId, title, message, actionService) {
    const container = getToastContainer();

    const toast = document.createElement("div");
    toast.className = "todo-smooth-toast";

    const header = document.createElement("div");
    header.className = "todo-toast-header";

    const titleEl = document.createElement("span");
    titleEl.className = "todo-toast-title";
    titleEl.textContent = title || "Personal To-Do Reminder";

    const closeBtn = document.createElement("button");
    closeBtn.className = "todo-toast-close";
    closeBtn.innerHTML = "&times;";
    closeBtn.setAttribute("aria-label", "Close");

    header.appendChild(titleEl);
    header.appendChild(closeBtn);

    const body = document.createElement("div");
    body.className = "todo-toast-body";
    body.textContent = message || "You have a task scheduled for now.";

    const footer = document.createElement("div");
    footer.className = "todo-toast-footer";

    const openBtn = document.createElement("button");
    openBtn.className = "todo-toast-open-btn";
    openBtn.textContent = "Open To-Do ↗";

    footer.appendChild(openBtn);

    toast.appendChild(header);
    toast.appendChild(body);
    toast.appendChild(footer);

    container.appendChild(toast);

    let dismissed = false;
    const dismissToast = () => {
        if (dismissed) return;
        dismissed = true;
        toast.classList.add("todo-toast-fade-out");
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 1200); // 1.2s smooth slow fade out
    };

    closeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        dismissToast();
    });

    openBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        dismissToast();
        if (todoId && actionService) {
            actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "crm.personal.todo",
                res_id: todoId,
                views: [[false, "form"]],
                target: "current",
            });
        }
    });

    // Auto fade out slowly after 7 seconds
    setTimeout(dismissToast, 7000);
}

export const todoReminderService = {
    dependencies: ["bus_service", "action"],
    start(env, { bus_service, action }) {
        const shownReminders = new Set();

        const triggerReminder = (todoId, title, message) => {
            if (shownReminders.has(todoId)) return;
            shownReminders.add(todoId);
            createSmoothToast(todoId, title, message, action);
        };

        const checkLiveReminders = async () => {
            try {
                const dueTodos = await rpc("/web/dataset/call_kw", {
                    model: "crm.personal.todo",
                    method: "get_live_due_reminders",
                    args: [],
                    kwargs: {
                        client_now: new Date().toISOString(),
                    },
                });
                if (Array.isArray(dueTodos) && dueTodos.length > 0) {
                    for (const item of dueTodos) {
                        triggerReminder(item.id, item.title, item.message);
                    }
                }
            } catch (e) {
                // Ignore transient errors
            }
        };

        setTimeout(checkLiveReminders, 1500);
        setInterval(checkLiveReminders, 10000);

        if (bus_service) {
            bus_service.subscribe("crm.personal.todo/reminder", (payload) => {
                if (!payload) return;
                triggerReminder(payload.todo_id, payload.title, payload.message);
            });
        }
    },
};

registry.category("services").add("todoReminderService", todoReminderService);
