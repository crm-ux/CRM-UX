/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

let isNoticeOpen = false;

// Store the original user who opened this tab
const originalUid = (odoo.session_info && odoo.session_info.uid) || null;
const originalUserName = (odoo.session_info && odoo.session_info.name) || "";

function showSessionSwitchedDialog(userName) {
    if (isNoticeOpen) return;
    isNoticeOpen = true;

    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(15,23,42,0.65);z-index:999999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(3px);font-family:inherit;padding:clamp(1rem, 3vw, 2rem);box-sizing:border-box;";

    const modal = document.createElement("div");
    modal.style.cssText = "background:#ffffff;border-radius:clamp(0.75rem, 1.2vw, 1rem);box-shadow:0 20px 25px -5px rgba(0,0,0,0.25);width:100%;max-width:clamp(20rem, 30vw, 28rem);padding:clamp(1.5rem, 2.5vw, 2rem) clamp(1.25rem, 2vw, 1.75rem);text-align:center;box-sizing:border-box;";

    const userText = userName ? `as <strong>${userName}</strong>` : 'to your account';

    modal.innerHTML = `
        <div style="font-size:clamp(2rem, 3vw, 2.5rem);margin-bottom:clamp(0.5rem, 1vw, 0.75rem);">&#128100;</div>
        <h3 style="color:#0f172a;font-size:clamp(1.125rem, 1.5vw, 1.35rem);font-weight:700;margin:0 0 clamp(0.5rem, 0.8vw, 0.75rem) 0;">Session Switched</h3>
        <p style="color:#475569;font-size:clamp(0.85rem, 1vw, 0.95rem);line-height:1.55;margin:0 0 clamp(1.25rem, 2vw, 1.5rem) 0;">
            Another user logged in on this browser, so your previous session is no longer active.<br/><br/>
            Please sign in again to continue ${userText}.
        </p>
        <a href="/web/login" style="display:inline-block;width:100%;padding:clamp(0.65rem, 1vw, 0.85rem) 0;background:#1a3d6e;color:#ffffff;border-radius:clamp(0.4rem, 0.6vw, 0.55rem);font-weight:600;font-size:clamp(0.9rem, 1.1vw, 1rem);text-decoration:none;box-sizing:border-box;box-shadow:0 4px 6px -1px rgba(26,61,110,0.2);">
            Log in Again
        </a>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

// 1. Check whenever the user switches back to this tab
window.addEventListener("focus", async () => {
    if (!originalUid || isNoticeOpen) return;
    try {
        const sessionInfo = await rpc("/web/session/get_session_info");
        if (sessionInfo && sessionInfo.uid && sessionInfo.uid !== originalUid) {
            showSessionSwitchedDialog(originalUserName);
        }
    } catch (e) {
        showSessionSwitchedDialog(originalUserName);
    }
});

// 2. Intercept any CSRF or Session Expired RPC error
registry.category("error_handlers").add("csrf_session_switched_handler", (env, error) => {
    const err = error || env;
    const errorStr = (err?.message || err?.data?.message || err?.data?.name || "").toLowerCase();

    if (
        errorStr.includes("csrf") ||
        errorStr.includes("session expired") ||
        errorStr.includes("session invalid") ||
        err?.status === 400
    ) {
        showSessionSwitchedDialog(originalUserName);
        return true; // Prevents Odoo from showing the red crash dialog
    }
    return false;
}, { sequence: 0 });
