/** @odoo-module **/

import { registry } from "@web/core/registry";

let isNoticeOpen = false;

function showSessionSwitchedDialog(userName) {
    if (isNoticeOpen) return;
    isNoticeOpen = true;

    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(15,23,42,0.65);z-index:999999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(3px);";

    const modal = document.createElement("div");
    modal.style.cssText = "background:#ffffff;border-radius:14px;box-shadow:0 20px 25px -5px rgba(0,0,0,0.25);width:90%;max-width:440px;padding:28px 24px;text-align:center;font-family:inherit;";

    modal.innerHTML = `
        <div style="font-size:36px;margin-bottom:12px;">👤</div>
        <h3 style="color:#0f172a;font-size:20px;font-weight:700;margin:0 0 10px 0;">Session Switched</h3>
        <p style="color:#475569;font-size:14px;line-height:1.55;margin:0 0 20px 0;">
            Another user logged in on this browser, so your previous session is no longer active.<br/><br/>
            Please sign in again to continue ${userName ? `as <strong>${userName}</strong>` : ''}.
        </p>
        <a href="/web/login?switch=1" style="display:inline-block;width:100%;padding:12px 0;background:#1a3d6e;color:#ffffff;border-radius:8px;font-weight:600;font-size:15px;text-decoration:none;">
            Log in Again
        </a>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

// Catch CSRF or Session Expired error and show our clean dialog
registry.category("error_handlers").add("csrf_session_switched_handler", ({ error }) => {
    const errorStr = (error?.message || error?.data?.message || "").toLowerCase();
    if (errorStr.includes("csrf") || errorStr.includes("session expired") || errorStr.includes("session invalid")) {
        const userName = odoo.session_info?.name || "";
        showSessionSwitchedDialog(userName);
        return true; // Stops the ugly red error from showing
    }
    return false;
});
