// -------------------------------------------------------------
// UI.JS
// Toast notifications, loading overlay, button busy state.
// -------------------------------------------------------------

import { toastContainer, loadingOverlay, latencyChart } from "./dom.js";
import { LATENCY_SERIES } from "./config.js";
import { bucketLabel, formatMs } from "./utils.js";

export function showToast(title, message, type = "success") {
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
    <button class="toast-close" aria-label="Dismiss notification"><i class="fa-solid fa-xmark"></i></button>
  `;
    toast.querySelector(".toast-title").textContent = title;
    toast.querySelector(".toast-message").textContent = message;

    toastContainer.appendChild(toast);

    const dismiss = () => {
        toast.style.transform = "translateY(-20px)";
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    };

    const autoDismiss = setTimeout(dismiss, 4000);

    toast.querySelector(".toast-close").addEventListener("click", () => {
        clearTimeout(autoDismiss);
        dismiss();
    });
}

export function toggleLoading(show) {
    if (show) {
        loadingOverlay.classList.remove("hidden");
    } else {
        loadingOverlay.classList.add("hidden");
    }
}

export function setButtonBusy(btn, busy, busyText) {
    if (!btn) return;
    if (busy) {
        btn.dataset.originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ${busyText || "Please wait..."}`;
    } else {
        btn.disabled = false;
        if (btn.dataset.originalHtml) {
            btn.innerHTML = btn.dataset.originalHtml;
            delete btn.dataset.originalHtml;
        }
    }
}
export function initMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;

    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';

    const dashboardScreen = document.querySelector('#dashboard-screen');

    if (dashboardScreen) {
        dashboardScreen.appendChild(overlay);
    } else {
        document.body.appendChild(overlay);
    }


    const hamburger = document.createElement('button');
    hamburger.className = 'mobile-menu-btn';
    hamburger.setAttribute('aria-label', 'Toggle navigation menu');
    hamburger.innerHTML = '<i class="fa-solid fa-bars"></i>';

    const topbar = document.querySelector('.topbar');
    if (topbar) {
        const h1 = topbar.querySelector('h1');
        if (h1 && !topbar.querySelector('.topbar-title-area')) {
            const titleArea = document.createElement('div');
            titleArea.className = 'topbar-title-area';
            h1.parentNode.insertBefore(titleArea, h1);
            titleArea.appendChild(h1);
        }
        const titleArea = topbar.querySelector('.topbar-title-area');
        if (titleArea) {
            titleArea.insertBefore(hamburger, titleArea.firstChild);
        } else {
            topbar.insertBefore(hamburger, topbar.firstChild);
        }
    }

    const statusIndicator = topbar?.querySelector('.status-indicator');
    if (statusIndicator && !topbar.querySelector('.topbar-right')) {
        const rightGroup = document.createElement('div');
        rightGroup.className = 'topbar-right';
        statusIndicator.parentNode.insertBefore(rightGroup, statusIndicator);
        rightGroup.appendChild(statusIndicator);
    }

    function openSidebar() {
        sidebar.classList.add('mobile-open');
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        hamburger.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    }

    function closeSidebar() {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
        document.body.style.overflow = '';
        hamburger.innerHTML = '<i class="fa-solid fa-bars"></i>';
    }

    hamburger.addEventListener('click', () => {
        if (sidebar.classList.contains('mobile-open')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    overlay.addEventListener('click', closeSidebar);

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768 && sidebar.classList.contains('mobile-open')) {
                closeSidebar();
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('mobile-open')) {
            closeSidebar();
        }
    });

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (window.innerWidth > 768 && sidebar.classList.contains('mobile-open')) {
                closeSidebar();
            }
        }, 150);
    });
}
// A line chart in HTML is interactive by default: crosshair + tooltip.
export function attachLatencyHover(series, xAt, yAt) {
    const svg = latencyChart.querySelector("svg");
    const hit = latencyChart.querySelector("#latency-hitarea");
    const hover = latencyChart.querySelector("#latency-hover");
    const tooltip = latencyChart.querySelector("#latency-tooltip");
    if (!svg || !hit || !hover || !tooltip) return;

    const crosshair = hover.querySelector("line");
    const markers = hover.querySelectorAll("circle");

    function hide() {
        hover.style.display = "none";
        tooltip.classList.add("hidden");
    }

    hit.addEventListener("mousemove", event => {
        const box = svg.getBoundingClientRect();
        // Map client px into viewBox units.
        const scale = 720 / box.width;
        const vx = (event.clientX - box.left) * scale;

        let nearest = 0;
        let bestDist = Infinity;
        series.forEach((_, i) => {
            const dist = Math.abs(xAt(i) - vx);
            if (dist < bestDist) {
                bestDist = dist;
                nearest = i;
            }
        });

        const point = series[nearest];
        const x = xAt(nearest);
        crosshair.setAttribute("x1", x);
        crosshair.setAttribute("x2", x);
        LATENCY_SERIES.forEach((s, idx) => {
            markers[idx].setAttribute("cx", x);
            markers[idx].setAttribute("cy", yAt(point[s.key] || 0));
        });
        hover.style.display = "";

        tooltip.innerHTML = `
      <div class="viz-tooltip-time">${escapeHtml(bucketLabel(point.bucket))} · ${point.count} req</div>
      ${LATENCY_SERIES.map(s => `
        <div class="viz-tooltip-row">
          <span><span class="legend-swatch" style="background:${s.color}"></span> ${escapeHtml(s.label)}</span>
          <span class="viz-tooltip-value">${formatMs(point[s.key])} ms</span>
        </div>
      `).join("")}
    `;
        tooltip.style.left = `${(x / scale)}px`;
        tooltip.style.top = `${(yAt(Math.max(point.avg || 0, point.p95 || 0)) / scale)}px`;
        tooltip.classList.remove("hidden");
    });

    hit.addEventListener("mouseleave", hide);
}
function escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
}