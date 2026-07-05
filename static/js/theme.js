(function(){
  const themeColors={
    light:'#1a2235',
    dark:'#0d1117',
    windows:'#0067c0',
    'windows-dark':'#202020'
  };
  const fonts={jakarta:true,arial:true,calibri:true,system:true};
  const navLayouts={horizontal:true,vertical:true};

  function readStorage(key,fallback){
    try{
      const value=localStorage.getItem(key);
      return value===null?fallback:value;
    }catch(e){
      return fallback;
    }
  }

  function writeStorage(key,value){
    try{ localStorage.setItem(key,value); }catch(e){}
  }

  function removeStorage(key){
    try{ localStorage.removeItem(key); }catch(e){}
  }

  function markSelected(selector,key,value){
    document.querySelectorAll(selector).forEach(function(button){
      const selected=button.dataset[key]===value;
      button.classList.toggle('active',selected);
      button.setAttribute('aria-pressed',selected?'true':'false');
    });
  }

  function applyTheme(theme,opts){
    const name=themeColors[theme]?theme:'light';
    if(opts&&opts.animate) document.documentElement.classList.add('theme-changing');
    document.documentElement.setAttribute('data-theme',name);
    const meta=document.querySelector('meta[name="theme-color"]');
    if(meta) meta.setAttribute('content',themeColors[name]);
    markSelected('.js-theme','themeValue',name);
    window.clearTimeout(window.fabThemeTimer);
    if(opts&&opts.animate){
      window.fabThemeTimer=window.setTimeout(function(){
        document.documentElement.classList.remove('theme-changing');
      },280);
    }
  }

  function applyFont(font){
    const name=fonts[font]?font:'system';
    document.documentElement.setAttribute('data-font',name);
    markSelected('.js-font','font',name);
  }

  function navHidden(){
    return document.documentElement.getAttribute('data-nav-hidden')==='1';
  }

  function updateSideNavToggle(){
    const button=document.getElementById('sideNavToggle');
    if(!button) return;
    const vertical=document.documentElement.getAttribute('data-nav')==='vertical';
    const hidden=navHidden();
    button.hidden=!vertical;
    button.setAttribute('aria-label',hidden?'Afficher la barre verticale':'Masquer la barre verticale');
    button.setAttribute('aria-expanded',hidden?'false':'true');
    button.innerHTML='<i class="bi bi-list"></i>';
  }

  function applyNavLayout(layout){
    const name=navLayouts[layout]?layout:'horizontal';
    document.documentElement.setAttribute('data-nav',name);
    markSelected('.js-nav-layout','navLayout',name);
    updateSideNavToggle();
  }

  function applyNavHidden(hidden){
    const value=hidden?'1':'0';
    document.documentElement.setAttribute('data-nav-hidden',value);
    writeStorage('fab_nav_hidden',value);
    updateSideNavToggle();
  }

  try{
    const params=new URLSearchParams(window.location.search);
    if(params.get('mobile_shell')==='1') writeStorage('fab_mobile_shell','1');
    if(params.get('mobile_shell')==='0') removeStorage('fab_mobile_shell');
  }catch(e){}

  applyTheme(readStorage('fab_theme','light'));
  applyFont(readStorage('fab_font','system'));
  applyNavHidden(readStorage('fab_nav_hidden','0')==='1');
  applyNavLayout(readStorage('fab_nav_layout','horizontal'));

  document.addEventListener('click',function(event){
    const themeButton=event.target.closest('.js-theme');
    if(themeButton){
      event.preventDefault();
      const theme=themeButton.dataset.themeValue;
      applyTheme(theme,{animate:true});
      writeStorage('fab_theme',theme);
      return;
    }

    const fontButton=event.target.closest('.js-font');
    if(fontButton){
      event.preventDefault();
      const font=fontButton.dataset.font;
      applyFont(font);
      writeStorage('fab_font',font);
      return;
    }

    const navButton=event.target.closest('.js-nav-layout');
    if(navButton){
      event.preventDefault();
      const layout=navButton.dataset.navLayout;
      applyNavLayout(layout);
      writeStorage('fab_nav_layout',layout);
    }
  });

  const sideNavToggle=document.getElementById('sideNavToggle');
  if(sideNavToggle){
    sideNavToggle.addEventListener('click',function(){
      applyNavHidden(!navHidden());
    });
  }

  /*
   * P3 — Auto-activate vertical sidebar on large screens (≥ 1400px)
   * Only when the user has not explicitly set a nav layout preference.
   * Respects user choices: once the user picks horizontal or vertical
   * manually, this auto-behaviour is permanently disabled for them.
   */
  (function autoSidebar() {
    var LAYOUT_KEY = 'fab_nav_layout';
    var AUTO_KEY   = 'fab_nav_auto_applied';

    // Check if user has ever manually set a nav layout
    var userHasChosen = false;
    try { userHasChosen = localStorage.getItem(LAYOUT_KEY) !== null; } catch(e) {}

    if (userHasChosen) return; // Respect explicit user preference

    var THRESHOLD = 1400; // px — same as CSS P3-A breakpoint

    function applyAutoSidebar() {
      var isWide = window.innerWidth >= THRESHOLD;
      var current = document.documentElement.getAttribute('data-nav');

      if (isWide && current !== 'vertical') {
        document.documentElement.classList.add('desktop-auto-sidebar');
        // Use the existing applyNavLayout function already in scope
        document.documentElement.setAttribute('data-nav', 'vertical');
        var btn = document.getElementById('sideNavToggle');
        if (btn) { btn.hidden = false; }
      } else if (!isWide && current === 'vertical') {
        // Only revert if we auto-applied it (not if user chose vertical)
        try {
          var autoApplied = sessionStorage.getItem(AUTO_KEY) === '1';
          if (autoApplied) {
            document.documentElement.setAttribute('data-nav', 'horizontal');
            document.documentElement.classList.remove('desktop-auto-sidebar');
            var btn2 = document.getElementById('sideNavToggle');
            if (btn2) { btn2.hidden = true; }
          }
        } catch(e) {}
      }

      // Record that we auto-applied (session only, not persistent)
      if (isWide) {
        try { sessionStorage.setItem(AUTO_KEY, '1'); } catch(e) {}
      }
    }

    // Apply on load (after a short delay to let existing CSS settle)
    setTimeout(applyAutoSidebar, 0);

    // Re-evaluate on resize (debounced)
    var resizeTimer;
    window.addEventListener('resize', function() {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(applyAutoSidebar, 150);
    }, { passive: true });
  })();
})();
