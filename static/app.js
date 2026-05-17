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
