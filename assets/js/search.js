// -------------------------------------------------------------
// SEARCH.JS
// Course search, facet filters, pagination.
// -------------------------------------------------------------

import { state } from "./state.js";
import { FACET_KEYS, PAGE_SIZE } from "./config.js";
import { apiRequest } from "./api.js";
import { showToast, toggleLoading } from "./ui.js";
import {
    searchInput, searchResultsGrid, searchCount, facetPanel,
    filtersClearBtn, paginationNav
} from "./dom.js";
import { renderSkeletons, escapeHtml } from "./utils.js";
import { renderCourseCards } from "./recommendations.js";

export const courseQuery = {
    page: 1,
    selected: { difficulty: [], theme: [], software: [], job_type: [], type: [] },
    options: {}
};

export function buildCourseQueryString() {
    const params = new URLSearchParams();
    const q = searchInput.value.trim();
    if (q) params.set("q", q);
    for (const key of FACET_KEYS) {
        for (const value of courseQuery.selected[key]) params.append(key, value);
    }
    params.set("page", String(courseQuery.page));
    params.set("limit", String(PAGE_SIZE));
    params.set("lang", state.lang);
    return params.toString();
}

export function countSelectedFilters() {
    return FACET_KEYS.reduce((n, key) => n + courseQuery.selected[key].length, 0);
}

export function renderFacetOptions() {
    for (const key of FACET_KEYS) {
        const container = document.getElementById(`facet-${key}`);
        if (!container) continue;
        const options = courseQuery.options[key] || [];

        if (options.length === 0) {
            container.innerHTML = `<p class="facet-empty">No values</p>`;
            continue;
        }

        container.innerHTML = options.map(opt => {
            const checked = courseQuery.selected[key].includes(opt.value) ? "checked" : "";
            const id = `facet-${key}-${opt.value}`;
            return `
        <label class="facet-option" for="${escapeHtml(id)}">
          <input type="checkbox" id="${escapeHtml(id)}" data-facet="${key}"
            value="${escapeHtml(opt.value)}" ${checked} />
          <span class="facet-label" title="${escapeHtml(opt.label)}">${escapeHtml(opt.label)}</span>
          <span class="facet-count">${opt.count}</span>
        </label>
      `;
        }).join("");
    }

    filtersClearBtn.classList.toggle("hidden", countSelectedFilters() === 0);
}

export async function loadFacetOptions() {
    try {
        const res = await apiRequest(`/courses/filters?lang=${state.lang}`, "GET");
        courseQuery.options = res.filters || {};

        for (const key of FACET_KEYS) {
            const valid = new Set((courseQuery.options[key] || []).map(o => o.value));
            courseQuery.selected[key] = courseQuery.selected[key].filter(v => valid.has(v));
        }
        renderFacetOptions();
    } catch (err) {
        showToast("Could not load filters", err.message, "error");
    }
}

export function renderPagination(pagination) {
    const { page, total_pages: totalPages } = pagination;
    if (!totalPages || totalPages <= 1) {
        paginationNav.innerHTML = "";
        return;
    }

    const windowSize = 5;
    let start = Math.max(1, page - Math.floor(windowSize / 2));
    const end = Math.min(totalPages, start + windowSize - 1);
    start = Math.max(1, end - windowSize + 1);

    let html = `<button class="page-btn" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>
      <i class="fa-solid fa-chevron-left"></i></button>`;
    if (start > 1) {
        html += `<button class="page-btn" data-page="1">1</button>`;
        if (start > 2) html += `<span class="page-ellipsis">…</span>`;
    }
    for (let p = start; p <= end; p++) {
        html += `<button class="page-btn ${p === page ? "page-current" : ""}" data-page="${p}">${p}</button>`;
    }
    if (end < totalPages) {
        if (end < totalPages - 1) html += `<span class="page-ellipsis">…</span>`;
        html += `<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;
    }
    html += `<button class="page-btn" data-page="${page + 1}" ${page >= totalPages ? "disabled" : ""}>
      <i class="fa-solid fa-chevron-right"></i></button>`;

    paginationNav.innerHTML = html;
}

export async function runSearch() {
    searchResultsGrid.innerHTML = renderSkeletons(8);

    try {
        const res = await apiRequest(`/courses/?${buildCourseQueryString()}`, "GET");
        const courses = res.courses || [];
        const pagination = res.pagination || { page: 1, total: 0, total_pages: 0 };

        const total = pagination.total;
        if (total === 0) {
            searchCount.textContent = "Showing 0 courses";
        } else {
            const first = (pagination.page - 1) * pagination.limit + 1;
            const last = first + courses.length - 1;
            searchCount.textContent =
                `Showing ${first}–${last} of ${total} courses` +
                (pagination.total_pages > 1 ? ` (page ${pagination.page} of ${pagination.total_pages})` : "");
        }

        if (courses.length === 0) {
            searchResultsGrid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; width: 100%;">
          <i class="fa-solid fa-face-frown-open"></i>
          <h3>No courses found</h3>
          <p>Try refining your search text or removing filters.</p>
        </div>
      `;
            paginationNav.innerHTML = "";
            return;
        }

        searchResultsGrid.innerHTML = renderCourseCards(courses);
        renderPagination(pagination);
    } catch (err) {
        showToast("Search failed", err.message, "error");
    }
}

export function resetToFirstPageAndSearch() {
    courseQuery.page = 1;
    return runSearch();
}