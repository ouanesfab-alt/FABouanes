export function getCsrfToken() {
  return window.fabCsrfToken || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

export function absoluteUrl(url) {
  if (!url) return url;
  try {
    if (url.startsWith('/')) return window.location.origin + url;
    const parsed = new URL(url);
    if (parsed.host !== window.location.host) {
      parsed.hostname = window.location.hostname;
      parsed.port = window.location.port;
      parsed.protocol = window.location.protocol;
    }
    return parsed.toString();
  } catch (e) {
    return url;
  }
}

export function headers(extra) {
  return Object.assign({ 'X-CSRFToken': getCsrfToken(), 'Content-Type': 'application/json' }, extra || {});
}

export function showToast(message, type = 'info', options = {}) {
  const normType = type === 'error' ? 'danger' : type;

  // Play dynamic synthesized sound feedback
  if (normType === 'success' && typeof window.playSuccessSound === 'function') {
    window.playSuccessSound();
  } else if (normType === 'danger' && typeof window.playErrorSound === 'function') {
    window.playErrorSound();
  } else if (normType === 'warning' && typeof window.playClickSound === 'function') {
    window.playClickSound('warning');
  }

  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container position-fixed top-0 end-0 p-4 toast-container-app';
    container.style.marginTop = '60px';
    container.style.zIndex = '99999';
    container.setAttribute('aria-live', 'polite');
    container.setAttribute('aria-atomic', 'true');
    document.body.appendChild(container);
  }

  const iconMap = {
    success: 'check-circle-fill',
    danger: 'exclamation-triangle-fill',
    warning: 'exclamation-circle-fill',
    info: 'info-circle-fill'
  };
  const accentMap = {
    success: '#25D366',
    danger: '#ef4444',
    warning: '#f59e0b',
    info: '#007AFF'
  };

  const icon = iconMap[normType] || 'info-circle-fill';
  const accent = accentMap[normType] || '#007AFF';
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

  const toastEl = document.createElement('div');
  toastEl.className = 'toast border-0 mb-2 shadow-lg flash-toast';
  toastEl.setAttribute('role', 'alert');
  toastEl.setAttribute('aria-live', 'assertive');
  toastEl.setAttribute('aria-atomic', 'true');
  toastEl.dataset.accent = accent;

  toastEl.style.borderRadius = '10px';
  toastEl.style.backgroundColor = isDark ? '#1e2a30' : '#f0f2f5';
  toastEl.style.color = isDark ? '#e9edef' : '#111b21';
  toastEl.style.borderLeft = `4px solid ${accent}`;
  toastEl.style.minWidth = '280px';
  toastEl.style.maxWidth = '380px';
  if (!isDark) toastEl.style.boxShadow = '0 6px 24px rgba(0,0,0,0.12)';

  const autoHide = options.autoHide !== false;
  const duration = options.duration || 4500;

  toastEl.innerHTML = `
    <div class="toast-body p-3">
      <div class="d-flex align-items-center gap-2">
        <i class="bi bi-${icon} flex-shrink-0" style="color:${accent};font-size:1rem;"></i>
        <div class="fw-medium flex-grow-1" style="font-size:0.9rem;line-height:1.4;">${message}</div>
        <button type="button" class="btn-close ${isDark ? 'btn-close-white' : ''} flex-shrink-0 flash-toast-close ms-auto"
          data-bs-dismiss="toast" aria-label="Fermer" style="font-size:0.7em;opacity:0.75;"></button>
      </div>
    </div>
  `;

  container.appendChild(toastEl);

  if (window.bootstrap && window.bootstrap.Toast) {
    const bsToast = new window.bootstrap.Toast(toastEl, {
      autohide: autoHide,
      delay: duration
    });
    bsToast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
  } else {
    toastEl.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    toastEl.style.opacity = '1';
    if (autoHide) {
      setTimeout(() => {
        toastEl.style.opacity = '0';
        setTimeout(() => toastEl.remove(), 300);
      }, duration);
    }
    const closeBtn = toastEl.querySelector('.flash-toast-close');
    if (closeBtn) closeBtn.onclick = () => toastEl.remove();
  }
}

export async function fabFetch(url, options = {}) {
  const finalUrl = absoluteUrl(url);
  const defaultHeaders = {
    'X-CSRFToken': getCsrfToken(),
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  };

  options.headers = Object.assign(defaultHeaders, options.headers || {});
  
  const timeout = options.timeout || 30000;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  options.signal = controller.signal;

  try {
    let response = await fetch(finalUrl, options);
    clearTimeout(id);

    if (response.status === 401) {
      window.location.href = '/login?expired=1';
      return;
    }

    if (response.status === 429) {
      showToast("Trop de requêtes. Veuillez patienter.", "warning");
      throw new Error("Trop de requêtes (429)");
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMsg = errorData.error?.message || `Erreur serveur (${response.status})`;
      showToast(errorMsg, "error");
      throw new Error(errorMsg);
    }

    return response;
  } catch (error) {
    clearTimeout(id);
    if (error.name === 'AbortError') {
      const timeoutMsg = "La requête a expiré (timeout).";
      showToast(timeoutMsg, "error");
      throw new Error(timeoutMsg);
    }
    throw error;
  }
}

export function initApiModule() {
  window.fabApi = {
    get csrfToken() { return getCsrfToken(); },
    getCsrfToken: getCsrfToken,
    absoluteUrl: absoluteUrl,
    headers: headers,
    fetch: fabFetch,
    showToast: showToast
  };
  window.fixUrl = window.fixUrl || absoluteUrl;
  window.fabFetch = window.fabFetch || fabFetch;
  window.showToast = showToast;
  window.fabToast = showToast;
}
