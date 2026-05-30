export function initMobileShellModule() {
  try {
    const isAndroid = /Android/i.test(navigator.userAgent);
    const mobileShell = localStorage.getItem('fab_mobile_shell') === '1';
    const isLocalHost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (isAndroid && mobileShell && !isLocalHost) {
      document.documentElement.classList.add('fab-mobile-shell');
      if (!document.querySelector('.fab-mobile-return')) {
        const back = document.createElement('a');
        back.className = 'fab-mobile-return';
        back.href = 'http://localhost/?setup=1';
        back.innerHTML = '<i class="bi bi-phone"></i><span>Config mobile</span>';
        document.body.appendChild(back);
      }
    }
  } catch (e) {}
}
