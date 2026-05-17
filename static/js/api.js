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
