// FABOuanes ERP — Instant Native Hover Prefetcher & SPA PJAX Page Switcher Module

let progressBar = null;

const RANDOM_GRADIENTS = [
  {
    bg: 'linear-gradient(90deg, #ff0000, #ff7f00, #ffff00, #00ff00, #007aff, #4b0082, #8b00ff)',
    shadow: '0 0 12px rgba(255, 127, 0, 0.9), 0 0 6px rgba(0, 122, 255, 0.9)'
  },
  {
    bg: 'linear-gradient(90deg, #ff007f, #7f00ff, #00f0ff, #ff007f)',
    shadow: '0 0 12px rgba(255, 0, 127, 0.9), 0 0 6px rgba(0, 240, 255, 0.9)'
  },
  {
    bg: 'linear-gradient(90deg, #ff4500, #ff8c00, #ffd700, #ff1493)',
    shadow: '0 0 12px rgba(255, 69, 0, 0.9), 0 0 6px rgba(255, 215, 0, 0.9)'
  },
  {
    bg: 'linear-gradient(90deg, #00f2fe, #4facfe, #00ff87, #60efff)',
    shadow: '0 0 12px rgba(0, 242, 254, 0.9), 0 0 6px rgba(0, 255, 135, 0.9)'
  },
  {
    bg: 'linear-gradient(90deg, #b000ff, #e100ff, #00e5ff, #7000ff)',
    shadow: '0 0 12px rgba(176, 0, 255, 0.9), 0 0 6px rgba(0, 229, 255, 0.9)'
  },
  {
    bg: 'linear-gradient(90deg, #39ff14, #00e5ff, #007aff, #39ff14)',
    shadow: '0 0 12px rgba(57, 255, 20, 0.9), 0 0 6px rgba(0, 122, 255, 0.9)'
  }
];

function getProgressBar() {
  if (!progressBar) {
    progressBar = document.createElement('div');
    progressBar.id = 'instant-nav-bar';
    progressBar.style.cssText = 'position:fixed;top:0;left:0;height:2.5px;z-index:999999;transition:width 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;width:0%;pointer-events:none;';

    if (!document.getElementById('rainbow-nav-style')) {
      const style = document.createElement('style');
      style.id = 'rainbow-nav-style';
      style.textContent = '@keyframes rainbow-shift { 0% { background-position: 0% 50%; } 100% { background-position: 200% 50%; } } #instant-nav-bar { animation: rainbow-shift 2s infinite linear; }';
      document.head.appendChild(style);
    }

    document.body.appendChild(progressBar);
  }
  return progressBar;
}

function triggerRainbowProgressBar() {
  const bar = getProgressBar();
  const palette = RANDOM_GRADIENTS[Math.floor(Math.random() * RANDOM_GRADIENTS.length)];

  bar.style.background = palette.bg;
  bar.style.backgroundSize = '200% 100%';
  bar.style.boxShadow = palette.shadow;

  bar.style.opacity = '1';
  bar.style.width = '45%';
  setTimeout(() => {
    bar.style.width = '100%';
    setTimeout(() => {
      bar.style.opacity = '0';
      setTimeout(() => {
        bar.style.width = '0%';
      }, 300);
    }, 200);
  }, 100);
}

const prefetchedUrls = new Set();

function prefetch(url) {
  if (!url || prefetchedUrls.has(url)) return;
  if (url.startsWith('#') || url.startsWith('javascript:')) return;
  if (url.includes('/logout') || url.includes('/print/') || url.includes('/export')) return;

  try {
    const urlObj = new URL(url, window.location.origin);
    if (urlObj.origin !== window.location.origin) return;

    prefetchedUrls.add(url);
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = url;
    link.as = 'document';
    document.head.appendChild(link);
  } catch (e) {}
}

function isPjaxEligible(link) {
  if (!link) return false;
  const href = link.getAttribute('href');
  if (!href || href.startsWith('#') || href.startsWith('javascript:')) return false;
  if (link.target === '_blank' || link.hasAttribute('download') || link.getAttribute('data-no-pjax') === 'true') return false;
  if (href.includes('/logout') || href.includes('/print/') || href.includes('/export')) return false;

  try {
    const urlObj = new URL(link.href, window.location.origin);
    return urlObj.origin === window.location.origin;
  } catch (e) {
    return false;
  }
}

function cleanupPageGlobals() {
  try {
    if (typeof window.Chart !== 'undefined' && window.Chart.instances) {
      Object.keys(window.Chart.instances).forEach(id => {
        try { window.Chart.instances[id].destroy(); } catch (e) {}
      });
    }
  } catch (e) {}

  if (window.reportChartInstances) {
    Object.keys(window.reportChartInstances).forEach(k => {
      try { window.reportChartInstances[k].destroy(); } catch(e) {}
    });
    delete window.reportChartInstances;
  }
  if (window.kpiChartInstance) {
    try { window.kpiChartInstance.destroy(); } catch(e) {}
    window.kpiChartInstance = null;
  }

  // Clean up any open Bootstrap Modals & Backdrops
  try {
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    document.querySelectorAll('.modal.show').forEach(el => {
      el.classList.remove('show');
      el.style.display = 'none';
    });
    document.body.classList.remove('modal-open', 'kpi-modal-open', 'drawer-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');
  } catch (e) {}

  // Close drawers & overlays
  try {
    const kpiOverlay = document.getElementById('kpiSheetOverlay');
    if (kpiOverlay) kpiOverlay.classList.remove('open');
    const drawer = document.getElementById('drawer');
    const drawerOverlay = document.getElementById('drawerOverlay');
    if (drawer) drawer.classList.remove('open');
    if (drawerOverlay) drawerOverlay.classList.remove('open');
  } catch (e) {}
}


async function loadPjaxPage(url, pushState = true) {
  const currentContainer = document.querySelector('.app-content');
  if (!currentContainer) {
    window.location.href = url;
    return;
  }

  triggerRainbowProgressBar();

  try {
    const response = await fetch(url, {
      headers: {
        'X-PJAX': 'true',
        'X-Requested-With': 'XMLHttpRequest'
      }
    });

    if (!response.ok) {
      window.location.href = url;
      return;
    }

    const htmlText = await response.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlText, 'text/html');

    const newContainer = doc.querySelector('.app-content');
    if (!newContainer) {
      window.location.href = url;
      return;
    }

    // Clean up stale chart instances before DOM swap
    cleanupPageGlobals();

    // Direct, single-frame instant replacement (no double flash)
    currentContainer.innerHTML = newContainer.innerHTML;
    currentContainer.style.opacity = '1';

    // Update Document Title
    if (doc.title) {
      document.title = doc.title;
    }

    // Update PushState URL if requested
    if (pushState) {
      window.history.pushState({ pjaxUrl: url }, doc.title || '', url);
    }

    // Update Navbar Active States
    updateNavbarActiveLinks(url);

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'instant' });

    // Execute scripts contained within the new page content
    executeContainerScripts(currentContainer);

    // Fire custom page-loaded & resize events for chart & layout re-initialization
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
      document.dispatchEvent(new CustomEvent('fab:page-loaded', { detail: { url } }));
    }, 20);

  } catch (err) {
    console.warn('[PJAX] Navigation failed, fallback to standard link:', err);
    window.location.href = url;
  }
}

function updateNavbarActiveLinks(url) {
  try {
    const path = new URL(url, window.location.origin).pathname;
    document.querySelectorAll('.nav-link, .fab-drawer-item, .bottom-nav-item').forEach(link => {
      const href = link.getAttribute('href');
      if (!href) return;
      const linkPath = new URL(href, window.location.origin).pathname;
      if (linkPath === path || (path !== '/' && linkPath.length > 1 && path.startsWith(linkPath))) {
        link.classList.add('active');
        link.setAttribute('aria-current', 'page');
      } else {
        link.classList.remove('active');
        link.removeAttribute('aria-current');
      }
    });
  } catch (e) {}
}

function executeContainerScripts(container) {
  const scripts = Array.from(container.querySelectorAll('script'));
  scripts.forEach(script => {
    const newScript = document.createElement('script');
    Array.from(script.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
    if (script.src) {
      newScript.src = script.src;
    } else {
      newScript.textContent = script.innerHTML;
    }
    script.parentNode.replaceChild(newScript, script);
  });
}



export function initInstantNavModule() {
  // Patch document.addEventListener for DOMContentLoaded so dynamic PJAX scripts execute immediately
  if (!window._pjaxDCLPatched) {
    window._pjaxDCLPatched = true;
    const origAddEv = document.addEventListener.bind(document);
    document.addEventListener = function (type, listener, options) {
      origAddEv(type, listener, options);
      if (type === 'DOMContentLoaded' && (document.readyState === 'complete' || document.readyState === 'interactive')) {
        try {
          if (typeof listener === 'function') {
            setTimeout(listener, 10);
          } else if (listener && typeof listener.handleEvent === 'function') {
            setTimeout(() => listener.handleEvent(), 10);
          }
        } catch (e) {}
      }
    };
  }

  // Prefetch on hover/touch
  document.addEventListener('mouseover', (e) => {
    const link = e.target.closest('a');
    if (link && link.href) prefetch(link.href);
  }, { passive: true });

  document.addEventListener('touchstart', (e) => {
    const link = e.target.closest('a');
    if (link && link.href) prefetch(link.href);
  }, { passive: true });

  // SPA PJAX click interceptor
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link || !isPjaxEligible(link)) return;

    // Ignore modifier clicks (Ctrl+Click, Cmd+Click, Shift+Click)
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

    e.preventDefault();
    loadPjaxPage(link.href, true);
  });

  // Handle Browser Back/Forward buttons
  window.addEventListener('popstate', (e) => {
    const targetUrl = window.location.href;
    loadPjaxPage(targetUrl, false);
  });
}


