/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { FileInput } from "@web/core/file_input/file_input";
import { patch } from "@web/core/utils/patch";

export const CUSTOM_USER_ERROR_MESSAGE = "We apologize for the inconvenience. The system is temporarily unable to process this request.";

// Client-side file size validation & graceful 413 handling
patch(FileInput.prototype, {
    async onFileInputChange(ev) {
        const files = Array.from(ev.target?.files || []);
        const MAX_SIZE = 25 * 1024 * 1024; // 25 MB default limit
        const oversized = files.filter((f) => f.size > MAX_SIZE);
        if (oversized.length > 0) {
            ev.target.value = "";
            const names = oversized.map((f) => f.name).join(", ");
            this.env.services.notification?.add(
                _t(`The file(s) "${names}" exceed the maximum allowed upload size of 25 MB. Please select a smaller file.`),
                {
                    title: _t("File Too Large"),
                    type: "warning",
                    sticky: false,
                }
            );
            return;
        }

        try {
            return await super.onFileInputChange(...arguments);
        } catch (err) {
            const errStr = ((err?.message || "") + " " + JSON.stringify(err || "")).toLowerCase();
            if (errStr.includes("large") || errStr.includes("413")) {
                this.env.services.notification?.add(
                    _t("The selected file is too large to upload. Please select a smaller file (under 25 MB)."),
                    {
                        title: _t("File Too Large"),
                        type: "warning",
                        sticky: false,
                    }
                );
                return;
            }
            throw err;
        }
    },
});

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
            // Ignore intentional aborted requests (debounced searches, user navigation, form unmounts)
            if (err?.name === "AbortError") {
                throw err;
            }
            // Network failure / connection refused while server is dead or restarting
            if (!window._isServerReconnecting) {
                window._isServerReconnecting = true;
                window.location.replace(window.location.href);
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

    const fullErrStr = JSON.stringify(err || {}) + " " + (err?.message || "") + " " + (err?.data?.message || "") + " " + (err?.name || "") + " " + (err?.stack || "");
    const fullErrLower = fullErrStr.toLowerCase();

    // 0. If it's an AccessError caused by lead assignment / transfer, completely silent-suppress
    if (
        err?.data?.name === "odoo.exceptions.AccessError" ||
        fullErrLower.includes("accesserror") ||
        fullErrLower.includes("top-secret records") ||
        fullErrLower.includes("doesn't have 'read' access")
    ) {
        return true;
    }

    // 1. Always log complete technical details, traceback, and error object to developer console
    console.error("[Odoo Technical Error - Logged for Developers]:", err);
    if (err?.data?.message) {
        console.error(">>> EXACT ERROR MESSAGE:", err.data.message);
    }
    if (err?.data?.debug) {
        console.error(">>> EXACT PYTHON TRACEBACK:\n" + err.data.debug);
    }

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

    // 2.3 AccessError handling when a record is assigned/transferred to another user
    const isAccessError =
        err?.data?.name === "odoo.exceptions.AccessError" ||
        fullErrLower.includes("accesserror") ||
        fullErrLower.includes("top-secret records") ||
        fullErrLower.includes("doesn't have 'read' access");

    if (isAccessError) {
        // Suppress technical traceback and error dialog completely
        return true;
    }

    // 2.5 If server is offline, restarting, or upgrading (Connection Lost / 502 Bad Gateway / NetworkError):
    // DO NOT show apology dialog! Navigate directly so NGINX serves the maintenance page

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
        fullErrLower.includes("server connection") ||
        fullErrLower.includes("couldn't be established") ||
        fullErrLower.includes("was interrupted") ||
        fullErrLower.includes("connectionlosterror") ||
        fullErrLower.includes("invalid controller to restore");

    if (isConnectionLost) {
        window._isServerReconnecting = true;
        window.location.replace(window.location.href);
        return true;
    }

    // 2.8 Content Too Large / 413 File Upload Error:
    // Show a clean friendly warning notification instead of technical error dialog
    const isContentTooLarge =
        fullErrLower.includes("content too large") ||
        fullErrLower.includes("entity too large") ||
        fullErrLower.includes("413") ||
        err?.status === 413 ||
        err?.code === 413;

    if (isContentTooLarge) {
        if (env.services?.notification) {
            env.services.notification.add(
                _t("The selected file is too large to upload. Please select a smaller file (under 25 MB)."),
                {
                    title: _t("File Too Large"),
                    type: "warning",
                    sticky: false,
                }
            );
        }
        return true;
    }

    // 3. For technical application / RPC errors:
    // Log the full technical error & traceback ONLY to console, and show the clean 1-line apology message in UI
    const userFacingMsg = _t(CUSTOM_USER_ERROR_MESSAGE);
    if (env.services?.dialog) {
        env.services.dialog.add(ConfirmationDialog, {
            title: _t("System Notice"),
            body: userFacingMsg,
            confirmLabel: _t("OK"),
        });
    } else if (env.services?.notification) {
        env.services.notification.add(userFacingMsg, {
            type: "warning",
            sticky: false,
        });
    }
    return true;
}

// Add with high sequence so it intercepts before Odoo's default dialog error handler
errorHandlerRegistry.add("custom_clean_error_handler", customCleanErrorHandler, { sequence: 1 });

