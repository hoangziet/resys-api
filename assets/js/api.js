// -------------------------------------------------------------
// API.JS
// API request wrapper, language helper, recommendation cache.
// -------------------------------------------------------------

import { API_PREFIX, RECO_CACHE_TTL_MS } from "./config.js";
import { state } from "./state.js";
import { showToast } from "./ui.js";

// --- Language helper ---
export function withLang(endpoint) {
    return `${endpoint}${endpoint.includes("?") ? "&" : "?"}lang=${state.lang}`;
}

// --- Recommendation Cache ---
function recoCacheKey() {
    return `reco_cache:${state.username || "anon"}:${state.lang}`;
}

export function getRecoCache() {
    try {
        const raw = localStorage.getItem(recoCacheKey());
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

export function setRecoCache(data) {
    try {
        localStorage.setItem(recoCacheKey(), JSON.stringify({ ts: Date.now(), data }));
    } catch { /* storage full */ }
}

export function isRecoCacheValid(cache) {
    return cache && (Date.now() - cache.ts) < RECO_CACHE_TTL_MS;
}

export function clearRecoCache() {
    try {
        localStorage.removeItem(recoCacheKey());
    } catch { /* ignore */ }
}

// --- API Request Wrapper ---
export async function apiRequest(endpoint, method = "GET", body = null) {
    const headers = {};

    if (state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
    }

    const options = { method, headers };

    if (body) {
        if (body instanceof URLSearchParams) {
            headers["Content-Type"] = "application/x-www-form-urlencoded";
            options.body = body.toString();
        } else {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
    }

    try {
        const response = await fetch(`${API_PREFIX}${endpoint}`, options);

        if (response.status === 401) {
            // Import auth dynamically to avoid circular dependency at module level
            const { logout } = await import("./auth.js");
            logout();
            showToast("Session Expired", "Please log in again.", "error");
            throw new Error("Unauthorized");
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const message = errorData.detail?.message || errorData.detail || "API Request failed";
            throw new Error(message);
        }

        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}