// -------------------------------------------------------------
// UTILS.JS
// Pure utility functions — no DOM, no side effects.
// -------------------------------------------------------------

import { CATEGORY_VISUALS, DEFAULT_CATEGORY_VISUAL } from "./config.js";

export function escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}

export function formatDuration(sec) {
    if (!sec) return "\u2014";
    const mins = Math.round(sec / 60);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    return remMins > 0 ? `${hrs}h ${remMins}m` : `${hrs}h`;
}

export function renderSkeletons(count) {
    let html = "";
    for (let i = 0; i < count; i++) {
        html += `
      <div class="shimmer-card">
        <div class="shimmer-line shimmer-img"></div>
        <div class="shimmer-line shimmer-title"></div>
        <div class="shimmer-line shimmer-text"></div>
        <div class="shimmer-line shimmer-footer"></div>
      </div>
    `;
    }
    return html;
}

export function getCategoryVisual(theme) {
    if (!theme) return DEFAULT_CATEGORY_VISUAL;
    const found = CATEGORY_VISUALS.find(v => v.match.test(theme));
    return found || DEFAULT_CATEGORY_VISUAL;
}

export function bucketLabel(bucket) {
    // Server buckets are "YYYY-MM-DDTHH:00" in UTC.
    const date = new Date(`${bucket}:00Z`);
    if (Number.isNaN(date.getTime())) return bucket;
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatMs(value) {
    // Always milliseconds: callers render the "ms" unit themselves, so this must
    // not switch to seconds or the unit label would contradict the number.
    if (value === null || value === undefined) return "—";
    return value >= 100 ? String(Math.round(value)) : value.toFixed(1);
}