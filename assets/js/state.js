// -------------------------------------------------------------
// STATE.JS
// Global application state — single source of truth.
// -------------------------------------------------------------

export const state = {
    token: localStorage.getItem("auth_token") || null,
    username: localStorage.getItem("username") || null,
    role: localStorage.getItem("user_role") || null,
    lang: localStorage.getItem("display_lang") === "fr" ? "fr" : "en",
    history: [],
    logs: [],
    currentTab: "dashboard",
    openCourse: null
};