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
    button.innerHTML = '<span class="mac-spinner" role="status" aria-hidden="true"></span>' + originalHTML;
    
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


