// -------------------------------------------------------------
// NAVIGATION.JS
// Tab switching logic.
// -------------------------------------------------------------

import { state } from "./state.js";
import { navItems, tabPanes, tabTitle } from "./dom.js";
import { loadHistory, renderHistoryTimeline } from "./history.js";
import { loadRecommendations } from "./recommendations.js";
import { loadFacetOptions, runSearch } from "./search.js";
import { loadAdminDashboard } from "./admin.js";
import { toggleLoading, showToast } from "./ui.js";

export function switchTab(tabId) {
    state.currentTab = tabId;

    navItems.forEach(item => {
        item.classList.toggle("active", item.getAttribute("data-tab") === tabId);
    });

    tabPanes.forEach(pane => {
        pane.classList.toggle("hidden", pane.id !== `tab-${tabId}`);
    });

    switch (tabId) {
        case "dashboard":
            tabTitle.innerHTML = "Learning Dashboard";
            refreshDashboard();
            break;
        case "search":
            tabTitle.innerHTML = "Catalog Search";
            loadFacetOptions().then(() => runSearch());
            break;
        case "history":
            tabTitle.innerHTML = "Study Journal";
            renderHistoryTimeline();
            break;
        case "admin":
            tabTitle.innerHTML = "Admin Console";
            loadAdminDashboard();
            break;
    }
}

async function refreshDashboard() {
    toggleLoading(true);
    try {
        await loadHistory();
        await loadRecommendations();
    } catch (err) {
        showToast("Error loading dashboard", err.message, "error");
    } finally {
        toggleLoading(false);
    }
}