/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

let isNoticeOpen = false;

// Store the original user who opened this tab
const originalUid = odoo.session_info?.uid;
const originalUserName = odoo.session_info?.name || "";

function showSessionSwitchedDialog(userName) {
    if (isNoticeOpen) return;
    isNoticeOpen = true;

    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(15,23,42,0.65);z-index:999999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(3px);";

    const modal = document.createElement("div");
    modal.style.cssText = "background:#ffffff;border-radius:14px;box-shadow:0 20px 25px -5px rgba(0,0,0,0.25);width:90%;max-width:440px;padding:28px 24px;text-align:center;font-family:inherit;";

    const userText = userName ? `as <strong>${userName}</strong>` : 'to your account';

    modal.innerHTML = `
        <div style="font-size:36px;margin-bottom:12px;">👤</div>
        <h3 style="color:#0f172a;font-size:20px;font-weight:700;margin:0 0 10px 0;">Session Switched</h3>
        <p style="color:#475569;font-size:14px;line-height:1.55;margin:0 0 20px 0;">
            Another user logged in on this browser, so your previous session is no longer active.<br/><br/>
            Please sign in again to continue ${userText}.
        </p>
        <a href="/web/login" style="display:inline-block;width:100%;padding:12px 0;background:#1a3d6e;color:#ffffff;border-radius:8px;font-weight:600;font-size:15px;text-decoration:none;">
            Log in Again
        </a>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

// 1. TRIGGER WHEN USER CLICKS BACK TO THIS TAB (Focus Check)
window.addEventListener("focus", async () => {
    if (!originalUid || isNoticeOpen) return;
    try {
        const sessionInfo = await rpc("/web/session/get_session_info");
        // If the user on the server is different from the user who opened this tab:
        if (sessionInfo && sessionInfo.uid && sessionInfo.uid !== originalUid) {
            showSessionSwitchedDialog(originalUserName);
        }
    } catch (e) {
        // If session expired or CSRF error occurred:
        showSessionSwitchedDialog(originalUserName);
    }
});

// 2. TRIGGER ON ANY ERROR (CSRF / Session Expired)
registry.category("error_handlers").add("csrf_session_switched_handler", ({ error }) => {
    const errorStr = (error?.message || error?.data?.message || "").toLowerCase();
    if (errorStr.includes("csrf") || errorStr.includes("session expired") || errorStr.includes("session invalid")) {
        showSessionSwitchedDialog(originalUserName);
        return true;
    }
    return false;
});
