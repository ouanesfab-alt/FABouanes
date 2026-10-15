let _formsListenersBound = false;

function bindFormEventListeners() {
  if (_formsListenersBound) return;
  _formsListenersBound = true;

  document.addEventListener('submit', function (event) {
    const form = event.target;
    if (!form || form.dataset.noSpinner || form.hasAttribute('data-no-spinner') || form.target === '_blank') return;
    if ((form.method || '').toLowerCase() === 'get') return;

    if (form.dataset.submitting === 'true') {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    form.dataset.submitting = 'true';
    
    const button = form.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
    if (!button || button.classList.contains('is-loading')) return;
    
    button.classList.add('is-loading', 'disabled');
    const originalHTML = button.innerHTML;

    button.setAttribute('data-original-html', originalHTML);
    
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>' + originalHTML;
    
    setTimeout(() => {
      button.disabled = true;
    }, 0);
    
    setTimeout(() => {
      if (button.classList.contains('is-loading')) {
        button.classList.remove('is-loading', 'disabled');
        button.disabled = false;
        button.innerHTML = originalHTML;
        form.dataset.submitting = 'false';
      }
    }, 8000);

  });

  document.addEventListener('input', function (event) {
    const field = event.target;
    if (!field) return;
    
    const form = field.closest('form');
    if (!form) return;
    
    const qty = form.querySelector('input[name="quantity"]');
    const uprice = form.querySelector('input[name="unit_price"]');
    const total = form.querySelector('input[name="total"]');
    const paid = form.querySelector('input[name="amount_paid"]');
    const due = form.querySelector('input[name="balance_due"]');
    
    if (!qty || !uprice || !total) return;
    
    if (field === qty || field === uprice) {
      const q = parseFloat(qty.value) || 0;
      const u = parseFloat(uprice.value) || 0;
      total.value = (q * u).toFixed(2);
    }
    
    if (paid && (field === qty || field === uprice || field === total || field === paid)) {
      const t = parseFloat(total.value) || 0;
      const p = parseFloat(paid.value) || 0;
      due.value = Math.max(0, t - p).toFixed(2);
    }

    // Dynamic credit badge update on total change
    const clientSelect = form.querySelector('select[name="client_id"]');
    if (clientSelect) {
      updateClientCreditStatus(clientSelect);
    }
  });

  document.addEventListener('change', function (event) {
    const target = event.target;
    if (!target) return;
    if (target.matches('select[name="client_id"]') || target.matches('select[name="sale_type"]') || target.id === 'clientSelect' || target.id === 'saleTypeSelect') {
      const form = target.closest('form') || document;
      const clientSelect = form.querySelector('select[name="client_id"]') || document.getElementById('clientSelect');
      if (clientSelect) updateClientCreditStatus(clientSelect);
    }
  });

  document.addEventListener('click', function (event) {
    const target = event.target.closest('[data-confirm]');
    if (!target) return;
    
    const message = target.getAttribute('data-confirm') || "Êtes-vous sûr de vouloir effectuer cette action ?";
    if (!confirm(message)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  bindCounterKeyboardShortcuts();
}

export function updateClientCreditStatus(clientSelectEl) {
  if (!clientSelectEl) return;
  const form = clientSelectEl.closest('form') || document;
  const badge = form.querySelector('.client-credit-badge') 
    || document.getElementById('clientCreditBadge')
    || document.getElementById('saleEditClientCreditBadge')
    || document.getElementById('paymentClientCreditBadge')
    || document.getElementById('paymentEditClientCreditBadge');
  if (!badge) return;

  const opt = clientSelectEl.selectedOptions ? clientSelectEl.selectedOptions[0] : null;
  if (!opt || !opt.value) {
    badge.style.display = 'none';
    badge.innerHTML = '';
    return;
  }

  const balance = parseFloat(opt.dataset.balance || '0');
  const limitStr = opt.dataset.creditLimit;
  const limit = limitStr && !isNaN(parseFloat(limitStr)) ? parseFloat(limitStr) : null;

  const totalEl = form.querySelector('#saleDocumentTotal') || form.querySelector('input[name="total"]');
  let currentSaleTotal = 0;
  if (totalEl) {
    const rawTxt = totalEl.value || totalEl.textContent || '0';
    currentSaleTotal = parseFloat(rawTxt.replace(/[^\d.,]/g, '').replace(',', '.')) || 0;
  }

  const saleTypeEl = form.querySelector('select[name="sale_type"]') || document.getElementById('saleTypeSelect') || document.getElementById('saleEditTypeSelect');
  const isCredit = saleTypeEl ? (saleTypeEl.value === 'credit' || saleTypeEl.value === 'dette') : true;

  const newProjected = balance + (isCredit ? currentSaleTotal : 0);

  badge.style.display = 'block';

  if (limit !== null && isCredit && newProjected > limit) {
    badge.className = 'client-credit-badge alert alert-danger p-2 mt-2 mb-0 small';
    badge.innerHTML = `
      <div class="fw-bold mb-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>Plafond de crédit dépassé !</div>
      <div>Encours actuel : <strong>${balance.toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</strong> + Vente : <strong>${currentSaleTotal.toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</strong></div>
      <div>Nouveau solde : <span class="text-danger fw-bold">${newProjected.toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</span> &gt; Plafond : <strong>${limit.toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</strong></div>
      <div class="form-check mt-2 pt-1 border-top border-danger-subtle">
        <input class="form-check-input" type="checkbox" name="allow_overlimit" id="allowOverlimitCheck" value="1">
        <label class="form-check-label text-dark fw-medium" for="allowOverlimitCheck">Forcer l'autorisation de crédit exceptionnel</label>
      </div>
    `;
  } else if (limit !== null) {
    const remaining = Math.max(0, limit - newProjected);
    const isWarning = limit > 0 && (newProjected / limit) >= 0.8;
    const alertClass = isWarning ? 'alert-warning' : 'alert-info';
    badge.className = `client-credit-badge alert ${alertClass} p-2 mt-2 mb-0 small`;
    badge.innerHTML = `
      <div class="d-flex justify-content-between align-items-center">
        <span><i class="bi bi-shield-check me-1"></i>Encours : <strong>${balance.toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</strong></span>
        <span>Plafond : <strong>${limit.toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</strong></span>
      </div>
      <div class="text-muted mt-1">Crédit disponible : <strong class="text-success">${remaining.toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</strong></div>
    `;
  } else if (balance > 0) {
    badge.className = 'client-credit-badge alert alert-warning p-2 mt-2 mb-0 small';
    badge.innerHTML = `
      <div><i class="bi bi-clock-history me-1"></i>Créance client en cours : <strong class="text-danger">${balance.toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</strong> (Plafond illimité)</div>
    `;
  } else if (balance < 0) {
    badge.className = 'client-credit-badge alert alert-success p-2 mt-2 mb-0 small';
    badge.innerHTML = `
      <div><i class="bi bi-check-circle me-1"></i>Avance disponible : <strong class="text-success">${Math.abs(balance).toLocaleString('fr-FR', {minimumFractionDigits: 2})} DA</strong></div>
    `;
  } else {
    badge.className = 'client-credit-badge alert alert-secondary p-2 mt-2 mb-0 small text-muted';
    badge.innerHTML = `<div><i class="bi bi-person-check me-1"></i>Client à jour (aucun encours). Plafond illimité.</div>`;
  }
}

function bindCounterKeyboardShortcuts() {
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' || e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return;
    const target = e.target;
    if (!target) return;

    // Inside sale or purchase lines
    if (target.classList.contains('sale-item') || target.classList.contains('purchase-material')) {
      e.preventDefault();
      const row = target.closest('.doc-line-card') || target.closest('.doc-line-grid');
      if (row) {
        const qtyInput = row.querySelector('.sale-qty, .purchase-qty, input[name="quantity[]"]');
        if (qtyInput) qtyInput.focus();
      }
    } else if (target.classList.contains('sale-qty') || target.classList.contains('purchase-qty')) {
      e.preventDefault();
      const row = target.closest('.doc-line-card') || target.closest('.doc-line-grid');
      if (row) {
        const priceInput = row.querySelector('.sale-price, .purchase-price, input[name="unit_price[]"]');
        if (priceInput) priceInput.focus();
      }
    } else if (target.classList.contains('sale-price') || target.classList.contains('purchase-price')) {
      e.preventDefault();
      const isSale = target.classList.contains('sale-price');
      const addBtn = isSale ? document.getElementById('addSaleLine') : document.getElementById('addPurchaseLine');
      if (addBtn) {
        addBtn.click();
        setTimeout(() => {
          const container = document.getElementById(isSale ? 'saleLines' : 'purchaseLines');
          if (container) {
            const rows = container.querySelectorAll('.doc-line-card');
            const lastRow = rows[rows.length - 1];
            if (lastRow) {
              const nextSelect = lastRow.querySelector('select');
              if (nextSelect) nextSelect.focus();
            }
          }
        }, 60);
      }
    }
  });
}

export function initFormsModule() {
  const token = window.fabApi?.csrfToken || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  if (token) {
    document.querySelectorAll('form[method="post"],form[method="POST"]').forEach(function (form) {
      if (form.querySelector('input[name="csrf_token"]')) return;
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'csrf_token';
      input.value = token;
      form.appendChild(input);
    });
    window.fabCsrfToken = token;
  }

  const _getLocalDate = typeof window.getLocalDateISO === 'function' 
    ? window.getLocalDateISO 
    : function(d) {
        const dt = d || new Date();
        return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
      };
  const today = _getLocalDate();
  document.querySelectorAll('input[type="date"]').forEach(function (input) {
    if (input.dataset.noAutoDate === '1') return;
    if (input.value) return;
    const form = input.closest('form');
    if (form && (form.method || 'get').toLowerCase() === 'get') return;
    input.value = today;
  });

  bindFormEventListeners();
  resetSubmittingButtons();
}

export function resetSubmittingButtons(root) {
  const scope = root || (typeof document !== 'undefined' ? document : null);
  if (!scope) return;
  scope.querySelectorAll('button.is-loading, input.is-loading').forEach(button => {
    button.classList.remove('is-loading', 'disabled');
    button.disabled = false;
    const originalHTML = button.getAttribute('data-original-html');
    if (originalHTML) {
      button.innerHTML = originalHTML;
    }
  });
  scope.querySelectorAll('form[data-submitting="true"]').forEach(form => {
    form.dataset.submitting = 'false';
  });
}

if (typeof window !== 'undefined') {
  window.addEventListener('pageshow', (event) => {
    resetSubmittingButtons();
  });
}

if (typeof document !== 'undefined') {
  document.addEventListener('fab:page-loaded', () => {
    initFormsModule();
  });
}
