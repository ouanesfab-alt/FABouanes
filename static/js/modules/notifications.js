export function initNotificationsModule() {
  const banner = document.getElementById('pwaBanner');
  const reloadBtn = document.getElementById('pwaReload');
  const dismissBtn = document.getElementById('pwaDismiss');
  let waitingWorker = null;
  
  function show(message) {
    if (!banner) return;
    const text = document.getElementById('pwaBannerText');
    if (text && message) text.textContent = message;
    banner.classList.add('show');
  }
  
  function hide() { if (banner) banner.classList.remove('show'); }
  
  dismissBtn?.addEventListener('click', hide);
  reloadBtn?.addEventListener('click', function () {
    if (waitingWorker) waitingWorker.postMessage({ type: 'SKIP_WAITING' });
    else window.location.reload();
  });
  
  window.addEventListener('online', hide);
  window.addEventListener('offline', function () {
    show('Mode hors ligne détecté. Les pages récentes restent disponibles.');
  });
  
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('/sw.js').then(function (registration) {
    if (registration.waiting) {
      waitingWorker = registration.waiting;
      show('Une nouvelle version est prête. Recharge pour l\'appliquer.');
    }
    registration.addEventListener('updatefound', function () {
      const worker = registration.installing;
      if (!worker) return;
      worker.addEventListener('statechange', function () {
        if (worker.state === 'installed' && navigator.serviceWorker.controller) {
          waitingWorker = worker;
          show('Une nouvelle version est prête. Recharge pour l\'appliquer.');
        }
      });
    });
    navigator.serviceWorker.addEventListener('controllerchange', function () { window.location.reload(); });
  }).catch(function () {});
}
