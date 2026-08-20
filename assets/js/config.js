// -------------------------------------------------------------
// CONFIG.JS
// Application constants — no imports, no side effects.
// -------------------------------------------------------------

export const API_PREFIX = "/api/v1";

export const FACET_KEYS = ["difficulty", "theme", "software", "job_type", "type"];
export const PAGE_SIZE = 12;

export const RECO_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

export const CATEGORY_VISUALS = [
    { match: /web|html|css|javascript|react|front.?end|back.?end/i, icon: "fa-solid fa-code", cover: "cat-cover-1" },
    { match: /data|sql|analytic|statistic|big data/i, icon: "fa-solid fa-chart-column", cover: "cat-cover-2" },
    { match: /cloud|devops|kubernetes|docker|server|infra/i, icon: "fa-solid fa-cloud", cover: "cat-cover-3" },
    { match: /design|ui|ux|graphic|photo|illustrat/i, icon: "fa-solid fa-palette", cover: "cat-cover-5" },
    { match: /market|seo|communicat|business|vente|sales/i, icon: "fa-solid fa-bullhorn", cover: "cat-cover-6" },
    { match: /security|s[ée]curit|cyber|reseau|network/i, icon: "fa-solid fa-shield-halved", cover: "cat-cover-8" },
    { match: /mobile|android|ios|app/i, icon: "fa-solid fa-mobile-screen", cover: "cat-cover-4" },
    { match: /ai|ia\b|machine learning|intelligence artificielle|deep learning/i, icon: "fa-solid fa-brain", cover: "cat-cover-7" },
    { match: /manage|gestion|project|projet|leadership/i, icon: "fa-solid fa-diagram-project", cover: "cat-cover-2" },
    { match: /office|bureautique|excel|word|powerpoint/i, icon: "fa-solid fa-file-lines", cover: "cat-cover-6" },
    { match: /langue|language|anglais|english/i, icon: "fa-solid fa-language", cover: "cat-cover-4" },
];
export const DEFAULT_CATEGORY_VISUAL = { icon: "fa-solid fa-book-open", cover: "cat-cover-7" };

export const LATENCY_SERIES = [
    { key: "avg", label: "Average", color: "var(--viz-series-avg)" },
    { key: "p95", label: "P95", color: "var(--viz-series-p95)" }
];