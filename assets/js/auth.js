// -------------------------------------------------------------
// AUTH.JS
// Login, register, logout, session persistence, auth UI switching.
// -------------------------------------------------------------

import { state } from "./state.js";
import { clearRecoCache } from "./api.js";
import { showToast } from "./ui.js";
import {
    authScreen, dashboardScreen, loginForm, registerForm,
    tabLoginBtn, tabRegisterBtn, authTabs, authTitle, authSubtitle,
    userDisplayName, userRoleBadge
} from "./dom.js";
import { switchTab } from "./navigation.js";

export function checkAuth() {
    if (state.token) {
        authScreen.classList.add("hidden");
        dashboardScreen.classList.remove("hidden");

        userDisplayName.textContent = state.username;
        userRoleBadge.textContent = state.role;
        userRoleBadge.className = `badge ${state.role === "admin" ? "badge-orange" : "badge-indigo"}`;

        const adminItems = document.querySelectorAll(".admin-only");
        adminItems.forEach(item => {
            if (state.role === "admin") {
                item.classList.remove("hidden");
            } else {
                item.classList.add("hidden");
            }
        });

        switchTab("dashboard");
    } else {
        authScreen.classList.remove("hidden");
        dashboardScreen.classList.add("hidden");
    }
}

export function saveSession(token, username, role) {
    clearRecoCache();
    state.token = token;
    state.username = username;
    state.role = role;
    localStorage.setItem("auth_token", token);
    localStorage.setItem("username", username);
    localStorage.setItem("user_role", role);
    checkAuth();
}

export function logout() {
    clearRecoCache();
    state.token = null;
    state.username = null;
    state.role = null;
    localStorage.removeItem("auth_token");
    localStorage.removeItem("username");
    localStorage.removeItem("user_role");
    checkAuth();

    // Pause any playing video
    const { drawerVideo, detailDrawer } = requireDom();
    drawerVideo.pause();
    detailDrawer.classList.add("hidden");
}

// Lazy DOM import to avoid circular dependency with drawer
function requireDom() {
    return {
        drawerVideo: document.getElementById("drawer-video"),
        detailDrawer: document.getElementById("detail-drawer")
    };
}

export function switchAuthMode(mode) {
    const isRegister = mode === "register";

    loginForm.classList.toggle("hidden", isRegister);
    registerForm.classList.toggle("hidden", !isRegister);

    if (tabLoginBtn && tabRegisterBtn) {
        tabLoginBtn.classList.toggle("active", !isRegister);
        tabRegisterBtn.classList.toggle("active", isRegister);
        tabLoginBtn.setAttribute("aria-selected", String(!isRegister));
        tabRegisterBtn.setAttribute("aria-selected", String(isRegister));
    }
    if (authTabs) authTabs.classList.toggle("register-active", isRegister);

    if (authTitle) authTitle.textContent = isRegister ? "Create your account" : "Welcome back";
    if (authSubtitle) {
        authSubtitle.textContent = isRegister
            ? "Join MARS and start building your learning history"
            : "Sign in to continue your learning path";
    }
}

export function updatePasswordStrength(value) {
    const bar = document.getElementById("password-strength")?.querySelector(".strength-bar");
    const label = document.getElementById("password-strength-label");
    if (!bar || !label) return;

    if (!value) {
        bar.className = "strength-bar";
        label.textContent = "\u00a0";
        return;
    }

    let score = 0;
    if (value.length >= 6) score++;
    if (value.length >= 10) score++;
    if (/[0-9]/.test(value) && /[a-zA-Z]/.test(value)) score++;
    if (/[^a-zA-Z0-9]/.test(value)) score++;

    if (score <= 1) {
        bar.className = "strength-bar weak";
        label.textContent = "Weak";
    } else if (score <= 2) {
        bar.className = "strength-bar medium";
        label.textContent = "Okay";
    } else {
        bar.className = "strength-bar strong";
        label.textContent = "Strong";
    }
}