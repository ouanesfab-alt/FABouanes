// dashboard-fonts.js — Corporate Typography & Brand Palette System
// Lightweight, offline-first typography enhancer for FABOuanes executive branding
(function () {
  'use strict';

  const EXECUTIVE_FONTS = [
    {
      id: 1,
      name: "Plus Jakarta Sans",
      query: "Plus+Jakarta+Sans",
      stack: "'Plus Jakarta Sans', system-ui, -apple-system, 'SF Pro Display', sans-serif",
      weight: "700"
    },
    {
      id: 2,
      name: "Outfit",
      query: "Outfit",
      stack: "'Outfit', 'Plus Jakarta Sans', system-ui, sans-serif",
      weight: "800"
    },
    {
      id: 3,
      name: "Inter",
      query: "Inter",
      stack: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      weight: "700"
    },
    {
      id: 4,
      name: "System Executive",
      query: "system",
      stack: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      weight: "700"
    }
  ];

  const BRAND_ACCENTS = [
    '#007AFF', // Sequoia Blue
    '#25D366', // Emerald Success
    '#34C759', // Apple Mint
    '#5856D6', // Royal Indigo
    '#AF52DE', // Elegant Purple
    '#FF9500'  // Warm Amber
  ];

  let currentFontIdx = 0;
  let currentColorIdx = 0;

  function applyFontObj(fontObj, index, isInitial) {
    if (!fontObj) return;
    const targets = document.querySelectorAll('.fab-logo-text-main, .nav-brand-title');
    targets.forEach(el => {
      el.style.fontFamily = fontObj.stack;
      if (fontObj.weight) el.style.fontWeight = fontObj.weight;
    });

    try {
      localStorage.setItem('fab_active_font_query', fontObj.query);
      localStorage.setItem('fab_active_font_stack', fontObj.stack);
      localStorage.setItem('fab_active_font_name', fontObj.name);
    } catch (e) {}

    if (!isInitial && typeof window.showToast === 'function') {
      window.showToast(`Typographie : ${fontObj.name}`, 'info');
    }
  }

  function applyColor(colorStr) {
    if (!colorStr) return;
    const targets = document.querySelectorAll('.fab-logo-text-main, .page-title-main');
    targets.forEach(el => {
      el.style.setProperty('color', colorStr, 'important');
    });
    try {
      localStorage.setItem('fab_active_color', colorStr);
    } catch (e) {}
  }

  function rotateFont() {
    currentFontIdx = (currentFontIdx + 1) % EXECUTIVE_FONTS.length;
    applyFontObj(EXECUTIVE_FONTS[currentFontIdx], currentFontIdx, false);
  }

  function rotateColor() {
    currentColorIdx = (currentColorIdx + 1) % BRAND_ACCENTS.length;
    applyColor(BRAND_ACCENTS[currentColorIdx]);
  }

  function restoreSavedFontAndColor() {
    try {
      const savedQuery = localStorage.getItem('fab_active_font_query');
      if (savedQuery) {
        const found = EXECUTIVE_FONTS.findIndex(f => f.query === savedQuery || f.name === savedQuery);
        if (found !== -1) {
          currentFontIdx = found;
          applyFontObj(EXECUTIVE_FONTS[found], found, true);
        }
      }
      const savedColor = localStorage.getItem('fab_active_color');
      if (savedColor && BRAND_ACCENTS.includes(savedColor)) {
        currentColorIdx = BRAND_ACCENTS.indexOf(savedColor);
        applyColor(savedColor);
      }
    } catch (e) {}
  }

  function init() {
    const logoTargets = document.querySelectorAll('.fab-logo-text-main, .fab-logo-text-sub, .nav-brand, .nav-brand-title');
    logoTargets.forEach(target => {
      target.style.cursor = 'pointer';
      target.setAttribute('title', 'Cliquer pour alterner la palette et la typographie');
      target.addEventListener('click', (e) => {
        // Prevent default only if target is just a toggle, not if user navigates to home
        if (target.classList.contains('nav-brand-title') || target.classList.contains('fab-logo-text-main')) {
          e.preventDefault();
          e.stopPropagation();
          rotateFont();
          rotateColor();
        }
      });
    });

    restoreSavedFontAndColor();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
