// -------------------------------------------------------------
// DOM.JS
// All DOM element references — queried once at module load time.
// ES modules are deferred, so DOM is ready when this runs.
// -------------------------------------------------------------

// Auth / Dashboard screens
export const authScreen = document.getElementById("auth-screen");
export const dashboardScreen = document.getElementById("dashboard-screen");
export const loginForm = document.getElementById("login-form");
export const registerForm = document.getElementById("register-form");
export const goToRegister = document.getElementById("go-to-register");
export const goToLogin = document.getElementById("go-to-login");
export const logoutBtn = document.getElementById("btn-logout");

// Auth tabs / theme toggle
export const authTabs = document.getElementById("auth-tabs") || document.querySelector(".auth-tabs");
export const tabLoginBtn = document.getElementById("tab-login");
export const tabRegisterBtn = document.getElementById("tab-register");
export const authTitle = document.getElementById("auth-title");
export const authSubtitle = document.getElementById("auth-subtitle");
export const themeToggleSidebar = document.getElementById("theme-toggle");
export const themeToggleAuth = document.getElementById("theme-toggle-auth");
export const passwordStrengthLabel = document.getElementById("password-strength-label");
export const tabPanes = document.querySelectorAll(".tab-pane");
export const navItems = document.querySelectorAll(".nav-item");
export const tabTitle = document.getElementById("tab-title");
export const toastContainer = document.getElementById("toast-container");
export const loadingOverlay = document.getElementById("loading-overlay");

// User details
export const userDisplayName = document.getElementById("user-display-name");
export const userRoleBadge = document.getElementById("user-role-badge");

// Rails
export const railForYou = document.getElementById("rail-for-you");
export const railYouMayLike = document.getElementById("rail-you-may-also-like");
export const railPopular = document.getElementById("rail-popular");

// Search
export const searchInput = document.getElementById("search-input");
export const searchClearBtn = document.getElementById("search-clear");
export const searchResultsGrid = document.getElementById("search-results-grid");
export const searchCount = document.getElementById("search-count");
export const filterLanguage = document.getElementById("filter-language");
export const facetPanel = document.getElementById("facet-panel");
export const filtersClearBtn = document.getElementById("filters-clear");
export const paginationNav = document.getElementById("pagination");

// History
export const historyTimeline = document.getElementById("history-timeline-container");
export const historyEmptyState = document.getElementById("history-empty");
export const clearHistoryBtn = document.getElementById("btn-clear-history");
export const statHistoryCount = document.getElementById("stat-history-count");

// Admin
export const adminModelStatus = document.getElementById("admin-model-status");
export const adminModelMaxLen = document.getElementById("admin-model-maxlen");
export const adminModelVocab = document.getElementById("admin-model-vocab");
export const adminModelDim = document.getElementById("admin-model-dim");
export const btnSyncCatalog = document.getElementById("btn-sync-catalog");
export const btnRebuildEmb = document.getElementById("btn-rebuild-emb");
export const btnRefreshLogs = document.getElementById("btn-refresh-logs");
export const logsTbody = document.getElementById("logs-tbody");

// Admin monitoring
export const latencyWindowSelect = document.getElementById("latency-window");
export const latencyTiles = document.getElementById("latency-tiles");
export const latencyLegend = document.getElementById("latency-legend");
export const latencyChart = document.getElementById("latency-chart");
export const latencyTable = document.getElementById("latency-table");
export const btnLatencyTable = document.getElementById("btn-latency-table");

// Admin course management
export const pipelineBanner = document.getElementById("pipeline-banner");
export const adminCoursesTbody = document.getElementById("admin-courses-tbody");
export const adminCoursesPagination = document.getElementById("admin-courses-pagination");
export const adminCourseSearch = document.getElementById("admin-course-search");
export const btnAddCourse = document.getElementById("btn-add-course");
export const courseModal = document.getElementById("course-modal");
export const courseModalTitle = document.getElementById("course-modal-title");
export const courseForm = document.getElementById("course-form");
export const courseItemIdx = document.getElementById("course-item-idx");
export const btnSaveCourse = document.getElementById("btn-save-course");
export const btnCancelCourse = document.getElementById("btn-cancel-course");
export const btnCloseCourseModal = document.getElementById("btn-close-course-modal");

// Drawer
export const detailDrawer = document.getElementById("detail-drawer");
export const btnCloseDrawer = document.getElementById("btn-close-drawer");
export const drawerVideo = document.getElementById("drawer-video");
export const drawerTitle = document.getElementById("drawer-title");
export const drawerMeta = document.getElementById("drawer-meta-info");
export const drawerDesc = document.getElementById("drawer-description");
export const drawerTags = document.getElementById("drawer-tags-container");
export const btnToggleLearn = document.getElementById("btn-toggle-learn");
export const drawerSimilar = document.getElementById("drawer-similar-courses");