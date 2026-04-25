// ── CSRF auto-inject ──
(function(){
  const token=document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')||'';
  if(!token) return;
  document.querySelectorAll('form[method="post"],form[method="POST"]').forEach(f=>{
    if(f.querySelector('input[name="csrf_token"]')) return;
    const i=document.createElement('input');i.type='hidden';i.name='csrf_token';i.value=token;f.appendChild(i);
  });
  window.fabCsrfToken=token;
})();

// ── Submit spinner ──
document.addEventListener('submit',function(e){
  const f=e.target; if(f.dataset.noSpinner) return;
  if((f.method||'').toLowerCase()==='get') return;
  const btn=f.querySelector('button[type="submit"],button:not([type])');
  if(!btn||btn.dataset.spinning) return;
  btn.dataset.spinning='1'; btn.disabled=true;
  const orig=btn.innerHTML;
  btn.innerHTML='<span class="spinner-border spinner-border-sm me-1"></span>En cours…';
  setTimeout(()=>{btn.disabled=false;btn.innerHTML=orig;delete btn.dataset.spinning;},8000);
});

// ── Drawer ──
(function(){
  const btn=document.getElementById('drawerBtn');
  const close=document.getElementById('drawerClose');
  const drawer=document.getElementById('navDrawer');
  const overlay=document.getElementById('navOverlay');
  const toolsToggle=document.getElementById('drawerToolsToggle');
  const toolsGroup=toolsToggle?.closest('.drawer-group');
  if(!btn) return;
  let previousOverflow='';
  function open(){
    previousOverflow=document.body.style.overflow;
    drawer.classList.add('open');
    overlay.classList.add('open');
    document.body.style.overflow='hidden';
  }
  function shut(){
    drawer.classList.remove('open');
    overlay.classList.remove('open');
    document.body.style.overflow=previousOverflow;
  }
  function setToolsOpen(isOpen){
    if(!toolsGroup || !toolsToggle) return;
    toolsGroup.classList.toggle('open', isOpen);
    toolsToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }
  btn.addEventListener('click',open);
  close.addEventListener('click',shut);
  overlay.addEventListener('click',shut);
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&drawer.classList.contains('open')) shut();
  });
  if(toolsToggle && toolsGroup){
    toolsToggle.addEventListener('click',function(e){
      e.preventDefault();
      e.stopPropagation();
      setToolsOpen(!toolsGroup.classList.contains('open'));
    });
  }
  drawer.querySelectorAll('a').forEach(a=>a.addEventListener('click',shut));
})();

// ── Fix URL host (remote access fix) ──
(function(){
  document.querySelectorAll('[data-fab-switch-root]').forEach(function(root){
    const buttons=Array.from(root.querySelectorAll('[data-fab-switch-target]'));
    const panels=buttons
      .map(function(btn){ return document.getElementById(btn.getAttribute('data-fab-switch-target')); })
      .filter(Boolean);
    const placeholderId=root.getAttribute('data-fab-switch-placeholder');
    const placeholder=placeholderId ? document.getElementById(placeholderId) : null;

    function resetPanels(showPlaceholder){
      buttons.forEach(function(btn){
        btn.classList.remove('is-active');
        btn.setAttribute('aria-pressed','false');
      });
      panels.forEach(function(panel){
        panel.hidden=true;
      });
      if(placeholder){
        placeholder.hidden=!showPlaceholder;
      }
    }

    buttons.forEach(function(btn){
      btn.addEventListener('click',function(){
        const targetId=btn.getAttribute('data-fab-switch-target');
        const panel=document.getElementById(targetId);
        const isActive=btn.classList.contains('is-active');
        resetPanels(isActive);
        if(!panel || isActive) return;
        btn.classList.add('is-active');
        btn.setAttribute('aria-pressed','true');
        panel.hidden=false;
        if(placeholder){
          placeholder.hidden=true;
        }
        requestAnimationFrame(function(){
          document.dispatchEvent(new CustomEvent('fab:panel-open',{detail:{panel:panel}}));
          window.dispatchEvent(new Event('resize'));
        });
      });
    });

    resetPanels(true);
  });
})();

function fixUrl(url){
  if(!url) return url;
  try{
    if(url.startsWith('/')) return window.location.origin+url;
    const u=new URL(url);
    if(u.host!==window.location.host){u.hostname=window.location.hostname;u.port=window.location.port;u.protocol=window.location.protocol;}
    return u.toString();
  }catch(e){return url;}
}

// ── Context Menu ──
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
  function hide(){menu.style.display='none';}
  function show(x,y,t){
    const eu=t.dataset.editUrl||'',du=t.dataset.deleteUrl||'',pu=fixUrl(t.dataset.printUrl||'');
    const dl=t.dataset.deleteLabel||'cet élément',lbl=t.dataset.label||'';
    if(titleEl) titleEl.textContent=lbl||'Actions';
    if(viewLink){viewLink.style.display=pu?'flex':'none';if(pu)viewLink.href=pu;}
    if(printLink){printLink.style.display=pu?'flex':'none';if(pu){printLink.href=pu;const isAndroidWebView=(/Android/i.test(navigator.userAgent)&&window.location.hostname==='127.0.0.1');printLink.target=isAndroidWebView?'_self':'_blank';}}
    if(editLink){editLink.style.display=eu?'flex':'none';if(eu)editLink.href=eu;}
    if(dividerEl) dividerEl.style.display=((eu||pu)&&du)?'block':'none';
    if(deleteForm) deleteForm.style.display=du?'block':'none';
    if(deleteBtn&&du){deleteForm.action=du;deleteBtn.style.display='flex';deleteBtn.onclick=e=>{if(!confirm('Supprimer '+dl+' ?'))e.preventDefault();};}
    menu.style.display='block';
    const mw=menu.offsetWidth,mh=menu.offsetHeight;
    menu.style.left=Math.max(4,Math.min(x,window.innerWidth-mw-8))+'px';
    menu.style.top=Math.max(4,Math.min(y,window.innerHeight-mh-8))+'px';
  }
  document.addEventListener('contextmenu',function(e){
    const t=e.target.closest('.context-target');
    if(!t){hide();return;} e.preventDefault(); show(e.clientX,e.clientY,t);
  });
  document.addEventListener('dblclick',function(e){
    const t=e.target.closest('.context-target'); if(!t) return;
    const pu=fixUrl(t.dataset.printUrl); if(pu){ if(/Android/i.test(navigator.userAgent)&&window.location.hostname==='127.0.0.1'){window.location.href=pu;}else{window.open(pu,'_blank');} }
  });
  let pt;
  document.addEventListener('touchstart',function(e){
    const t=e.target.closest('.context-target'); if(!t) return;
    pt=setTimeout(()=>{const tc=e.touches[0];show(tc.clientX,tc.clientY,t);},500);
  },{passive:true});
  document.addEventListener('touchend',()=>clearTimeout(pt),{passive:true});
  document.addEventListener('touchmove',()=>clearTimeout(pt),{passive:true});
  document.addEventListener('click',function(e){if(!e.target.closest('.context-menu'))hide();});
  window.addEventListener('scroll',hide,true);
  window.addEventListener('resize',hide);
})();

// ── Theme + DataGrid ──
(function(){
  try{
    const params=new URLSearchParams(window.location.search);
    if(params.get('mobile_shell')==='1'){
      localStorage.setItem('fab_mobile_shell','1');
    }else if(params.get('mobile_shell')==='0'){
      localStorage.removeItem('fab_mobile_shell');
    }
  }catch(e){}
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
  const themeColors={
    light:'#1a2235',
    slate:'#475569',
    sand:'#7c5a34',
    forest:'#1f5f46',
    ocean:'#0f5f89',
    rose:'#a33a50',
    violet:'#6d4cc2',
    midnight:'#0a0a14',
    coffee:'#2c1a0e',
    mint:'#166534',
    gold:'#92620a',
    dark:'#0d1117'
  };
  function applyTheme(theme,opts){
    const name=themeColors[theme]?theme:'light';
    const animate=opts&&opts.animate;
    if(animate) document.documentElement.classList.add('theme-changing');
    document.documentElement.setAttribute('data-theme',name);
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',themeColors[name]);
    window.clearTimeout(window.fabThemeTimer);
    if(animate){
      window.fabThemeTimer=window.setTimeout(function(){
        document.documentElement.classList.remove('theme-changing');
      },280);
    }
  }
  const saved=localStorage.getItem('fab_theme')||'light';
  applyTheme(saved);
  document.querySelectorAll('.js-theme').forEach(b=>{
    b.addEventListener('click',function(){
      const t=this.dataset.theme;
      applyTheme(t,{animate:true});
      localStorage.setItem('fab_theme',t);
    });
  });
  // Default date inputs
  const today=(new Date()).toISOString().slice(0,10);
  function shouldAutoFillDate(inp){
    if(inp.value||inp.dataset.noAutoDate==='1') return false;
    const form=inp.closest('form');
    if(form&&(form.method||'').toLowerCase()==='get') return false;
    return true;
  }
  document.querySelectorAll('input[type="date"]').forEach(inp=>{if(shouldAutoFillDate(inp))inp.value=today;});

  // DataGrid with search + sort
  function queueGridTask(fn){
    if('requestIdleCallback' in window){
      window.requestIdleCallback(fn,{timeout:250});
      return;
    }
    window.setTimeout(fn,0);
  }
  function isInsideHiddenPanel(el){
    return !!el.closest('[hidden]');
  }
  function hasExternalFilter(table){
    const card=table.closest('.card');
    if(!card) return false;
    return Array.from(card.querySelectorAll('form')).some(function(form){
      const method=(form.method||'get').toLowerCase();
      if(method!=='get') return false;
      return !!(form.compareDocumentPosition(table)&Node.DOCUMENT_POSITION_FOLLOWING);
    });
  }
  function parseCellValue(text){
    const clean=(text||'').trim().replace(/\s+/g,' ');
    const num=Number(clean.replace(/[\s,]/g,'').replace(/DA/gi,'').replace('%',''));
    if(!isNaN(num)&&/\d/.test(clean)) return {type:'number',value:num};
    const d=Date.parse(clean);
    if(!isNaN(d)&&/\d{4}-\d{2}-\d{2}/.test(clean)) return {type:'date',value:d};
    return {type:'text',value:clean.toLowerCase()};
  }
  function setupGrid(table){
    if(table.dataset.enhanced||table.classList.contains('no-grid')) return;
    table.dataset.enhanced='1';
    const tbody=table.tBodies[0]; if(!tbody) return;
    const baseRows=Array.from(tbody.querySelectorAll('tr')).filter(r=>!r.querySelector('td[colspan]'));
    baseRows.forEach(function(row){
      if(!row.dataset.searchText){
        row.dataset.searchText=(row.innerText||'').toLowerCase();
      }
    });
    const wrap=document.createElement('div'); wrap.className='table-shell';
    const showSearch=!hasExternalFilter(table);
    const bar=document.createElement('div'); bar.className='table-search';
    bar.innerHTML='<input class="form-control form-control-sm" placeholder="Rechercher...">';
    const existingScroll=table.parentElement&&table.parentElement.classList.contains('table-responsive')?table.parentElement:null;
    const scrollDiv=existingScroll||document.createElement('div');
    scrollDiv.classList.add('table-scroll','table-responsive');
    table.classList.add('table-sticky','table-row-hover');
    if(existingScroll){
      existingScroll.parentNode.insertBefore(wrap,existingScroll);
      if(showSearch) wrap.appendChild(bar);
      wrap.appendChild(existingScroll);
    }else{
      table.parentNode.insertBefore(wrap,table);
      if(showSearch) wrap.appendChild(bar);
      wrap.appendChild(scrollDiv);
      scrollDiv.appendChild(table);
    }
    const inp=showSearch?bar.querySelector('input'):null;
    let currentRows=[...baseRows];
    function applyFilter(){
      const q=inp?(inp.value||'').toLowerCase():'';
      currentRows.forEach(function(r){
        const haystack=r.dataset.searchText||'';
        r.style.display=!q||haystack.includes(q)?'':'none';
      });
    }
    if(inp) inp.addEventListener('input',applyFilter);
    Array.from(table.querySelectorAll('thead th')).forEach((th,idx)=>{
      if(th.colSpan>1) return;
      th.dataset.sortable='1';
      th.setAttribute('aria-sort','none');
      th.title='Trier';
      th.addEventListener('click',()=>{
        const next=th.dataset.sortDir==='asc'?'desc':'asc';
        table.querySelectorAll('thead th[data-sortable="1"]').forEach(h=>{
          delete h.dataset.sortDir;
          h.setAttribute('aria-sort','none');
        });
        th.dataset.sortDir=next;
        th.setAttribute('aria-sort',next==='asc'?'ascending':'descending');
        currentRows.sort((a,b)=>{
          const av=parseCellValue(a.cells[idx]?.innerText||'');
          const bv=parseCellValue(b.cells[idx]?.innerText||'');
          const cmp=av.value>bv.value?1:av.value<bv.value?-1:0;
          return next==='asc'?cmp:-cmp;
        });
        currentRows.forEach(r=>tbody.appendChild(r));
        applyFilter();
      });
    });
    applyFilter();
  }
  function initDataGrids(root){
    (root||document).querySelectorAll('table.js-datagrid').forEach(function(table){
      if(table.dataset.enhanced||table.classList.contains('no-grid')||isInsideHiddenPanel(table)) return;
      queueGridTask(function(){ setupGrid(table); });
    });
  }
  document.addEventListener('fab:panel-open',function(ev){
    const panel=ev.detail&&ev.detail.panel;
    if(panel) initDataGrids(panel);
  });
  queueGridTask(function(){ initDataGrids(document); });
})();

// ── Invoice opener ──
function openInvoice(e, url) {
  if (e) e.preventDefault();
  var dest = url || (e && e.currentTarget && e.currentTarget.href);
  if (!dest || dest === '#' || dest === window.location.href + '#') return;
  // Ensure absolute URL with correct host
  if (dest.indexOf('/') === 0) dest = window.location.protocol + '//' + window.location.host + dest;
  window.location.href = dest;
}

(function(){
  const banner=document.getElementById('pwaBanner');
  const reloadBtn=document.getElementById('pwaReload');
  const dismissBtn=document.getElementById('pwaDismiss');
  let waitingWorker=null;
  function showBanner(message){
    if(!banner) return;
    const text=document.getElementById('pwaBannerText');
    if(text && message) text.textContent=message;
    banner.classList.add('show');
  }
  function hideBanner(){
    if(banner) banner.classList.remove('show');
  }
  dismissBtn?.addEventListener('click',hideBanner);
  reloadBtn?.addEventListener('click',function(){
    if(waitingWorker){waitingWorker.postMessage({type:'SKIP_WAITING'});}
    else{window.location.reload();}
  });
  window.addEventListener('online',function(){hideBanner();});
  window.addEventListener('offline',function(){showBanner('Mode hors ligne detecte. Les pages recentes restent disponibles.');});
  if(!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('/static/sw.js').then(function(registration){
    if(registration.waiting){
      waitingWorker=registration.waiting;
      showBanner('Une nouvelle version est prete. Recharge pour l appliquer.');
    }
    registration.addEventListener('updatefound',function(){
      const newWorker=registration.installing;
      if(!newWorker) return;
      newWorker.addEventListener('statechange',function(){
        if(newWorker.state==='installed' && navigator.serviceWorker.controller){
          waitingWorker=newWorker;
          showBanner('Une nouvelle version est prete. Recharge pour l appliquer.');
        }
      });
    });
    navigator.serviceWorker.addEventListener('controllerchange',function(){
      window.location.reload();
    });
  }).catch(function(){});
})();
