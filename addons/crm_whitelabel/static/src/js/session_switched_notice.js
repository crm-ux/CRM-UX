/** @odoo-module **/

import { registry } from "@web/core/registry";

let isNoticeOpen = false;

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

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

// 1. Lock this tab to whichever user opened it
let tabLoadedUid = null;

function initSessionMonitor() {
    tabLoadedUid = getCookie("crm_logged_uid") || (window.odoo && window.odoo.__session_info__ && window.odoo.__session_info__.uid);

    const checkUserChange = () => {
        if (!tabLoadedUid || isNoticeOpen) return;
        const currentCookieUid = getCookie("crm_logged_uid");
        // If cookie changed because another user logged in:
        if (currentCookieUid && String(currentCookieUid) !== String(tabLoadedUid)) {
            showSessionSwitchedDialog();
        }
    };

    // Check immediately on switching back to tab, and every 1.5 seconds
    window.addEventListener("focus", checkUserChange);
    setInterval(checkUserChange, 1500);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSessionMonitor);
} else {
    initSessionMonitor();
}

// 2. Also catch any CSRF / 400 session error
registry.category("error_handlers").add("csrf_session_switched_handler", (env, error) => {
    const err = error || env;
    const errorStr = (err?.message || err?.data?.message || err?.data?.name || "").toLowerCase();

    if (
        errorStr.includes("csrf") ||
        errorStr.includes("session expired") ||
        errorStr.includes("session invalid") ||
        err?.status === 400
    ) {
        showSessionSwitchedDialog();
        return true;
    }
    return false;
}, { sequence: 0 });
