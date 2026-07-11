const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

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
  return Object.assign({ 'X-CSRFToken': token, 'Content-Type': 'application/json' }, extra || {});
}

export function showToast(message, type = 'info') {
  let container = document.getElementById('fab-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'fab-toast-container';
    container.style.position = 'fixed';
    container.style.bottom = '20px';
    container.style.right = '20px';
    container.style.zIndex = '99999';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast-message toast-${type}`;
  toast.style.padding = '12px 20px';
  toast.style.borderRadius = '8px';
  toast.style.color = '#fff';
  toast.style.fontFamily = 'system-ui, -apple-system, sans-serif';
  toast.style.fontSize = '14px';
  toast.style.fontWeight = '500';
  toast.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
  toast.style.opacity = '0';
  toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
  toast.style.transform = 'translateY(20px)';
  
  let bgColor = '#333';
  if (type === 'error') bgColor = '#dc3545';
  else if (type === 'warning') bgColor = '#ffc107';
  else if (type === 'success') bgColor = '#198754';
  else if (type === 'info') bgColor = '#0dcaf0';
  toast.style.backgroundColor = bgColor;
  if (type === 'warning') toast.style.color = '#000';

  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  }, 10);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-20px)';
    setTimeout(() => {
      toast.remove();
      if (container.children.length === 0) {
        container.remove();
      }
    }, 300);
  }, 5000);
}

export async function fabFetch(url, options = {}) {
  const finalUrl = absoluteUrl(url);
  const defaultHeaders = {
    'X-CSRFToken': token,
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
    csrfToken: token,
    absoluteUrl: absoluteUrl,
    headers: headers,
    fetch: fabFetch,
    showToast: showToast
  };
  window.fixUrl = window.fixUrl || absoluteUrl;
  window.fabFetch = window.fabFetch || fabFetch;
}
