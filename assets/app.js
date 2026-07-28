/* -------------------------------------------------------------
 * APP.JS
 * State Management, API integration, client-side caching,
 * animations, and interactive event handlers.
 * ------------------------------------------------------------- */

// API Base Endpoints
const API_PREFIX = "/api/v1";

// Global App State
const state = {
  token: localStorage.getItem("auth_token") || null,
  username: localStorage.getItem("username") || null,
  role: localStorage.getItem("user_role") || null,
  history: [],
  logs: [],
  currentTab: "dashboard",
  openCourse: null
};

// --- DOM Selector Constants ---
const authScreen = document.getElementById("auth-screen");
const dashboardScreen = document.getElementById("dashboard-screen");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const goToRegister = document.getElementById("go-to-register");
const goToLogin = document.getElementById("go-to-login");
const logoutBtn = document.getElementById("btn-logout");
const tabPanes = document.querySelectorAll(".tab-pane");
const navItems = document.querySelectorAll(".nav-item");
const tabTitle = document.getElementById("tab-title");
const toastContainer = document.getElementById("toast-container");
const loadingOverlay = document.getElementById("loading-overlay");

// User details DOM
const userDisplayName = document.getElementById("user-display-name");
const userRoleBadge = document.getElementById("user-role-badge");

// Rails DOM
const railForYou = document.getElementById("rail-for-you");
const railYouMayLike = document.getElementById("rail-you-may-also-like");
const railPopular = document.getElementById("rail-popular");

// Search DOM
const searchInput = document.getElementById("search-input");
const searchClearBtn = document.getElementById("search-clear");
const searchResultsGrid = document.getElementById("search-results-grid");
const searchCount = document.getElementById("search-count");
const filterDifficulty = document.getElementById("filter-difficulty");
const filterLanguage = document.getElementById("filter-language");
const filterType = document.getElementById("filter-type");

// History DOM
const historyTimeline = document.getElementById("history-timeline-container");
const historyEmptyState = document.getElementById("history-empty");
const clearHistoryBtn = document.getElementById("btn-clear-history");
const statHistoryCount = document.getElementById("stat-history-count");

// Admin DOM
const adminModelStatus = document.getElementById("admin-model-status");
const adminModelMaxLen = document.getElementById("admin-model-maxlen");
const adminModelVocab = document.getElementById("admin-model-vocab");
const adminModelDim = document.getElementById("admin-model-dim");
const btnSyncCatalog = document.getElementById("btn-sync-catalog");
const btnRebuildEmb = document.getElementById("btn-rebuild-emb");
const btnRefreshLogs = document.getElementById("btn-refresh-logs");
const logsTbody = document.getElementById("logs-tbody");
const latencyBars = document.getElementById("latency-bars");

// Drawer DOM
const detailDrawer = document.getElementById("detail-drawer");
const btnCloseDrawer = document.getElementById("btn-close-drawer");
const drawerVideo = document.getElementById("drawer-video");
const drawerTitle = document.getElementById("drawer-title");
const drawerMeta = document.getElementById("drawer-meta-info");
const drawerDesc = document.getElementById("drawer-description");
const drawerTags = document.getElementById("drawer-tags-container");
const btnToggleLearn = document.getElementById("btn-toggle-learn");
const drawerSimilar = document.getElementById("drawer-similar-courses");

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  checkAuth();
});

// --- Toast Helper ---
function showToast(title, message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  let icon = "fa-circle-check";
  if (type === "error") icon = "fa-circle-xmark";
  if (type === "info") icon = "fa-circle-info";

  toast.innerHTML = `
    <i class="fa-solid ${icon} toast-icon"></i>
    <div class="toast-content">
      <div class="toast-title"></div>
      <div class="toast-message"></div>
    </div>
  `;
  toast.querySelector(".toast-title").textContent = title;
  toast.querySelector(".toast-message").textContent = message;

  toastContainer.appendChild(toast);

  // Auto remove toast
  setTimeout(() => {
    toast.style.transform = "translateY(-20px)";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// --- Loading Helper ---
function toggleLoading(show) {
  if (show) {
    loadingOverlay.classList.remove("hidden");
  } else {
    loadingOverlay.classList.add("hidden");
  }
}

// --- API Request Wrapper ---
async function apiRequest(endpoint, method = "GET", body = null) {
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
      // Auto logout on token expired
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

// --- Authentication Handler ---
function checkAuth() {
  if (state.token) {
    authScreen.classList.add("hidden");
    dashboardScreen.classList.remove("hidden");

    userDisplayName.textContent = state.username;
    userRoleBadge.textContent = state.role;
    userRoleBadge.className = `badge ${state.role === "admin" ? "badge-orange" : "badge-indigo"}`;

    // Show admin options if role is admin
    const adminItems = document.querySelectorAll(".admin-only");
    adminItems.forEach(item => {
      if (state.role === "admin") {
        item.classList.remove("hidden");
      } else {
        item.classList.add("hidden");
      }
    });

    // Reset view to dashboard tab
    switchTab("dashboard");
    refreshDashboard();
  } else {
    authScreen.classList.remove("hidden");
    dashboardScreen.classList.add("hidden");
  }
}

function saveSession(token, username, role) {
  state.token = token;
  state.username = username;
  state.role = role;
  localStorage.setItem("auth_token", token);
  localStorage.setItem("username", username);
  localStorage.setItem("user_role", role);
  checkAuth();
}

function logout() {
  state.token = null;
  state.username = null;
  state.role = null;
  localStorage.removeItem("auth_token");
  localStorage.removeItem("username");
  localStorage.removeItem("user_role");
  checkAuth();

  // Pause any playing video
  drawerVideo.pause();
  detailDrawer.classList.add("hidden");
}

// --- Setup Event Listeners ---
function setupEventListeners() {
  // Navigation Tabs Switch
  navItems.forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const tab = item.getAttribute("data-tab");
      switchTab(tab);
    });
  });

  // Switch between Login and Register
  goToRegister.addEventListener("click", (e) => {
    e.preventDefault();
    loginForm.classList.add("hidden");
    registerForm.classList.remove("hidden");
    document.querySelector(".auth-header h1").textContent = "Create Account";
  });

  goToLogin.addEventListener("click", (e) => {
    e.preventDefault();
    registerForm.classList.add("hidden");
    loginForm.classList.remove("hidden");
    document.querySelector(".auth-header h1").textContent = "Welcome back";
  });

  // Forms Submissions
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    toggleLoading(true);
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;

    const params = new URLSearchParams();
    params.append("username", username);
    params.append("password", password);

    try {
      const data = await apiRequest("/auth/token", "POST", params);

      // Decode JWT token payload to grab role (base64url-safe decode)
      const payloadBase64 = data.access_token.split(".")[1];
      const padded = payloadBase64.replace(/-/g, "+").replace(/_/g, "/");
      const payload = JSON.parse(atob(padded));

      saveSession(data.access_token, payload.sub, payload.role || "learner");
      showToast("Success", `Welcome back, ${payload.sub}!`, "success");
    } catch (err) {
      showToast("Login Failed", err.message, "error");
    } finally {
      toggleLoading(false);
    }
  });

  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    toggleLoading(true);
    const username = document.getElementById("register-username").value.trim();
    const password = document.getElementById("register-password").value;

    try {
      await apiRequest("/auth/register", "POST", { username, password });
      showToast("Success", "Account created! Logging in...", "success");

      // Auto Login
      const params = new URLSearchParams();
      params.append("username", username);
      params.append("password", password);
      const data = await apiRequest("/auth/token", "POST", params);

      const payloadBase64 = data.access_token.split(".")[1];
      const padded = payloadBase64.replace(/-/g, "+").replace(/_/g, "/");
      const payload = JSON.parse(atob(padded));
      saveSession(data.access_token, payload.sub, payload.role || "learner");
    } catch (err) {
      showToast("Registration Failed", err.message, "error");
    } finally {
      toggleLoading(false);
    }
  });

  // Logout button
  logoutBtn.addEventListener("click", logout);

  // Close Drawer
  btnCloseDrawer.addEventListener("click", () => {
    drawerVideo.pause();
    detailDrawer.classList.add("hidden");
  });

  // Search input with Debounce
  let searchTimeout;
  searchInput.addEventListener("input", () => {
    const val = searchInput.value.trim();
    if (val) {
      searchClearBtn.classList.remove("hidden");
    } else {
      searchClearBtn.classList.add("hidden");
    }

    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      runSearch();
    }, 300);
  });

  // Clear Search
  searchClearBtn.addEventListener("click", () => {
    searchInput.value = "";
    searchClearBtn.classList.add("hidden");
    runSearch();
  });

  // Filters select
  [filterDifficulty, filterLanguage, filterType].forEach(el => {
    el.addEventListener("change", runSearch);
  });

  // Toggle Learn button in drawer
  btnToggleLearn.addEventListener("click", async () => {
    if (!state.openCourse) return;
    const isLearned = state.history.some(idx => idx === state.openCourse.item_idx);
    toggleLoading(true);

    try {
      if (isLearned) {
        // Remove from history
        await apiRequest(`/history/${state.openCourse.item_idx}`, "DELETE");
        showToast("Removed", "Course removed from history.", "info");
      } else {
        // Add to history
        await apiRequest(`/history/?item_idx=${state.openCourse.item_idx}`, "POST");
        showToast("Learned", "Course marked as learned!", "success");
      }

      // Refresh history state
      await loadHistory();

      // Update toggle button UI
      updateDrawerToggleButton();

      // Refresh home recommendations
      await loadRecommendations();
    } catch (err) {
      showToast("Error", err.message, "error");
    } finally {
      toggleLoading(false);
    }
  });

  // Clear History
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
  });

  // Admin Actions
  btnSyncCatalog.addEventListener("click", async () => {
    toggleLoading(true);
    try {
      const res = await apiRequest("/admin/sync-catalog", "POST");
      showToast("Sync Successful", `Database catalog updated with ${res.synced_items} items!`, "success");
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
      await apiRequest("/admin/rebuild-embeddings", "POST");
      showToast("Success", "Course embeddings successfully rebuilt!", "success");
    } catch (err) {
      showToast("Error", err.message, "error");
    } finally {
      toggleLoading(false);
    }
  });

  btnRefreshLogs.addEventListener("click", async () => {
    toggleLoading(true);
    try {
      await loadAdminLogs();
      showToast("Refreshed", "Latest recommendation logs fetched.", "info");
    } catch (err) {
      showToast("Error", err.message, "error");
    } finally {
      toggleLoading(false);
    }
  });
}

// --- Tab Switching Navigation ---
function switchTab(tabId) {
  state.currentTab = tabId;

  // Set navbar active class
  navItems.forEach(item => {
    if (item.getAttribute("data-tab") === tabId) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  // Show/Hide sections
  tabPanes.forEach(pane => {
    if (pane.id === `tab-${tabId}`) {
      pane.classList.remove("hidden");
    } else {
      pane.classList.add("hidden");
    }
  });

  // Update Header Title
  switch (tabId) {
    case "dashboard":
      tabTitle.innerHTML = 'Learning Dashboard';
      refreshDashboard();
      break;
    case "search":
      tabTitle.innerHTML = 'Catalog Search';
      runSearch();
      break;
    case "history":
      tabTitle.innerHTML = 'Study Journal';
      renderHistoryTimeline();
      break;
    case "admin":
      tabTitle.innerHTML = 'Admin Console';
      loadAdminDashboard();
      break;
  }
}

// --- Refresh Functions ---
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

// --- Recommendation Cache (localStorage fallback) ---
const RECO_CACHE_KEY = "reco_cache";
const RECO_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

function getRecoCache() {
  try {
    const raw = localStorage.getItem(RECO_CACHE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function setRecoCache(data) {
  try {
    localStorage.setItem(RECO_CACHE_KEY, JSON.stringify({ ts: Date.now(), data }));
  } catch { /* storage full — ignore */ }
}

function isRecoCacheValid(cache) {
  return cache && (Date.now() - cache.ts) < RECO_CACHE_TTL_MS;
}

// --- Load Recommendations ---
async function loadRecommendations() {
  // Show Skeletons
  railForYou.innerHTML = renderSkeletons(4);
  railYouMayLike.innerHTML = renderSkeletons(4);
  railPopular.innerHTML = renderSkeletons(4);

  const cached = getRecoCache();
  let forYouRes, youMayRes, popularRes;
  let hitRateLimit = false;

  try {
    forYouRes = await apiRequest("/recommendations/for-you", "POST", { limit: 10 });
  } catch (err) {
    if (err.message?.includes("429") || err.message?.includes("Rate limit")) {
      hitRateLimit = true;
    }
  }

  try {
    youMayRes = await apiRequest("/recommendations/you-may-also-like", "POST", { limit: 10 });
  } catch (err) {
    if (err.message?.includes("429") || err.message?.includes("Rate limit")) {
      hitRateLimit = true;
    }
  }

  try {
    popularRes = await apiRequest("/recommendations/popular", "POST", { limit: 10 });
  } catch (err) {
    if (err.message?.includes("429") || err.message?.includes("Rate limit")) {
      hitRateLimit = true;
    }
  }

  // If at least one succeeded, cache the results
  if (forYouRes || youMayRes || popularRes) {
    setRecoCache({ forYou: forYouRes, youMay: youMayRes, popular: popularRes });
  }

  // Render — prefer fresh data, fallback to cache, then show message
  if (forYouRes) {
    railForYou.innerHTML = renderCourseCards(forYouRes.items, forYouRes.source);
  } else if (cached?.data?.forYou) {
    railForYou.innerHTML = renderCourseCards(cached.data.forYou.items, cached.data.forYou.source);
  }

  if (youMayRes) {
    railYouMayLike.innerHTML = renderCourseCards(youMayRes.items, youMayRes.source);
  } else if (cached?.data?.youMay) {
    railYouMayLike.innerHTML = renderCourseCards(cached.data.youMay.items, cached.data.youMay.source);
  }

  if (popularRes) {
    railPopular.innerHTML = renderCourseCards(popularRes.items, popularRes.source);
  } else if (cached?.data?.popular) {
    railPopular.innerHTML = renderCourseCards(cached.data.popular.items, cached.data.popular.source);
  }

  if (hitRateLimit) {
    const msg = isRecoCacheValid(cached)
      ? "Rate limit reached — showing cached recommendations."
      : "Rate limit reached — please try again in a moment.";
    showToast("Slow down", msg, "info");
  }
}

// --- Load History ---
async function loadHistory() {
  const data = await apiRequest("/history/", "GET");
  state.history = data.history.map(item => item.item_idx);
  statHistoryCount.textContent = state.history.length;
}

// --- Render Skeletons ---
function renderSkeletons(count) {
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

// --- Course Cards Renderer ---
function renderCourseCards(items, source) {
  if (!items || items.length === 0) {
    return `<div class="empty-rail-msg">No recommendations available. Update your history to trigger predictions.</div>`;
  }

  return items.map(item => {
    const formattedDuration = formatDuration(item.duration);
    const isBert = source === "bert4rec_personalized" || source === "bert4rec";
    const scoreText = (item.score !== undefined && !isBert) ? `${Math.round(item.score * 100)}% Match` : "";



    return `
      <div class="card" onclick="openCourseDetail(${item.item_idx})">
        <div class="card-img-wrapper">
          <img src="${escapeHtml(item.thumbnail_url)}" alt="${escapeHtml(item.title)}" />
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
            <span class="badge badge-light-blue">${escapeHtml(item.theme || "Tech")}</span>
          </div>
          <div class="card-duration">
            <i class="fa-regular fa-clock"></i> ${escapeHtml(formattedDuration)}
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// --- Parse Helpers ---
function escapeHtml(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

function formatDuration(sec) {
  if (!sec) return "\u2014";
  const mins = Math.round(sec / 60);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  const remMins = mins % 60;
  return remMins > 0 ? `${hrs}h ${remMins}m` : `${hrs}h`;
}

// --- Search Engine ---
async function runSearch() {
  searchResultsGrid.innerHTML = renderSkeletons(8);
  const q = searchInput.value.trim();

  try {
    const res = await apiRequest(`/courses/?q=${encodeURIComponent(q)}`, "GET");
    let courses = res.data;

    // Apply front-end filtering
    const difficultyVal = filterDifficulty.value;
    const languageVal = filterLanguage.value;
    const typeVal = filterType.value;

    if (difficultyVal) {
      courses = courses.filter(c => c.difficulty && c.difficulty.toLowerCase().includes(difficultyVal.toLowerCase()));
    }
    if (languageVal) {
      courses = courses.filter(c => c.language === languageVal);
    }
    if (typeVal) {
      courses = courses.filter(c => c.type === typeVal);
    }

    searchCount.textContent = `Showing ${courses.length} courses`;

    if (courses.length === 0) {
      searchResultsGrid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; width: 100%;">
          <i class="fa-solid fa-face-frown-open"></i>
          <h3>No courses found</h3>
          <p>Try refining your search text or removing filters.</p>
        </div>
      `;
      return;
    }

    searchResultsGrid.innerHTML = renderCourseCards(courses);
  } catch (err) {
    showToast("Search failed", err.message, "error");
  }
}

// --- Render History Timeline ---
async function renderHistoryTimeline() {
  toggleLoading(true);
  try {
    const data = await apiRequest("/history/", "GET");
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

// Global functions for inline onclick handlers
window.deleteHistoryItem = async function (item_idx) {
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
};

// --- Course Details Drawer ---
window.openCourseDetail = async function (item_idx) {
  toggleLoading(true);
  drawerVideo.pause();

  try {
    const course = await apiRequest(`/courses/${item_idx}`, "GET");
    state.openCourse = course;

    // Set text contents
    drawerTitle.textContent = course.title;
    drawerMeta.textContent = `${course.language || "fr"} • ${course.type || "Course"} • ${formatDuration(course.duration)}`;
    drawerDesc.textContent = course.description || "No description available.";

    // Set tags
    let tagsHtml = "";
    if (course.difficulty) tagsHtml += `<span class="badge badge-indigo">${escapeHtml(course.difficulty)}</span>`;
    if (course.theme) tagsHtml += `<span class="badge badge-blue">${escapeHtml(course.theme)}</span>`;
    if (course.software) tagsHtml += `<span class="badge badge-orange">${escapeHtml(course.software)}</span>`;
    if (course.job) tagsHtml += `<span class="badge badge-green">${escapeHtml(course.job)}</span>`;
    drawerTags.innerHTML = tagsHtml;

    // Set poster image & reset video
    drawerVideo.poster = course.thumbnail_url || "/assets/thumbnail.png";
    drawerVideo.load();

    // Update learn button toggle
    updateDrawerToggleButton();

    // Load Similar Courses
    drawerSimilar.innerHTML = `<div class="spinner" style="width: 24px; height: 24px; border-width: 2px; margin: 20px auto;"></div>`;
    detailDrawer.classList.remove("hidden");

    const similarRes = await apiRequest(`/recommendations/similar/${course.item_idx}`, "POST", { limit: 4 });
    renderSimilarItems(similarRes.items);

  } catch (err) {
    showToast("Error", "Could not load course details: " + err.message, "error");
  } finally {
    toggleLoading(false);
  }
};

function updateDrawerToggleButton() {
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

// --- Admin Dashboard & Logs ---
async function loadAdminDashboard() {
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

    await loadAdminLogs();
  } catch (err) {
    showToast("Admin access error", err.message, "error");
  } finally {
    toggleLoading(false);
  }
}

async function loadAdminLogs() {
  const res = await apiRequest("/admin/recommendation-logs", "GET");
  state.logs = res.logs;

  // Render table rows
  if (!state.logs || state.logs.length === 0) {
    logsTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No logs recorded. Query recommendations to trigger audits.</td></tr>`;
    latencyBars.innerHTML = `<div class="chart-placeholder">No logs recorded yet. Query the model to track latencies!</div>`;
    return;
  }

  logsTbody.innerHTML = state.logs.map(log => {
    const date = new Date(log.timestamp + "Z").toLocaleTimeString();
    return `
      <tr>
        <td title="${escapeHtml(log.timestamp)}">${escapeHtml(date)}</td>
        <td><code>${escapeHtml(log.username || "anonymous")}</code></td>
        <td><span class="badge ${getStrategyBadge(log.strategy)}">${escapeHtml(log.strategy)}</span></td>
        <td><strong>${Math.round(log.latency_ms)} ms</strong></td>
        <td title="${escapeHtml(log.history)}"><code>${escapeHtml(log.history || "empty")}</code></td>
        <td title="${escapeHtml(log.results)}"><code>${escapeHtml(log.results || "empty")}</code></td>
      </tr>
    `;
  }).join("");

  // Draw latency charts
  renderLatencyChart();
}

function getStrategyBadge(strategy) {
  if (strategy === "bert4rec_personalized") return "badge-indigo";
  if (strategy === "vector_similarity") return "badge-blue";
  if (strategy === "popularity_nb_views") return "badge-light-blue";
  if (strategy.includes("fallback")) return "badge-orange";
  return "badge-rose";
}

function renderLatencyChart() {
  // Grab the last 12 log queries and display them
  const recentLogs = [...state.logs].slice(0, 12).reverse();

  if (recentLogs.length === 0) return;

  latencyBars.innerHTML = recentLogs.map(log => {
    // Max visual height is 150px representing 50ms latency
    const maxVal = 50.0;
    const height = Math.min((log.latency_ms / maxVal) * 100, 100); // percentage height

    let strategyClass = "pop";
    if (log.strategy === "bert4rec_personalized") strategyClass = "b4r";
    if (log.strategy === "vector_similarity") strategyClass = "sim";

    const timeLabel = new Date(log.timestamp + "Z").toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const tooltip = `${log.strategy}\nLatency: ${log.latency_ms.toFixed(1)}ms\nTime: ${timeLabel}`;

    return `
      <div class="latency-bar ${strategyClass}" style="height: ${height}%;" title="${escapeHtml(tooltip)}"></div>
    `;
  }).join("");
}