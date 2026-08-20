// -------------------------------------------------------------
// DRAWER.JS
// Course detail drawer — open, render similar, toggle learn.
// -------------------------------------------------------------

import { state } from "./state.js";
import { apiRequest, withLang } from "./api.js";
import { showToast, toggleLoading } from "./ui.js";
import {
    detailDrawer, drawerVideo, drawerTitle, drawerMeta,
    drawerDesc, drawerTags, btnToggleLearn, drawerSimilar
} from "./dom.js";
import { escapeHtml, formatDuration } from "./utils.js";

export async function openCourseDetail(item_idx) {
    toggleLoading(true);
    drawerVideo.pause();

    try {
        const course = await apiRequest(withLang(`/courses/${item_idx}`), "GET");
        state.openCourse = course;

        drawerTitle.textContent = course.title;
        drawerMeta.textContent = `${course.language || "fr"} • ${course.type || "Course"} • ${formatDuration(course.duration)}`;
        drawerDesc.textContent = course.description || "No description available.";

        let tagsHtml = "";
        if (course.difficulty) tagsHtml += `<span class="badge badge-indigo">${escapeHtml(course.difficulty)}</span>`;
        if (course.theme) tagsHtml += `<span class="badge badge-blue">${escapeHtml(course.theme)}</span>`;
        if (course.software) tagsHtml += `<span class="badge badge-orange">${escapeHtml(course.software)}</span>`;
        if (course.job) tagsHtml += `<span class="badge badge-green">${escapeHtml(course.job)}</span>`;
        drawerTags.innerHTML = tagsHtml;

        drawerVideo.poster = course.thumbnail_url || "/assets/thumbnail.png";
        drawerVideo.load();

        updateDrawerToggleButton();

        drawerSimilar.innerHTML = `<div class="spinner" style="width: 24px; height: 24px; border-width: 2px; margin: 20px auto;"></div>`;
        detailDrawer.classList.remove("hidden");

        const similarRes = await apiRequest(withLang(`/recommendations/similar/${course.item_idx}`), "POST", { limit: 4 });
        renderSimilarItems(similarRes.items);

    } catch (err) {
        showToast("Error", "Could not load course details: " + err.message, "error");
    } finally {
        toggleLoading(false);
    }
}

export function updateDrawerToggleButton() {
    const isLearned = state.history.some(idx => idx === state.openCourse.item_idx);
    if (isLearned) {
        btnToggleLearn.innerHTML = `<i class="fa-solid fa-xmark"></i> Remove from learned`;
        btnToggleLearn.className = "btn btn-danger-outline btn-block";
    } else {
        btnToggleLearn.innerHTML = `<i class="fa-solid fa-check"></i> Mark as Learned`;
        btnToggleLearn.className = "btn btn-indigo btn-block";
    }
}

function renderSimilarItems(items) {
    if (!items || items.length === 0) {
        drawerSimilar.innerHTML = "<p style='font-size: 0.8rem; color: var(--text-muted);'>No similar courses found.</p>";
        return;
    }

    drawerSimilar.innerHTML = items.map(item => `
    <div class="similar-item-card" onclick="openCourseDetail(${item.item_idx})">
      <div class="similar-item-info">
        <h5 title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h5>
        <p>${escapeHtml(item.type || "Course")} • ${escapeHtml(formatDuration(item.duration))}</p>
      </div>
      <span class="similar-score">${Math.round(item.score * 100)}% Match</span>
    </div>
  `).join("");
}