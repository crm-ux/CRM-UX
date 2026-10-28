/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

export const CUSTOM_USER_ERROR_MESSAGE = "We apologize for the inconvenience. The system is temporarily unable to process this request.";

const errorHandlerRegistry = registry.category("error_handlers");

// GLOBAL NETWORK INTERCEPTOR FOR SERVER RESTARTS / 502 BAD GATEWAY
// Whenever any user clicks anything while the server is restarting/upgrading:
// Intercept the 502/network failure instantly and auto-reload to maintenance screen.
if (typeof window !== "undefined" && !window._crmNetworkWatcherInstalled) {
    window._crmNetworkWatcherInstalled = true;
    const originalFetch = window.fetch;
    window.fetch = async function (...args) {
        try {
            const response = await originalFetch.apply(this, args);
            if (response.status === 502 || response.status === 503 || response.status === 504) {
                // Server is updating! Auto-reload immediately so NGINX shows maintenance page
                window.location.reload();
            }
            return response;
        } catch (err) {
            // Network failure / connection refused while server is dead
            if (!window._isServerReconnecting) {
                window._isServerReconnecting = true;
                window.location.reload();
            }
            throw err;
        }
    };
}

/**
 * Universal error handler that catches uncaught technical exceptions / RPC errors,
 * logs the full technical error & traceback to browser developer console,
 * and shows the user a clean centered modal wizard dialog with the 1-line apology message.
 */
export function customCleanErrorHandler(env, error, originalError) {
    const err = originalError || error;

    // 1. Always log complete technical details, traceback, and error object to developer console
    console.error("[Odoo Technical Error - Logged for Developers]:", err);

    // 2. If it's a known user-intended validation error (e.g. ValidationError / missing fields), allow standard display
    const isUserValidationError =
        err?.name === "RPC_ERROR" &&
        (err?.data?.name === "odoo.exceptions.UserError" ||
         err?.data?.name === "odoo.exceptions.ValidationError");

    if (isUserValidationError && err?.data?.message) {
        if (env.services?.dialog) {
            env.services.dialog.add(ConfirmationDialog, {
                title: _t("Notice"),
                body: err.data.message,
                confirmLabel: _t("OK"),
            });
        } else if (env.services?.notification) {
            env.services.notification.add(err.data.message, {
                type: "warning",
                sticky: false,
            });
        }
        return true;
    }

    // If we are already in the process of reconnecting/reloading, suppress ALL subsequent error dialogs
    if (window._isServerReconnecting) {
        return true;
    }

    // 2.5 If server is offline, restarting, or upgrading (Connection Lost / 502 Bad Gateway / NetworkError):
    // DO NOT show apology dialog! Navigate directly so NGINX serves the maintenance page
    const fullErrStr = JSON.stringify(err || {}) + " " + (err?.message || "") + " " + (err?.data?.message || "") + " " + (err?.name || "") + " " + (err?.stack || "");
    const fullErrLower = fullErrStr.toLowerCase();

    const isConnectionLost = 
        err?.status === 0 || 
        err?.status === 502 || 
        err?.status === 503 || 
        err?.status === 504 || 
        err?.code === 502 ||
        err?.code === 503 ||
        err?.code === 504 ||
        err?.code === 100 ||
        err?.response?.status === 502 ||
        err?.response?.status === 503 ||
        err?.response?.status === 504 ||
        err?.name === "ConnectionLost" || 
        fullErrLower.includes("502") ||
        fullErrLower.includes("bad gateway") ||
        fullErrLower.includes("failed to fetch") || 
        fullErrLower.includes("networkerror") ||
        fullErrLower.includes("connection lost") ||
        fullErrLower.includes("connection refused") ||
        fullErrLower.includes("server connection");

    if (isConnectionLost) {
        window._isServerReconnecting = true;
        window.location.replace(window.location.href);
        return true;
    }

    // If it's any RPC_ERROR or server error, NEVER show the apology dialog!
    // Auto-reload immediately so NGINX shows the maintenance page if server is upgrading/restarting
    if (err?.name === "RPC_ERROR" || !isUserValidationError) {
        if (!window._isServerReconnecting) {
            window._isServerReconnecting = true;
            window.location.reload();
        }
        return true;
    }

    return true;
}

// Add with high sequence so it intercepts before Odoo's default dialog error handler
errorHandlerRegistry.add("custom_clean_error_handler", customCleanErrorHandler, { sequence: 1 });

