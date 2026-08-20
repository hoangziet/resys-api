// -------------------------------------------------------------
// ADMIN.JS
// Admin dashboard, logs, monitoring, course management.
// -------------------------------------------------------------

import { state } from "./state.js";
import { apiRequest, withLang } from "./api.js";
import { showToast, toggleLoading, attachLatencyHover } from "./ui.js";
import {
    adminModelStatus, adminModelMaxLen, adminModelVocab, adminModelDim,
    btnSyncCatalog, btnRebuildEmb, btnRefreshLogs, logsTbody,
    latencyWindowSelect, latencyTable, btnLatencyTable, pipelineBanner,
    adminCoursesTbody, adminCoursesPagination, adminCourseSearch,
    btnAddCourse, courseModal, courseModalTitle, courseForm, latencyTiles, latencyLegend, latencyChart,
    courseItemIdx, btnSaveCourse, btnCancelCourse, btnCloseCourseModal
} from "./dom.js";
import { escapeHtml, bucketLabel } from "./utils.js";
import { FACET_KEYS, LATENCY_SERIES } from "./config.js";

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

export async function loadLatencyStats() {
    const hours = latencyWindowSelect ? latencyWindowSelect.value : "24";
    const res = await apiRequest(`/admin/latency-stats?hours=${encodeURIComponent(hours)}`, "GET");
    state.latency = res;
    renderLatencyTiles(res.overall);
    renderLatencyChart(res.timeseries || []);
    renderLatencyTable(res.timeseries || []);
}

function renderLatencyTiles(overall) {
    if (!latencyTiles) return;
    const o = overall || {};

    // Median and P50 are the same percentile; they are adjacent and marked as a
    // pair so the duplication reads as intentional rather than as a bug.
    const tiles = [
        { label: "Requests", value: o.count ?? 0, unit: "" },
        { label: "Average", value: formatMs(o.avg), unit: "ms" },
        { label: "Median", value: formatMs(o.median), unit: "ms", paired: true },
        { label: "P50", value: formatMs(o.p50), unit: "ms", paired: true },
        { label: "P95", value: formatMs(o.p95), unit: "ms" },
        { label: "P99", value: formatMs(o.p99), unit: "ms" }
    ];

    latencyTiles.innerHTML = tiles.map(t => `
    <div class="stat-tile ${t.paired ? "stat-tile-paired" : ""}">
      <span class="stat-tile-label">${escapeHtml(t.label)}</span>
      <span class="stat-tile-value">${escapeHtml(String(t.value))}${t.unit ? `<span class="stat-tile-unit">${escapeHtml(t.unit)}</span>` : ""
        }</span>
    </div>
  `).join("");

    if (latencyLegend) {
        latencyLegend.innerHTML = LATENCY_SERIES.map(s => `
      <span class="legend-item">
        <span class="legend-swatch" style="background:${s.color}"></span>${escapeHtml(s.label)}
      </span>
    `).join("");
    }
}

function renderLatencyChart(series) {
    if (!latencyChart) return;

    if (!series.length) {
        latencyChart.innerHTML = `<p class="chart-placeholder">No requests recorded in this window yet.</p>`;
        return;
    }

    const W = 720;
    const H = 240;
    const pad = { top: 16, right: 18, bottom: 30, left: 46 };
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    const values = series.flatMap(p => [p.avg, p.p95]).filter(v => typeof v === "number");
    const maxVal = Math.max(...values, 1);
    // Round the top of the scale up so ticks land on readable numbers.
    const step = Math.pow(10, Math.floor(Math.log10(maxVal))) / 2 || 1;
    const yMax = Math.ceil(maxVal / step) * step;

    const xAt = i => pad.left + (series.length === 1 ? plotW / 2 : (i / (series.length - 1)) * plotW);
    const yAt = v => pad.top + plotH - (v / yMax) * plotH;

    const ticks = 4;
    let gridSvg = "";
    for (let t = 0; t <= ticks; t++) {
        const value = (yMax / ticks) * t;
        const y = yAt(value);
        gridSvg += `<line class="viz-gridline" x1="${pad.left}" y1="${y}" x2="${W - pad.right}" y2="${y}" />`;
        gridSvg += `<text class="viz-tick" x="${pad.left - 8}" y="${y + 3}" text-anchor="end">${Math.round(value)}</text>`;
    }

    // Label first / middle / last only, so ticks never collide.
    const labelIdx = new Set([0, Math.floor((series.length - 1) / 2), series.length - 1]);
    let xLabels = "";
    labelIdx.forEach(i => {
        const anchor = i === 0 ? "start" : i === series.length - 1 ? "end" : "middle";
        xLabels += `<text class="viz-tick" x="${xAt(i)}" y="${H - 10}" text-anchor="${anchor}">${escapeHtml(bucketLabel(series[i].bucket))}</text>`;
    });

    const lines = LATENCY_SERIES.map(s => {
        const points = series.map((p, i) => `${xAt(i).toFixed(1)},${yAt(p[s.key] || 0).toFixed(1)}`).join(" ");
        return `<polyline class="viz-line" points="${points}" stroke="${s.color}" />`;
    }).join("");

    latencyChart.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" role="img"
      aria-label="Latency over time: average and P95 in milliseconds">
      ${gridSvg}
      <line class="viz-axisline" x1="${pad.left}" y1="${pad.top + plotH}" x2="${W - pad.right}" y2="${pad.top + plotH}" />
      ${xLabels}
      ${lines}
      <g id="latency-hover" style="display:none">
        <line class="viz-crosshair" y1="${pad.top}" y2="${pad.top + plotH}" />
        ${LATENCY_SERIES.map(s => `<circle r="5" fill="${s.color}" class="viz-marker" />`).join("")}
      </g>
      <rect x="${pad.left}" y="${pad.top}" width="${plotW}" height="${plotH}"
        fill="transparent" id="latency-hitarea" />
    </svg>
    <div class="viz-tooltip hidden" id="latency-tooltip"></div>
  `;

    attachLatencyHover(series, xAt, yAt);
}

function renderLatencyTable(series) {
    if (!latencyTable) return;
    if (!series.length) {
        latencyTable.innerHTML = `<p class="chart-placeholder">No data in this window.</p>`;
        return;
    }
    latencyTable.innerHTML = `
    <table class="viz-table">
      <thead>
        <tr><th>Time (UTC hour)</th><th>Requests</th><th>Average (ms)</th><th>P95 (ms)</th></tr>
      </thead>
      <tbody>
        ${series.map(p => `
          <tr>
            <td>${escapeHtml(p.bucket)}</td>
            <td>${p.count}</td>
            <td>${formatMs(p.avg)}</td>
            <td>${formatMs(p.p95)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function formatMs(value) {
    // Always milliseconds: callers render the "ms" unit themselves, so this must
    // not switch to seconds or the unit label would contradict the number.
    if (value === null || value === undefined) return "—";
    return value >= 100 ? String(Math.round(value)) : value.toFixed(1);
}

export async function loadPipelineStatus() {
    if (!pipelineBanner) return;
    try {
        const status = await apiRequest("/admin/pipeline-status", "GET");
        state.pipeline = status;

        const sim = status.text_similarity || {};
        const b4r = status.bert4rec || {};
        const chips = [
            { label: "Catalog", value: `${status.catalog?.courses ?? 0} courses`, action: false },
            {
                label: "Text similarity",
                value: sim.pending_courses
                    ? `${sim.pending_courses} awaiting embedding`
                    : `${sim.embedding_rows ?? 0} vectors`,
                action: Boolean(sim.action_required)
            },
            {
                label: "BERT4Rec",
                value: b4r.courses_outside_vocabulary
                    ? `${b4r.courses_outside_vocabulary} outside vocab (retrain)`
                    : `n_items ${b4r.n_items ?? 0}`,
                action: Boolean(b4r.action_required)
            },
            { label: "Trending", value: "live from history", action: false }
        ];

        pipelineBanner.innerHTML = chips.map(c => `
      <span class="pipeline-chip ${c.action ? "needs-action" : ""}"
        ${c.action ? 'title="Action required before new courses appear here"' : ""}>
        ${c.action ? '<i class="fa-solid fa-triangle-exclamation"></i>' : '<i class="fa-solid fa-circle-check"></i>'}
        ${escapeHtml(c.label)}: <strong>${escapeHtml(c.value)}</strong>
      </span>
    `).join("");
    } catch (err) {
        pipelineBanner.innerHTML = "";
        console.warn("pipeline-status unavailable:", err.message);
    }
}

export async function loadAdminCourses() {
    if (!adminCoursesTbody) return;
    const params = new URLSearchParams({
        page: String(adminCourses.page),
        limit: String(adminCourses.limit),
        lang: state.lang
    });
    if (adminCourses.q) params.set("q", adminCourses.q);

    try {
        const res = await apiRequest(`/admin/courses?${params.toString()}`, "GET");
        const courses = res.courses || [];

        if (!courses.length) {
            adminCoursesTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No courses found.</td></tr>`;
            adminCoursesPagination.innerHTML = "";
            return;
        }

        adminCoursesTbody.innerHTML = courses.map(c => {
            const pending = c.embedding_status !== "ready";
            const badges = [
                pending
                    ? '<span class="badge badge-orange" title="Not in text-similarity results until the embedding job runs">embedding pending</span>'
                    : '<span class="badge badge-green">similarity ready</span>',
                c.in_model_vocabulary
                    ? '<span class="badge badge-indigo">in BERT4Rec</span>'
                    : '<span class="badge badge-light-blue" title="Requires model retraining">awaiting retrain</span>'
            ].join(" ");

            return `
        <tr>
          <td><code>${c.item_idx}</code></td>
          <td title="${escapeHtml(c.title)}">${escapeHtml(c.title)}</td>
          <td>${escapeHtml(c.difficulty || "—")}</td>
          <td>${badges}</td>
          <td class="col-actions">
            <div class="row-actions">
              <button class="btn-row" data-edit="${c.item_idx}"><i class="fa-solid fa-pen"></i> Edit</button>
              <button class="btn-row btn-row-danger" data-delete="${c.item_idx}"><i class="fa-regular fa-trash-can"></i> Delete</button>
            </div>
          </td>
        </tr>
      `;
        }).join("");

        renderAdminPagination(res.pagination);
    } catch (err) {
        showToast("Could not load courses", err.message, "error");
    }
}

function renderAdminPagination(pagination) {
    if (!adminCoursesPagination) return;

    const { page, total_pages: totalPages } = pagination || {};

    if (!totalPages || totalPages <= 1) {
        adminCoursesPagination.innerHTML = "";
        return;
    }

    let html = `
        <button class="page-btn"
                data-admin-page="${page - 1}"
                ${page <= 1 ? "disabled" : ""}>
            <i class="fa-solid fa-chevron-left"></i>
        </button>
    `;

    const pages = [];

    pages.push(1);

    const start = Math.max(2, page - 2);
    const end = Math.min(totalPages - 1, page + 2);

    if (start > 2) {
        pages.push("...");
    }

    for (let p = start; p <= end; p++) {
        pages.push(p);
    }

    if (end < totalPages - 1) {
        pages.push("...");
    }

    if (totalPages > 1) {
        pages.push(totalPages);
    }

    for (const p of pages) {
        if (p === "...") {
            html += `<span class="pagination-ellipsis">...</span>`;
        } else {
            html += `
                <button class="page-btn ${p === page ? "page-current" : ""}"
                        data-admin-page="${p}">
                    ${p}
                </button>
            `;
        }
    }

    html += `
        <button class="page-btn"
                data-admin-page="${page + 1}"
                ${page >= totalPages ? "disabled" : ""}>
            <i class="fa-solid fa-chevron-right"></i>
        </button>
    `;

    adminCoursesPagination.innerHTML = html;
}

function courseFormPayload() {
    return {
        title: document.getElementById("course-title")?.value.trim() || "",
        description: document.getElementById("course-description")?.value.trim() || "",
        theme: document.getElementById("course-theme")?.value.trim() || "",
        software: document.getElementById("course-software")?.value.trim() || "",
        job: document.getElementById("course-job")?.value.trim() || "",
        type: document.getElementById("course-type")?.value.trim() || "",
        difficulty: document.getElementById("course-difficulty")?.value || "",
        duration: document.getElementById("course-duration")?.value
            ? Number(document.getElementById("course-duration").value)
            : null,
        language: document.getElementById("course-language")?.value || "fr",
        thumbnail_url: document.getElementById("course-thumbnail-url")?.value.trim() || ""
    };
}

async function populateCourseDatalists() {
    try {
        const res = await apiRequest(`/courses/filters?lang=${state.lang}`, "GET");
        const f = res.filters || {};

        const setList = (id, key) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.innerHTML = (f[key] || []).map(o => `<option value="${escapeHtml(o.value)}">`).join("");
        };

        setList("dl-theme", "theme");
        setList("dl-software", "software");
        setList("dl-job", "job_type");
        setList("dl-type", "type");
    } catch {
        // silently fail — datalists are convenience, not critical
    }
}

export function openCourseModal(course = null) {
    courseForm.reset();
    courseItemIdx.value = course ? course.item_idx : "";
    courseModalTitle.textContent = course ? `Edit Course #${course.item_idx}` : "Add Course";
    btnSaveCourse.textContent = course ? "Save Changes" : "Create Course";

    if (course) {
        document.getElementById("course-title").value = course.title || "";
        document.getElementById("course-description").value = course.description || "";
        document.getElementById("course-theme").value = course.theme || "";
        document.getElementById("course-software").value = course.software || "";
        document.getElementById("course-job").value = course.job || "";
        document.getElementById("course-type").value = course.type || "";
        document.getElementById("course-duration").value = course.duration ?? "";
        // Stored difficulty is "<level> - <Label>"; map back to the slug.
        const level = String(course.difficulty || "").trim().charAt(0);
        document.getElementById("course-difficulty").value =
            ({ "1": "beginner", "2": "intermediate", "3": "advanced" })[level] || "";
    }

    populateCourseDatalists();
    courseModal.classList.remove("hidden");
}


export function closeCourseModal() {
    courseModal.classList.add("hidden");
}

export async function submitCourseForm(event) {
    event.preventDefault();
    const itemIdx = courseItemIdx.value;
    const payload = courseFormPayload();

    if (!payload.title) {
        showToast("Title required", "A course needs a title.", "error");
        return;
    }

    toggleLoading(true);
    try {
        if (itemIdx) {
            await apiRequest(`/admin/courses/${itemIdx}`, "PUT", payload);
            showToast("Course updated", `Course #${itemIdx} saved.`, "success");
        } else {
            const res = await apiRequest("/admin/courses", "POST", payload);
            const avail = res.recommendation_availability || {};
            showToast(
                "Course created",
                avail.text_similarity
                    ? `Course #${res.item_idx} created.`
                    : `Course #${res.item_idx} created — searchable now, but needs the embedding job before it appears in similarity results.`,
                "success"
            );
        }
        closeCourseModal();
        await Promise.all([loadAdminCourses(), loadPipelineStatus()]);
    } catch (err) {
        showToast("Save failed", err.message, "error");
    } finally {
        toggleLoading(false);
    }
}

export async function deleteCourse(itemIdx) {
    if (!window.confirm(`Delete course #${itemIdx}? This cannot be undone.`)) return;

    toggleLoading(true);
    try {
        await apiRequest(`/admin/courses/${itemIdx}`, "DELETE");
        showToast("Course deleted", `Course #${itemIdx} removed.`, "success");
    } catch (err) {
        // The API refuses by default when the course is inside the model vocabulary,
        // because the checkpoint keeps predicting it until retrained.
        const forced = window.confirm(
            `${err.message}\n\nDelete anyway?`
        );
        if (!forced) {
            toggleLoading(false);
            return;
        }
        try {
            await apiRequest(`/admin/courses/${itemIdx}?force=true`, "DELETE");
            showToast("Course deleted", `Course #${itemIdx} force-deleted.`, "info");
        } catch (forceErr) {
            showToast("Delete failed", forceErr.message, "error");
            toggleLoading(false);
            return;
        }
    }

    await Promise.all([loadAdminCourses(), loadPipelineStatus()]);
    toggleLoading(false);
}