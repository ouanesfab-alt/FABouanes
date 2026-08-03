// FABOuanes ERP — Instant Native Hover Prefetcher & Random Vibrant Progress Bar Module

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
  if (url.includes('/logout') || url.includes('/print/')) return;

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

export function initInstantNavModule() {
  document.addEventListener('mouseover', (e) => {
    const link = e.target.closest('a');
    if (link && link.href) prefetch(link.href);
  }, { passive: true });

  document.addEventListener('touchstart', (e) => {
    const link = e.target.closest('a');
    if (link && link.href) prefetch(link.href);
  }, { passive: true });

  document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
    if (link.target === '_blank' || link.hasAttribute('download')) return;

    try {
      const urlObj = new URL(link.href, window.location.origin);
      if (urlObj.origin === window.location.origin) {
        triggerRainbowProgressBar();
      }
    } catch (err) {}
  });
}
