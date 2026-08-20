// -------------------------------------------------------------
// APP.JS
// Entry point — initializes the application.
// This is the ONLY file referenced in <script> tag.
// -------------------------------------------------------------

import { initTheme } from "./theme.js";
import { checkAuth, logout } from "./auth.js";
import { setupEventListeners } from "./events.js";
import { openCourseDetail } from "./drawer.js";
import { deleteHistoryItem } from "./history.js";
import { runSearch } from "./search.js";

// Expose to window for inline onclick handlers in dynamically rendered HTML
window.openCourseDetail = openCourseDetail;
window.deleteHistoryItem = deleteHistoryItem;
window.__logout = logout;
window.__runSearch = runSearch;

// Initialize
initTheme();
checkAuth();
setupEventListeners();