// --- theme.js ---
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
})();



// --- api.js ---
(function(){
  const token=document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')||'';
  function absoluteUrl(url){
    if(!url) return url;
    try{
      if(url.startsWith('/')) return window.location.origin+url;
      const parsed=new URL(url);
      if(parsed.host!==window.location.host){
        parsed.hostname=window.location.hostname;
        parsed.port=window.location.port;
        parsed.protocol=window.location.protocol;
      }
      return parsed.toString();
    }catch(e){
      return url;
    }
  }
  function headers(extra){
    return Object.assign({'X-CSRFToken':token,'Content-Type':'application/json'},extra||{});
  }
  window.fabApi={csrfToken:token,absoluteUrl:absoluteUrl,headers:headers};
  window.fixUrl=window.fixUrl||absoluteUrl;
})();



// --- layout.js ---
(function () {
  document.querySelectorAll('[data-fab-switch-root]').forEach(function (root) {
    const buttons = Array.from(root.querySelectorAll('[data-fab-switch-target]'));
    const panels = buttons.map(function (btn) { return document.getElementById(btn.getAttribute('data-fab-switch-target')); }).filter(Boolean);
    const placeholder = document.getElementById(root.getAttribute('data-fab-switch-placeholder') || '');
    function reset(showPlaceholder) {
      buttons.forEach(function (btn) { btn.classList.remove('is-active'); btn.setAttribute('aria-pressed', 'false'); });
      panels.forEach(function (panel) { panel.hidden = true; });
      if (placeholder) placeholder.hidden = !showPlaceholder;
    }
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const panel = document.getElementById(btn.getAttribute('data-fab-switch-target'));
        const active = btn.classList.contains('is-active');
        reset(active);
        if (!panel || active) return;
        btn.classList.add('is-active');
        btn.setAttribute('aria-pressed', 'true');
        panel.hidden = false;
        if (placeholder) placeholder.hidden = true;
        requestAnimationFrame(function () {
          document.dispatchEvent(new CustomEvent('fab:panel-open', { detail: { panel: panel } }));
          window.dispatchEvent(new Event('resize'));
        });
      });
    });
    reset(true);
  });

  const btn = document.getElementById('drawerBtn');
  const close = document.getElementById('drawerClose');
  const drawer = document.getElementById('navDrawer');
  const overlay = document.getElementById('navOverlay');
  if (!btn || !drawer || !overlay) return;
  let previousOverflow = '';
  function open() { previousOverflow = document.body.style.overflow; drawer.classList.add('open'); overlay.classList.add('open'); document.body.style.overflow = 'hidden'; }
  function shut() { drawer.classList.remove('open'); overlay.classList.remove('open'); document.body.style.overflow = previousOverflow; }
  btn.addEventListener('click', open);
  close?.addEventListener('click', shut);
  overlay.addEventListener('click', shut);
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape' && drawer.classList.contains('open')) shut(); });
  drawer.querySelectorAll('[data-drawer-toggle]').forEach(function (toggle) {
    const group = toggle.closest('.drawer-group');
    if (!group) return;
    toggle.addEventListener('click', function (event) {
      event.preventDefault();
      const nextOpen = !group.classList.contains('open');
      group.classList.toggle('open', nextOpen);
      toggle.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
    });
  });
  drawer.querySelectorAll('a').forEach(function (link) { link.addEventListener('click', shut); });
})();

window.openInvoice = window.openInvoice || function (event, url) {
  if (event) event.preventDefault();
  let dest = url || (event && event.currentTarget && event.currentTarget.href);
  if (!dest || dest === '#' || dest === window.location.href + '#') return;
  if (dest.indexOf('/') === 0) dest = window.location.protocol + '//' + window.location.host + dest;
  window.location.href = dest;
};



// --- forms.js ---
(function(){
  const token=window.fabApi?.csrfToken||document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')||'';
  if(token){
    document.querySelectorAll('form[method="post"],form[method="POST"]').forEach(function(form){
      if(form.querySelector('input[name="csrf_token"]')) return;
      const input=document.createElement('input');
      input.type='hidden';
      input.name='csrf_token';
      input.value=token;
      form.appendChild(input);
    });
    window.fabCsrfToken=token;
  }

  document.addEventListener('submit', function(event) {
    const form = event.target;
    if (!form || form.dataset.noSpinner || form.hasAttribute('data-no-spinner') || form.target === '_blank') return;
    if ((form.method || '').toLowerCase() === 'get') return;
    
    const button = form.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
    if (!button || button.classList.contains('is-loading')) return;
    
    button.classList.add('is-loading', 'disabled');
    const originalHTML = button.innerHTML;
    button.setAttribute('data-original-html', originalHTML);
    
    // Prepend a beautiful spinner to the existing content
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>' + originalHTML;
    
    // Disable click events after a tiny delay so the submit event finishes executing
    setTimeout(() => {
      button.disabled = true;
    }, 0);
    
    // Safety fallback to restore the button after 8 seconds (e.g., if submission is blocked or slow)
    setTimeout(() => {
      if (button.classList.contains('is-loading')) {
        button.classList.remove('is-loading', 'disabled');
        button.disabled = false;
        button.innerHTML = originalHTML;
      }
    }, 8000);
  });

  const today=(new Date(Date.now() - new Date().getTimezoneOffset() * 60000)).toISOString().slice(0,10);
  document.querySelectorAll('input[type="date"]').forEach(function(input){
    if(input.value || input.dataset.noAutoDate==='1') return;
    const form=input.closest('form');
    if(form && (form.method||'get').toLowerCase()==='get') return;
    input.value=today;
  });

  // Real-time sale calculations
  document.addEventListener('input', function(event) {
    const field = event.target;
    if (!field) return;
    
    const form = field.closest('form');
    if (!form) return;
    
    // Target only sale-related forms (checking for common fields)
    const qty = form.querySelector('input[name="quantity"]');
    const uprice = form.querySelector('input[name="unit_price"]');
    const total = form.querySelector('input[name="total"]');
    const paid = form.querySelector('input[name="amount_paid"]');
    const due = form.querySelector('input[name="balance_due"]');
    
    if (!qty || !uprice || !total) return;
    
    // Calculate total if quantity or unit_price changes
    if (field === qty || field === uprice) {
      const q = parseFloat(qty.value) || 0;
      const u = parseFloat(uprice.value) || 0;
      total.value = (q * u).toFixed(2);
    }
    
    // Calculate balance due if total or amount_paid changes
    if (paid && (field === qty || field === uprice || field === total || field === paid)) {
      const t = parseFloat(total.value) || 0;
      const p = parseFloat(paid.value) || 0;
      due.value = Math.max(0, t - p).toFixed(2);
    }
  });
  document.addEventListener('click', function(event) {
    const target = event.target.closest('[data-confirm]');
    if (!target) return;
    
    const message = target.getAttribute('data-confirm') || "Êtes-vous sûr de vouloir effectuer cette action ?";
    if (!confirm(message)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
})();





// --- tables.js ---
(function(){
  function queueGridTask(fn){
    if('requestAnimationFrame' in window){
      window.requestAnimationFrame(fn);
      return;
    }
    window.setTimeout(fn,0);
  }
  function hiddenPanel(el){return !!el.closest('[hidden]');}
  function cleanText(text){
    return (text||'').trim().replace(/\s+/g,' ');
  }
  function normalizeText(text){
    return cleanText(text).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
  }
  // Returns true when a server-side GET form precedes the table inside the same card.
  // Used ONLY to decide whether to add the local search bar — NOT to disable sorting.
  function externalFilter(table){
    const card=table.closest('.card');
    if(!card) return false;
    return Array.from(card.querySelectorAll('form')).some(function(form){
      return (form.method||'get').toLowerCase()==='get' && !!(form.compareDocumentPosition(table)&Node.DOCUMENT_POSITION_FOLLOWING);
    });
  }
  function columnKind(th,index,rows){
    const className=(th.className||'').toLowerCase();
    const label=normalizeText(th.textContent);
    const firstRow=rows.find(function(row){return !!row.cells[index];});
    const cellClass=firstRow&&firstRow.cells[index]?(firstRow.cells[index].className||'').toLowerCase():'';
    if(className.includes('col-date') || cellClass.includes('col-date') || /\b(date|cree|created|derniere)\b/.test(label)){
      return 'date';
    }
    if(
      className.includes('col-money') ||
      className.includes('col-balance') ||
      cellClass.includes('cell-num') ||
      cellClass.includes('col-money') ||
      cellClass.includes('col-balance') ||
      /(total|solde|reste|paye|versement|montant|prix|cout|qte|quantite|stock|jour|duree|vente|dette|creance|benefice|profit|chiffre|%|id)/.test(label)
    ){
      return 'number';
    }
    return 'text';
  }
  function parseDate(text){
    const clean=cleanText(text);
    if(!clean) return null;
    let match=clean.match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
    if(match){
      const date=new Date(+match[1],+match[2]-1,+match[3],+(match[4]||0),+(match[5]||0),+(match[6]||0));
      return isNaN(date.getTime())?null:date.getTime();
    }
    match=clean.match(/(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
    if(match){
      const year=match[3].length===2?2000+(+match[3]):+match[3];
      const date=new Date(year,+match[2]-1,+match[1],+(match[4]||0),+(match[5]||0),+(match[6]||0));
      return isNaN(date.getTime())?null:date.getTime();
    }
    const fallback=Date.parse(clean);
    return isNaN(fallback)?null:fallback;
  }
  function parseNumber(text){
    const clean=cleanText(text).replace(/\u00a0/g,' ');
    if(!clean || /^[-\u2013\u2014]$/.test(clean) || normalizeText(clean)==='ok') return null;
    const tokenMatch=clean.match(/[-+]?\d[\d\s.,]*/);
    if(!tokenMatch) return null;
    let token=tokenMatch[0].replace(/\s+/g,'');
    const comma=token.lastIndexOf(',');
    const dot=token.lastIndexOf('.');
    if(comma>-1 && dot>-1){
      if(comma>dot){
        token=token.replace(/\./g,'').replace(',','.');
      }else{
        token=token.replace(/,/g,'');
      }
    }else if(comma>-1){
      token=token.replace(',','.');
    }else if((token.match(/\./g)||[]).length>1){
      const last=token.lastIndexOf('.');
      token=token.slice(0,last).replace(/\./g,'')+'.'+token.slice(last+1);
    }
    const value=Number(token);
    return isNaN(value)?null:value;
  }
  function parseCell(cell,kind){
    const text=cell?(cell.getAttribute('data-sort-value')||cell.textContent):'';
    if(kind==='date') return parseDate(text);
    if(kind==='number') return parseNumber(text);
    return normalizeText(text);
  }
  function rowSortSequence(row){
    if(!row || row.dataset.sortSequence===undefined) return null;
    const value=Number(row.dataset.sortSequence);
    return isNaN(value)?null:value;
  }
  function compareValues(left,right,kind,direction){
    const leftMissing=left===null || left===undefined || left==='';
    const rightMissing=right===null || right===undefined || right==='';
    if(leftMissing && rightMissing) return 0;
    if(leftMissing) return 1;
    if(rightMissing) return -1;
    let cmp;
    if(kind==='text'){
      cmp=String(left).localeCompare(String(right),'fr',{numeric:true,sensitivity:'base'});
    }else{
      cmp=left>right?1:left<right?-1:0;
    }
    return direction==='asc'?cmp:-cmp;
  }
  function defaultDirection(kind){
    return kind==='text'?'asc':'desc';
  }
  function scrollSortedTableToStart(table){
    const shell=table.closest('.table-shell') || table.closest('.table-responsive') || table;
    const top=Math.max(0,shell.getBoundingClientRect().top+window.scrollY-76);
    const scroller=table.closest('.table-responsive');
    if(scroller) scroller.scrollLeft=0;
    window.scrollTo({top:top,behavior:'auto'});
  }
  function setupGrid(table){
    if(table.dataset.enhanced||table.classList.contains('no-grid')) return;
    table.dataset.enhanced='1';
    const tbody=table.tBodies[0]; if(!tbody) return;
    const rows=Array.from(tbody.querySelectorAll('tr')).filter(function(row){return !row.querySelector('td[colspan]');});
    rows.forEach(function(row,position){
      row.dataset.originalIndex=row.dataset.originalIndex||String(position);
      row.dataset.searchText=row.dataset.searchText||normalizeText(row.textContent);
    });
    const wrap=document.createElement('div');
    wrap.className='table-shell';
    // Only show local search bar when there is NO server-side GET form on the same card.
    // Column sorting is ALWAYS active regardless of this flag.
    const showSearch=!externalFilter(table);
    const bar=document.createElement('div');
    bar.className='table-search';
    bar.innerHTML='<input class="form-control form-control-sm" placeholder="Rechercher...">';
    const existing=table.parentElement&&table.parentElement.classList.contains('table-responsive')?table.parentElement:null;
    const scroller=existing||document.createElement('div');
    scroller.classList.add('table-scroll','table-responsive');
    table.classList.add('table-sticky','table-row-hover');
    if(existing){
      existing.parentNode.insertBefore(wrap,existing);
      if(showSearch) wrap.appendChild(bar);
      wrap.appendChild(existing);
    }else{
      table.parentNode.insertBefore(wrap,table);
      if(showSearch) wrap.appendChild(bar);
      wrap.appendChild(scroller);
      scroller.appendChild(table);
    }
    const input=showSearch?bar.querySelector('input'):null;
    
    // Sync local search bar with URL ?q= param
    if (input) {
      const urlParams = new URLSearchParams(window.location.search);
      const initialQ = urlParams.get('q') || '';
      if (initialQ) {
        input.value = initialQ;
      }
    }

    let currentRows=[...rows];
    function applyFilter(){
      const q=input?normalizeText(input.value):'';
      currentRows.forEach(function(row){row.style.display=!q||(row.dataset.searchText||'').includes(q)?'':'none';});
      
      // Update URL without reloading (only for local search bar)
      if (input && q !== (new URLSearchParams(window.location.search)).get('q')) {
        const url = new URL(window.location);
        if (q) url.searchParams.set('q', input.value);
        else url.searchParams.delete('q');
        window.history.replaceState({}, '', url);
      }
    }
    if(input) input.addEventListener('input',applyFilter);
    
    window.addEventListener('popstate', function() {
      if (input) {
        const urlParams = new URLSearchParams(window.location.search);
        input.value = urlParams.get('q') || '';
        applyFilter();
      }
    });

    // ── Column sort headers — ALWAYS activated, even on pages with external filters ──
    Array.from(table.querySelectorAll('thead th')).forEach(function(th,index){
      if(th.colSpan>1 || th.querySelector('a')) return;
      th.dataset.sortable='1';
      th.setAttribute('aria-sort','none');
      th.title='Trier';
      th.addEventListener('click',function(){
        const kind=columnKind(th,index,currentRows);
        const next=th.dataset.sortDir?(th.dataset.sortDir==='asc'?'desc':'asc'):defaultDirection(kind);
        table.querySelectorAll('thead th[data-sortable="1"]').forEach(function(header){
          delete header.dataset.sortDir;
          header.setAttribute('aria-sort','none');
        });
        th.dataset.sortDir=next;
        th.setAttribute('aria-sort',next==='asc'?'ascending':'descending');
        currentRows.sort(function(a,b){
          const av=parseCell(a.cells[index],kind);
          const bv=parseCell(b.cells[index],kind);
          const cmp=compareValues(av,bv,kind,next);
          if(cmp) return cmp;
          if(kind==='date'){
            const aSequence=rowSortSequence(a);
            const bSequence=rowSortSequence(b);
            if(aSequence!==null && bSequence!==null && aSequence!==bSequence){
              return next==='asc'?aSequence-bSequence:bSequence-aSequence;
            }
          }
          return Number(a.dataset.originalIndex||0)-Number(b.dataset.originalIndex||0);
        });
        currentRows.forEach(function(row){tbody.appendChild(row);});
        applyFilter();
        scrollSortedTableToStart(table);
      });
    });
    applyFilter();
  }
  function initDataGrids(root){
    (root||document).querySelectorAll('table.js-datagrid').forEach(function(table){
      if(table.dataset.enhanced||table.classList.contains('no-grid')||hiddenPanel(table)) return;
      queueGridTask(function(){setupGrid(table);});
    });
  }
  document.addEventListener('fab:panel-open',function(event){
    if(event.detail&&event.detail.panel) initDataGrids(event.detail.panel);
  });
  queueGridTask(function(){initDataGrids(document);});

})();



// --- notifications.js ---
(function(){
  const banner=document.getElementById('pwaBanner');
  const reloadBtn=document.getElementById('pwaReload');
  const dismissBtn=document.getElementById('pwaDismiss');
  let waitingWorker=null;
  function show(message){
    if(!banner) return;
    const text=document.getElementById('pwaBannerText');
    if(text&&message) text.textContent=message;
    banner.classList.add('show');
  }
  function hide(){if(banner) banner.classList.remove('show');}
  dismissBtn?.addEventListener('click',hide);
  reloadBtn?.addEventListener('click',function(){
    if(waitingWorker) waitingWorker.postMessage({type:'SKIP_WAITING'});
    else window.location.reload();
  });
  window.addEventListener('online',hide);
  window.addEventListener('offline',function(){show('Mode hors ligne detecte. Les pages recentes restent disponibles.');});
  if(!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('/static/sw.js').then(function(registration){
    if(registration.waiting){
      waitingWorker=registration.waiting;
      show('Une nouvelle version est prete. Recharge pour l appliquer.');
    }
    registration.addEventListener('updatefound',function(){
      const worker=registration.installing;
      if(!worker) return;
      worker.addEventListener('statechange',function(){
        if(worker.state==='installed'&&navigator.serviceWorker.controller){
          waitingWorker=worker;
          show('Une nouvelle version est prete. Recharge pour l appliquer.');
        }
      });
    });
    navigator.serviceWorker.addEventListener('controllerchange',function(){window.location.reload();});
  }).catch(function(){});
})();



// --- app.js ---
// Context menu and mobile-shell helpers that are not part of the split modules.
(function(){
  try{
    const isAndroid=/Android/i.test(navigator.userAgent);
    const mobileShell=localStorage.getItem('fab_mobile_shell')==='1';
    const isLocalHost=window.location.hostname==='localhost'||window.location.hostname==='127.0.0.1';
    if(isAndroid&&mobileShell&&!isLocalHost){
      document.documentElement.classList.add('fab-mobile-shell');
      if(!document.querySelector('.fab-mobile-return')){
        const back=document.createElement('a');
        back.className='fab-mobile-return';
        back.href='http://localhost/?setup=1';
        back.innerHTML='<i class="bi bi-phone"></i><span>Config mobile</span>';
        document.body.appendChild(back);
      }
    }
  }catch(e){}
})();

(function(){
  const menu=document.getElementById('contextMenu');
  if(!menu) return;
  const titleEl=document.getElementById('contextTitle');
  const viewLink=document.getElementById('contextView');
  const printLink=document.getElementById('contextPrint');
  const editLink=document.getElementById('contextEdit');
  const dividerEl=document.getElementById('contextDivider');
  const deleteForm=document.getElementById('contextDeleteForm');
  const deleteBtn=document.getElementById('contextDelete');

  function absoluteUrl(url){
    if(window.fabApi&&typeof window.fabApi.absoluteUrl==='function') return window.fabApi.absoluteUrl(url);
    if(!url) return url;
    try{
      if(url.startsWith('/')) return window.location.origin+url;
      const parsed=new URL(url);
      if(parsed.host!==window.location.host){
        parsed.hostname=window.location.hostname;
        parsed.port=window.location.port;
        parsed.protocol=window.location.protocol;
      }
      return parsed.toString();
    }catch(e){
      return url;
    }
  }

  function hide(){
    menu.style.display='none';
  }

  function show(x,y,target,options){
    const secondaryOnly=!!(options&&options.secondaryOnly);
    const editUrl=target.dataset.editUrl||'';
    const editAction=target.dataset.editAction||'';
    const deleteUrl=target.dataset.deleteUrl||'';
    const printUrl=absoluteUrl(target.dataset.printUrl||'');
    const deleteLabel=target.dataset.deleteLabel||'cet element';
    const label=target.dataset.label||'';
    const hasEdit=!!(editUrl||editAction);
    if(secondaryOnly&&!hasEdit&&!deleteUrl) return;

    if(titleEl) titleEl.textContent=label||'Actions';
    if(viewLink){
      viewLink.style.display=(printUrl&&!secondaryOnly)?'flex':'none';
      if(printUrl) viewLink.href=printUrl;
    }
    if(printLink){
      printLink.style.display=(printUrl&&!secondaryOnly)?'flex':'none';
      if(printUrl){
        printLink.href=printUrl;
        const isAndroidWebView=/Android/i.test(navigator.userAgent)&&window.location.hostname==='127.0.0.1';
        printLink.target=isAndroidWebView?'_self':'_blank';
      }
    }
    if(editLink){
      editLink.style.display=hasEdit?'flex':'none';
      editLink.onclick=null;
      if(editUrl){
        editLink.href=editUrl;
      }else if(editAction){
        editLink.href='#';
        editLink.onclick=function(event){
          event.preventDefault();
          hide();
          const handler=window[editAction];
          if(typeof handler==='function') handler(target);
        };
      }
    }
    if(dividerEl) dividerEl.style.display=(hasEdit&&deleteUrl)?'block':'none';
    if(deleteForm) deleteForm.style.display=deleteUrl?'block':'none';
    if(deleteBtn&&deleteUrl){
      deleteForm.action=deleteUrl;
      deleteBtn.style.display='flex';
      deleteBtn.onclick=function(event){
        if(!confirm('Supprimer '+deleteLabel+' ?')) event.preventDefault();
      };
    }

    menu.style.display='block';
    const menuWidth=menu.offsetWidth;
    const menuHeight=menu.offsetHeight;
    menu.style.left=Math.max(4,Math.min(x,window.innerWidth-menuWidth-8))+'px';
    menu.style.top=Math.max(4,Math.min(y,window.innerHeight-menuHeight-8))+'px';
  }

  document.addEventListener('contextmenu',function(event){
    const target=event.target.closest('.context-target');
    if(!target){
      hide();
      return;
    }
    event.preventDefault();
    show(event.clientX,event.clientY,target);
  });

  document.addEventListener('dblclick',function(event){
    const target=event.target.closest('.context-target');
    if(!target||event.target.closest('.col-actions')) return;
    event.preventDefault();
    show(event.clientX,event.clientY,target,{secondaryOnly:true});
  });

  let pressTimer;
  document.addEventListener('touchstart',function(event){
    const target=event.target.closest('.context-target');
    if(!target) return;
    pressTimer=setTimeout(function(){
      const touch=event.touches[0];
      show(touch.clientX,touch.clientY,target);
    },500);
  },{passive:true});
  document.addEventListener('touchend',function(){clearTimeout(pressTimer);},{passive:true});
  document.addEventListener('touchmove',function(){clearTimeout(pressTimer);},{passive:true});
  document.addEventListener('click',function(event){if(!event.target.closest('.context-menu')) hide();});
  window.addEventListener('scroll',hide,true);
  window.addEventListener('resize',hide);
})();


