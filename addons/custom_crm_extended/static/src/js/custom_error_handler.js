/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

export const CUSTOM_USER_ERROR_MESSAGE = "We apologize for the inconvenience. The system is temporarily unable to process this request.";

const errorHandlerRegistry = registry.category("error_handlers");

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

    // 3. For ANY technical DOM / Owl / JS error (like insertBefore, TypeError, RPC_ERROR, etc.):
    // DO NOT display raw code or technical jargon to user.
    // Show only the clean 1-line apology dialog modal:
    if (env.services?.dialog) {
        env.services.dialog.add(ConfirmationDialog, {
            title: _t("System Notice"),
            body: _t(CUSTOM_USER_ERROR_MESSAGE),
            confirmLabel: _t("OK"),
        });
    } else if (env.services?.notification) {
        env.services.notification.add(_t(CUSTOM_USER_ERROR_MESSAGE), {
            type: "danger",
            sticky: false,
        });
    }

    return true; // Stop default giant traceback modal from displaying to the user
}

// Add with high sequence so it intercepts before Odoo's default dialog error handler
errorHandlerRegistry.add("custom_clean_error_handler", customCleanErrorHandler, { sequence: 1 });

