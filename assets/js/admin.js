// -------------------------------------------------------------
// ADMIN.JS
// Admin dashboard, logs, monitoring, course management.
// -------------------------------------------------------------

import { state } from "./state.js";
import { apiRequest, withLang } from "./api.js";
import { showToast, toggleLoading } from "./ui.js";
import {
    adminModelStatus, adminModelMaxLen, adminModelVocab, adminModelDim,
    btnSyncCatalog, btnRebuildEmb, btnRefreshLogs, logsTbody,
    latencyWindowSelect, latencyTable, btnLatencyTable,
    adminCoursesTbody, adminCoursesPagination, adminCourseSearch,
    btnAddCourse, courseModal, courseModalTitle, courseForm,
    courseItemIdx, btnSaveCourse, btnCancelCourse, btnCloseCourseModal
} from "./dom.js";
import { escapeHtml } from "./utils.js";
import { FACET_KEYS } from "./config.js";

// --- Admin course pagination state ---
export const adminCourses = {
    page: 1,
    q: "",
    limit: 10
};

// --- Strategy badge helper ---
function getStrategyBadge(strategy) {
    if (!strategy) return "badge-light-blue";
    if (strategy.includes("popular")) return "badge-green";
    if (strategy.includes("bert4rec")) return "badge-orange";
    if (strategy.includes("similar")) return "badge-blue";
    if (strategy.includes("content")) return "badge-indigo";
    return "badge-light-blue";
}

export async function loadAdminDashboard() {
    toggleLoading(true);
    try {
        const health = await apiRequest("/admin/model-health", "GET");

        if (health.status === "healthy") {
            adminModelStatus.textContent = "Healthy & Active";
            adminModelStatus.className = "badge badge-green";
            adminModelMaxLen.textContent = `${health.max_len} steps`;
            adminModelVocab.textContent = `${health.vocab_size} classes`;
            adminModelDim.textContent = `${health.hidden_dim} dim`;
        } else if (health.status === "degraded") {
            adminModelStatus.textContent = "Degraded (error)";
            adminModelStatus.className = "badge badge-rose";
            console.warn("Model degradation reason:", health.error);
        } else {
            adminModelStatus.textContent = "Unavailable";
            adminModelStatus.className = "badge badge-rose";
        }

        await Promise.all([
            loadAdminLogs(),
            loadLatencyStats(),
            loadPipelineStatus(),
            loadAdminCourses()
        ]);
    } catch (err) {
        showToast("Admin access error", err.message, "error");
    } finally {
        toggleLoading(false);
    }
}

export async function loadAdminLogs() {
    const res = await apiRequest("/admin/recommendation-logs", "GET");
    state.logs = res.logs;

    if (!state.logs || state.logs.length === 0) {
        logsTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No logs recorded. Query recommendations to trigger audits.</td></tr>`;
        return;
    }

    logsTbody.innerHTML = state.logs.map(log => {
        const date = new Date(log.timestamp + "Z").toLocaleTimeString();
        const status = log.status_code ? ` · ${log.status_code}` : "";
        return `
      <tr>
        <td title="${escapeHtml(log.timestamp)}">${escapeHtml(date)}</td>
        <td><code>${escapeHtml(log.username || "anonymous")}</code></td>
        <td><span class="badge ${getStrategyBadge(log.strategy)}">${escapeHtml(log.strategy)}</span>${escapeHtml(status)}</td>
        <td><strong>${Math.round(log.latency_ms)} ms</strong></td>
        <td title="${escapeHtml(log.history)}"><code>${escapeHtml(log.history || "empty")}</code></td>
        <td title="${escapeHtml(log.results)}"><code>${escapeHtml(log.results || "empty")}</code></td>
      </tr>
    `;
    }).join("");
}

// --- TODO: Paste the remaining functions from your cut-off code here ---
// These functions were in the [...] portion of your paste:

export async function loadLatencyStats() {
    // TODO: Paste your original loadLatencyStats implementation
    console.warn("loadLatencyStats — paste original implementation");
}

export async function loadPipelineStatus() {
    // TODO: Paste your original loadPipelineStatus implementation
    console.warn("loadPipelineStatus — paste original implementation");
}

export async function loadAdminCourses() {
    // TODO: Paste your original loadAdminCourses implementation
    console.warn("loadAdminCourses — paste original implementation");
}

export function openCourseModal(course) {
    // TODO: Paste your original openCourseModal implementation
    console.warn("openCourseModal — paste original implementation");
}

export function closeCourseModal() {
    // TODO: Paste your original closeCourseModal implementation
    console.warn("closeCourseModal — paste original implementation");
}

export async function submitCourseForm(e) {
    // TODO: Paste your original submitCourseForm implementation
    console.warn("submitCourseForm — paste original implementation");
}

export async function deleteCourse(itemIdx) {
    // TODO: Paste your original deleteCourse implementation
    console.warn("deleteCourse — paste original implementation");
}