// -------------------------------------------------------------
// HISTORY.JS
// Learning history — load, render timeline, delete items.
// -------------------------------------------------------------

import { state } from "./state.js";
import { apiRequest, withLang } from "./api.js";
import { showToast, toggleLoading } from "./ui.js";
import {
    historyTimeline, historyEmptyState, clearHistoryBtn, statHistoryCount
} from "./dom.js";
import { escapeHtml, formatDuration } from "./utils.js";
import { loadRecommendations } from "./recommendations.js";

export async function loadHistory() {
    const data = await apiRequest(withLang("/history/"), "GET");
    state.history = data.history.map(item => item.item_idx);
    statHistoryCount.textContent = state.history.length;
}

export async function renderHistoryTimeline() {
    toggleLoading(true);
    try {
        const data = await apiRequest(withLang("/history/"), "GET");
        const history = data.history;
        statHistoryCount.textContent = history.length;

        if (!history || history.length === 0) {
            historyEmptyState.classList.remove("hidden");
            historyTimeline.innerHTML = "";
            clearHistoryBtn.classList.add("hidden");
            return;
        }

        historyEmptyState.classList.add("hidden");
        clearHistoryBtn.classList.remove("hidden");

        historyTimeline.innerHTML = history.map((item, index) => `
      <div class="timeline-item">
        <div class="timeline-node"></div>
        <div class="timeline-content-wrapper">
          <div class="timeline-idx-circle">${index + 1}</div>
          <div class="timeline-info" onclick="openCourseDetail(${item.item_idx})">
            <h4>${escapeHtml(item.title)}</h4>
            <p>${escapeHtml(item.type || "Course")} • ${escapeHtml(item.language || "fr")} • ${escapeHtml(formatDuration(item.duration))}</p>
          </div>
        </div>
        <button class="btn-remove-timeline" onclick="deleteHistoryItem(${item.item_idx})" title="Remove from sequence">
          <i class="fa-solid fa-trash"></i>
        </button>
      </div>
    `).join("");

    } catch (err) {
        showToast("Error", "Could not fetch learning history: " + err.message, "error");
    } finally {
        toggleLoading(false);
    }
}

export async function deleteHistoryItem(item_idx) {
    event.stopPropagation();
    toggleLoading(true);
    try {
        await apiRequest(`/history/${item_idx}`, "DELETE");
        showToast("Removed", "Course removed from history.", "info");
        await loadHistory();
        if (state.currentTab === "history") {
            await renderHistoryTimeline();
        } else {
            await loadRecommendations();
        }
    } catch (err) {
        showToast("Error", err.message, "error");
    } finally {
        toggleLoading(false);
    }
}