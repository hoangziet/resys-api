// -------------------------------------------------------------
// EVENTS.JS
// All event listener setup — wires UI to business logic.
// -------------------------------------------------------------

import { state } from "./state.js";
import { FACET_KEYS } from "./config.js";
import { apiRequest, withLang, clearRecoCache } from "./api.js";
import { toggleLoading, setButtonBusy, showToast } from "./ui.js";
import { switchTab } from "./navigation.js";
import { switchAuthMode, updatePasswordStrength } from "./auth.js";
import { toggleTheme } from "./theme.js";
import { loadHistory, renderHistoryTimeline } from "./history.js";
import { loadRecommendations } from "./recommendations.js";
import {
    courseQuery, countSelectedFilters, renderFacetOptions,
    loadFacetOptions, resetToFirstPageAndSearch
} from "./search.js";
import { updateDrawerToggleButton } from "./drawer.js";
import {
    loadAdminDashboard, loadAdminLogs, loadLatencyStats,
    loadPipelineStatus, loadAdminCourses, openCourseModal,
    closeCourseModal, submitCourseForm, deleteCourse, adminCourses
} from "./admin.js";
import {
    navItems, goToRegister, goToLogin, tabLoginBtn, tabRegisterBtn,
    themeToggleSidebar, themeToggleAuth, logoutBtn, btnCloseDrawer,
    drawerVideo, detailDrawer, searchInput, searchClearBtn,
    facetPanel, filtersClearBtn, paginationNav, filterLanguage,
    btnToggleLearn, clearHistoryBtn, btnSyncCatalog, btnRebuildEmb,
    btnRefreshLogs, latencyWindowSelect, latencyTable, btnLatencyTable,
    btnAddCourse, btnCancelCourse, btnCloseCourseModal, courseModal,
    courseForm, adminCoursesTbody, adminCoursesPagination, adminCourseSearch
} from "./dom.js";

export function setupEventListeners() {
    // --- Navigation tabs ---
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            switchTab(item.getAttribute("data-tab"));
        });
    });

    // --- Auth mode switch (links in forms) ---
    goToRegister.addEventListener("click", (e) => { e.preventDefault(); switchAuthMode("register"); });
    goToLogin.addEventListener("click", (e) => { e.preventDefault(); switchAuthMode("login"); });

    // --- Auth mode switch (segmented tabs) ---
    if (tabLoginBtn) tabLoginBtn.addEventListener("click", () => switchAuthMode("login"));
    if (tabRegisterBtn) tabRegisterBtn.addEventListener("click", () => switchAuthMode("register"));

    // --- Theme toggles ---
    if (themeToggleSidebar) themeToggleSidebar.addEventListener("click", toggleTheme);
    if (themeToggleAuth) themeToggleAuth.addEventListener("click", toggleTheme);

    // --- Password visibility toggles ---
    document.querySelectorAll(".btn-toggle-password").forEach(btn => {
        btn.addEventListener("click", () => {
            const input = document.getElementById(btn.getAttribute("data-target"));
            if (!input) return;
            const icon = btn.querySelector("i");
            const isHidden = input.type === "password";
            input.type = isHidden ? "text" : "password";
            if (icon) icon.className = isHidden ? "fa-regular fa-eye-slash" : "fa-regular fa-eye";
            btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
        });
    });

    // --- Password strength hint ---
    const registerPasswordInput = document.getElementById("register-password");
    if (registerPasswordInput) {
        registerPasswordInput.addEventListener("input", () => {
            updatePasswordStrength(registerPasswordInput.value);
        });
    }

    // --- Escape to clear search ---
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && document.activeElement === searchInput && searchInput.value) {
            searchInput.value = "";
            searchClearBtn.classList.add("hidden");
            resetToFirstPageAndSearch();
        }
    });

    // --- Login form ---
    document.getElementById("login-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        toggleLoading(true);
        const submitBtn = e.target.querySelector('button[type="submit"]');
        setButtonBusy(submitBtn, true, "Signing in...");
        const username = document.getElementById("login-username").value.trim();
        const password = document.getElementById("login-password").value;

        const params = new URLSearchParams();
        params.append("username", username);
        params.append("password", password);

        try {
            const data = await apiRequest("/auth/token", "POST", params);
            const payloadBase64 = data.access_token.split(".")[1];
            const padded = payloadBase64.replace(/-/g, "+").replace(/_/g, "/");
            const payload = JSON.parse(atob(padded));

            const { saveSession } = await import("./auth.js");
            saveSession(data.access_token, payload.sub, payload.role || "learner");
            showToast("Success", `Welcome back, ${payload.sub}!`, "success");
        } catch (err) {
            showToast("Login Failed", err.message, "error");
        } finally {
            toggleLoading(false);
            setButtonBusy(submitBtn, false);
        }
    });

    // --- Register form ---
    document.getElementById("register-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        toggleLoading(true);
        const submitBtn = e.target.querySelector('button[type="submit"]');
        setButtonBusy(submitBtn, true, "Creating account...");
        const username = document.getElementById("register-username").value.trim();
        const password = document.getElementById("register-password").value;

        try {
            await apiRequest("/auth/register", "POST", { username, password });
            showToast("Success", "Account created! Logging in...", "success");

            const params = new URLSearchParams();
            params.append("username", username);
            params.append("password", password);
            const data = await apiRequest("/auth/token", "POST", params);

            const payloadBase64 = data.access_token.split(".")[1];
            const padded = payloadBase64.replace(/-/g, "+").replace(/_/g, "/");
            const payload = JSON.parse(atob(padded));

            const { saveSession } = await import("./auth.js");
            saveSession(data.access_token, payload.sub, payload.role || "learner");
        } catch (err) {
            showToast("Registration Failed", err.message, "error");
        } finally {
            toggleLoading(false);
            setButtonBusy(submitBtn, false);
        }
    });

    // --- Logout ---
    logoutBtn.addEventListener("click", () => {
        const { logout } = requireAuth();
        logout();
    });

    function requireAuth() {
        // Dynamic import to avoid circular dependency at module level
        return { logout: window.__logout };
    }

    // --- Close drawer ---
    btnCloseDrawer.addEventListener("click", () => {
        drawerVideo.pause();
        detailDrawer.classList.add("hidden");
        if (state.currentTab === "history") renderHistoryTimeline();
    });

    // --- Search with debounce ---
    let searchTimeout;
    searchInput.addEventListener("input", () => {
        searchClearBtn.classList.toggle("hidden", !searchInput.value.trim());
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => resetToFirstPageAndSearch(), 300);
    });

    searchClearBtn.addEventListener("click", () => {
        searchInput.value = "";
        searchClearBtn.classList.add("hidden");
        resetToFirstPageAndSearch();
    });

    // --- Facet checkboxes (delegated) ---
    facetPanel.addEventListener("change", event => {
        const input = event.target;
        if (!input.matches('input[type="checkbox"][data-facet]')) return;

        const key = input.dataset.facet;
        const selected = courseQuery.selected[key];
        if (!selected) return;

        const at = selected.indexOf(input.value);
        if (input.checked && at === -1) selected.push(input.value);
        else if (!input.checked && at !== -1) selected.splice(at, 1);

        filtersClearBtn.classList.toggle("hidden", countSelectedFilters() === 0);
        resetToFirstPageAndSearch();
    });

    filtersClearBtn.addEventListener("click", () => {
        for (const key of FACET_KEYS) courseQuery.selected[key] = [];
        renderFacetOptions();
        resetToFirstPageAndSearch();
    });

    // --- Pagination (delegated) ---
    paginationNav.addEventListener("click", event => {
        const btn = event.target.closest("button[data-page]");
        if (!btn || btn.disabled) return;
        const page = Number(btn.dataset.page);
        if (!Number.isFinite(page) || page < 1 || page === courseQuery.page) return;
        courseQuery.page = page;
        const { runSearch } = requireSearch();
        runSearch();
        document.getElementById("search-results-grid").scrollIntoView({ behavior: "smooth", block: "start" });
    });

    function requireSearch() {
        return { runSearch: window.__runSearch };
    }

    // --- Language switch ---
    filterLanguage.value = state.lang;
    filterLanguage.addEventListener("change", async () => {
        state.lang = filterLanguage.value === "fr" ? "fr" : "en";
        localStorage.setItem("display_lang", state.lang);
        clearRecoCache();
        await loadFacetOptions();
        await resetToFirstPageAndSearch();
        await loadRecommendations();
        await renderHistoryTimeline();
    });

    // --- Toggle learn button in drawer ---
    btnToggleLearn.addEventListener("click", async () => {
        if (!state.openCourse) return;
        const isLearned = state.history.some(idx => idx === state.openCourse.item_idx);
        toggleLoading(true);

        try {
            if (isLearned) {
                await apiRequest(`/history/${state.openCourse.item_idx}`, "DELETE");
                showToast("Removed", "Course removed from history.", "info");
            } else {
                await apiRequest(`/history/?item_idx=${state.openCourse.item_idx}`, "POST");
                showToast("Learned", "Course marked as learned!", "success");
            }

            await loadHistory();
            updateDrawerToggleButton();
            await loadRecommendations();
        } catch (err) {
            showToast("Error", err.message, "error");
        } finally {
            toggleLoading(false);
        }
    });

    // --- Clear history ---
    clearHistoryBtn.addEventListener("click", async () => {
        if (state.history.length === 0) return;
        if (!confirm("Are you sure you want to clear your learning history? This will reset all personalization rails.")) return;

        toggleLoading(true);
        try {
            await apiRequest("/history/", "DELETE");
            showToast("Success", "Learning history cleared", "info");
            await loadHistory();
            await loadRecommendations();
        } catch (err) {
            showToast("Error", err.message, "error");
        } finally {
            toggleLoading(false);
        }
        renderHistoryTimeline();
    });

    // --- Admin actions ---
    btnSyncCatalog.addEventListener("click", async () => {
        toggleLoading(true);
        try {
            const res = await apiRequest("/admin/sync-catalog", "POST");
            showToast("Sync Successful", `Catalog now holds ${res.courses} courses (${res.facet_rows} facet rows rebuilt).`, "success");
            await loadAdminDashboard();
        } catch (err) {
            showToast("Error", err.message, "error");
        } finally {
            toggleLoading(false);
        }
    });

    btnRebuildEmb.addEventListener("click", async () => {
        toggleLoading(true);
        try {
            const res = await apiRequest("/admin/rebuild-embeddings", "POST");
            if (!res.pending_courses) {
                showToast("Nothing to do", "Every course already has an embedding.", "info");
            } else {
                showToast("Embeddings generated", `${res.embedded} course(s) embedded. ${res.restart_required ? "Restart the API to load them." : ""}`, "success");
            }
            await loadPipelineStatus();
        } catch (err) {
            showToast("Embedding job not run", err.message, "error");
        } finally {
            toggleLoading(false);
        }
    });

    btnRefreshLogs.addEventListener("click", async () => {
        toggleLoading(true);
        try {
            await Promise.all([loadAdminLogs(), loadLatencyStats()]);
            showToast("Refreshed", "Latest recommendation logs fetched.", "info");
        } catch (err) {
            showToast("Error", err.message, "error");
        } finally {
            toggleLoading(false);
        }
    });

    // --- Latency window + table toggle ---
    if (latencyWindowSelect) {
        latencyWindowSelect.addEventListener("change", async () => {
            try { await loadLatencyStats(); } catch (err) { showToast("Error", err.message, "error"); }
        });
    }

    if (btnLatencyTable) {
        btnLatencyTable.addEventListener("click", () => {
            const shown = latencyTable.classList.toggle("hidden");
            btnLatencyTable.setAttribute("aria-expanded", String(!shown));
        });
    }

    // --- Course management ---
    if (btnAddCourse) btnAddCourse.addEventListener("click", () => openCourseModal(null));
    if (btnCancelCourse) btnCancelCourse.addEventListener("click", closeCourseModal);
    if (btnCloseCourseModal) btnCloseCourseModal.addEventListener("click", closeCourseModal);
    if (courseModal) courseModal.addEventListener("click", event => { if (event.target === courseModal) closeCourseModal(); });
    if (courseForm) courseForm.addEventListener("submit", submitCourseForm);

    if (adminCoursesTbody) {
        adminCoursesTbody.addEventListener("click", async event => {
            const editBtn = event.target.closest("button[data-edit]");
            if (editBtn) {
                try {
                    const course = await apiRequest(withLang(`/courses/${editBtn.dataset.edit}`), "GET");
                    openCourseModal({ ...course, item_idx: Number(editBtn.dataset.edit) });
                } catch (err) { showToast("Could not open course", err.message, "error"); }
                return;
            }
            const delBtn = event.target.closest("button[data-delete]");
            if (delBtn) await deleteCourse(delBtn.dataset.delete);
        });
    }

    if (adminCoursesPagination) {
        adminCoursesPagination.addEventListener("click", event => {
            const btn = event.target.closest("button[data-admin-page]");
            if (!btn || btn.disabled) return;
            adminCourses.page = Number(btn.dataset.adminPage);
            loadAdminCourses();
        });
    }

    if (adminCourseSearch) {
        let adminSearchTimer;
        adminCourseSearch.addEventListener("input", () => {
            clearTimeout(adminSearchTimer);
            adminSearchTimer = setTimeout(() => {
                adminCourses.q = adminCourseSearch.value.trim();
                adminCourses.page = 1;
                loadAdminCourses();
            }, 300);
        });
    }
}