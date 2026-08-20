// -------------------------------------------------------------
// RECOMMENDATIONS.JS
// Load & render recommendation rails, cache management.
// -------------------------------------------------------------

import { state } from "./state.js";
import { apiRequest, withLang, getRecoCache, setRecoCache, isRecoCacheValid, clearRecoCache } from "./api.js";
import { showToast, toggleLoading } from "./ui.js";
import { railForYou, railYouMayLike, railPopular } from "./dom.js";
import { renderSkeletons, escapeHtml, formatDuration, getCategoryVisual } from "./utils.js";

export { clearRecoCache };

export async function loadRecommendations() {
    railForYou.innerHTML = renderSkeletons(4);
    railYouMayLike.innerHTML = renderSkeletons(4);
    railPopular.innerHTML = renderSkeletons(4);

    const cached = getRecoCache();
    let forYouRes, youMayRes, popularRes;
    let hitRateLimit = false;

    try {
        forYouRes = await apiRequest(withLang("/recommendations/for-you"), "POST", { limit: 10 });
    } catch (err) {
        if (err.message?.includes("429") || err.message?.includes("Rate limit")) hitRateLimit = true;
    }

    try {
        youMayRes = await apiRequest(withLang("/recommendations/you-may-also-like"), "POST", { limit: 10 });
    } catch (err) {
        if (err.message?.includes("429") || err.message?.includes("Rate limit")) hitRateLimit = true;
    }

    try {
        popularRes = await apiRequest(withLang("/recommendations/popular"), "POST", { limit: 10 });
    } catch (err) {
        if (err.message?.includes("429") || err.message?.includes("Rate limit")) hitRateLimit = true;
    }

    if (forYouRes || youMayRes || popularRes) {
        setRecoCache({ forYou: forYouRes, youMay: youMayRes, popular: popularRes });
    }

    if (forYouRes) {
        railForYou.innerHTML = renderCourseCards(forYouRes.items, forYouRes.source);
    } else if (isRecoCacheValid(cached) && cached?.data?.forYou) {
        railForYou.innerHTML = renderCourseCards(cached.data.forYou.items, cached.data.forYou.source);
    }

    if (youMayRes) {
        railYouMayLike.innerHTML = renderCourseCards(youMayRes.items, youMayRes.source);
    } else if (isRecoCacheValid(cached) && cached?.data?.youMay) {
        railYouMayLike.innerHTML = renderCourseCards(cached.data.youMay.items, cached.data.youMay.source);
    }

    if (popularRes) {
        railPopular.innerHTML = renderCourseCards(popularRes.items, popularRes.source);
    } else if (isRecoCacheValid(cached) && cached?.data?.popular) {
        railPopular.innerHTML = renderCourseCards(cached.data.popular.items, cached.data.popular.source);
    }

    if (hitRateLimit) {
        const msg = isRecoCacheValid(cached)
            ? "Rate limit reached — showing cached recommendations."
            : "Rate limit reached — please try again in a moment.";
        showToast("Slow down", msg, "info");
    }
}

export function renderCourseCards(items, source) {
    if (!items || items.length === 0) {
        return `<div class="empty-rail-msg">No recommendations available. Update your history to trigger predictions.</div>`;
    }

    return items.map(item => {
        const formattedDuration = formatDuration(item.duration);
        const isBert = source === "bert4rec_personalized" || source === "bert4rec";
        const scoreText = (item.score !== undefined && !isBert) ? `${Math.round(item.score * 100)}% Match` : "";
        const categoryName = item.theme || "Tech";
        const visual = getCategoryVisual(categoryName);

        return `
      <div class="card" onclick="openCourseDetail(${item.item_idx})">
        <div class="card-img-wrapper">
          <div class="card-cat-cover ${visual.cover}"><i class="${visual.icon}"></i></div>
          <div class="card-cat-chip" title="${escapeHtml(categoryName)}">
            <i class="${visual.icon}"></i><span>${escapeHtml(categoryName)}</span>
          </div>
          <img src="${escapeHtml(item.thumbnail_url)}" alt="${escapeHtml(item.title)}" loading="lazy"
            onerror="this.classList.add('img-error')" />
          ${scoreText ? `<div class="card-score-badge">${escapeHtml(scoreText)}</div>` : ""}
        </div>
        <div class="card-body">
          <div class="card-meta-row">
            <span class="badge ${item.language === "fr" ? "badge-blue" : "badge-indigo"}">${escapeHtml(item.language || "fr")}</span>
            <span class="badge badge-light-blue">${escapeHtml(item.type || "Course")}</span>
          </div>
          <h4 class="card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h4>
          <p class="card-desc">${escapeHtml(item.description)}</p>
        </div>
        <div class="card-footer">
          <div class="card-footer-tags">
            <span class="badge badge-light-blue">${escapeHtml(categoryName)}</span>
          </div>
          <div class="card-duration">
            <i class="fa-regular fa-clock"></i> ${escapeHtml(formattedDuration)}
          </div>
        </div>
      </div>
    `;
    }).join("");
}