// -------------------------------------------------------------
// THEME.JS
// Light / Dark theme toggle.
// -------------------------------------------------------------

import { themeToggleSidebar, themeToggleAuth } from "./dom.js";

export function initTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    updateThemeToggleUI(current);
}

export function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    const next = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try {
        localStorage.setItem("theme", next);
    } catch { /* storage unavailable */ }
    updateThemeToggleUI(next);
}

function updateThemeToggleUI(theme) {
    if (themeToggleSidebar) {
        const label = themeToggleSidebar.querySelector("span");
        if (label) label.textContent = theme === "light" ? "Dark mode" : "Light mode";
    }
    if (themeToggleAuth) {
        const icon = themeToggleAuth.querySelector("i");
        if (icon) icon.className = theme === "light" ? "fa-solid fa-moon" : "fa-solid fa-sun";
    }
}