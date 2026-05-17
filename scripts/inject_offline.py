"""
Inject offline-aware JS into sale_new.html and payment_new.html,
and add badge/icon + initOfflineSync() into base.html.
Run once from the project root.
"""
import re

# ─── sale_new.html ───────────────────────────────────────────────────────────

SALE_FORM_OLD = 'id="saleDocumentForm"'
SALE_FORM_NEW = 'id="sale-form"'

SALE_OFFLINE_SCRIPT = """
<script type="module">
import { queueOperation, getRefData } from '/static/js/offline-db.js';

const form = document.getElementById('sale-form');

async function fillSelectsFromCache() {
  if (navigator.onLine) return;
  const clients = await getRefData('clients');
  const catalog = await getRefData('catalog');
  const clientSelect = document.getElementById('clientSelect');
  if (clients && clientSelect) {
    clientSelect.innerHTML =
      '<option value="">Comptoir (cash)</option>' +
      clients.map(c =>
        `<option value="${c.id}">${c.name}${c.phone ? ' \u2014 ' + c.phone : ''}</option>`
      ).join('');
  }
  const tmplSelect = document.getElementById('saleLineTemplate')
    ?.content?.querySelector('.sale-item');
  if (catalog && tmplSelect) {
    tmplSelect.innerHTML = catalog.map(p =>
      `<option value="finished:${p.id}" data-price="${p.sale_price}" data-unit="${p.unit}" data-stock="0" data-cost="0">${p.name} (${p.sale_price} DA)</option>`
    ).join('');
  }
}

form?.addEventListener('submit', async (e) => {
  if (navigator.onLine) return;
  e.preventDefault();

  const fd = new FormData(form);
  const data = {};
  for (const [key, val] of fd.entries()) {
    if (key.endsWith('[]')) {
      if (!data[key]) data[key] = [];
      data[key].push(val);
    } else {
      data[key] = val;
    }
  }
  await queueOperation('create_sale', data);

  form.innerHTML = `
    <div class="alert alert-success text-center p-4">
      <i class="bi bi-clock-history fs-3 d-block mb-2"></i>
      <strong>Vente enregistr\u00e9e hors-ligne</strong><br>
      <small class="text-muted">Elle sera synchronis\u00e9e automatiquement \u00e0 la reconnexion.</small>
      <div class="mt-3">
        <a href="/sales" class="btn btn-sm btn-outline-success me-2">Retour aux ventes</a>
        <a href="/sales/new" class="btn btn-sm btn-success">Nouvelle vente</a>
      </div>
    </div>`;
});

document.addEventListener('DOMContentLoaded', fillSelectsFromCache);
</script>
"""

path = "templates/sale_new.html"
txt = open(path, encoding="utf-8").read()
txt = txt.replace(SALE_FORM_OLD, SALE_FORM_NEW, 1)
# Insert before final {% endblock %}
last = txt.rfind("\n{% endblock %}")
txt = txt[:last] + SALE_OFFLINE_SCRIPT + txt[last:]
open(path, "w", encoding="utf-8").write(txt)
print(f"[OK] {path}")


# ─── payment_new.html ────────────────────────────────────────────────────────

PAYMENT_FORM_OLD = '<form method="post" class="payment-form-grid">'
PAYMENT_FORM_NEW = '<form method="post" class="payment-form-grid" id="payment-form">'

PAYMENT_CLIENT_SELECT_OLD = '<select name="client_id" class="form-select" required>'
PAYMENT_CLIENT_SELECT_NEW = '<select name="client_id" class="form-select" id="paymentClientSelect" required>'

PAYMENT_DATE_INPUT_OLD = '<input name="payment_date" type="date" class="form-control">'
PAYMENT_DATE_INPUT_NEW = '<input name="payment_date" type="date" class="form-control" id="paymentDate">'

PAYMENT_OFFLINE_SCRIPT = """
<script type="module">
import { queueOperation, getRefData } from '/static/js/offline-db.js';

const form = document.getElementById('payment-form');
const paymentDateInput = document.getElementById('paymentDate');

if (paymentDateInput) {
  const today = new Date().toISOString().split('T')[0];
  paymentDateInput.max = today;
  if (!paymentDateInput.value) paymentDateInput.value = today;
}

async function fillClientsFromCache() {
  if (navigator.onLine) return;
  const clients = await getRefData('clients');
  const sel = document.getElementById('paymentClientSelect');
  if (clients && sel) {
    sel.innerHTML = clients.map(c =>
      `<option value="${c.id}">${c.name}${c.phone ? ' \u2014 ' + c.phone : ''}</option>`
    ).join('');
  }
}

form?.addEventListener('submit', async (e) => {
  if (navigator.onLine) return;
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  await queueOperation('create_payment', data);
  form.innerHTML = `
    <div class="alert alert-success text-center p-4">
      <i class="bi bi-clock-history fs-3 d-block mb-2"></i>
      <strong>Paiement enregistr\u00e9 hors-ligne</strong><br>
      <small class="text-muted">Il sera synchronis\u00e9 automatiquement \u00e0 la reconnexion.</small>
      <div class="mt-3">
        <a href="/payments" class="btn btn-sm btn-success">Retour aux paiements</a>
      </div>
    </div>`;
});

document.addEventListener('DOMContentLoaded', fillClientsFromCache);
</script>
"""

path = "templates/payment_new.html"
txt = open(path, encoding="utf-8").read()
txt = txt.replace(PAYMENT_FORM_OLD, PAYMENT_FORM_NEW, 1)
txt = txt.replace(PAYMENT_CLIENT_SELECT_OLD, PAYMENT_CLIENT_SELECT_NEW, 1)
txt = txt.replace(PAYMENT_DATE_INPUT_OLD, PAYMENT_DATE_INPUT_NEW, 1)
last = txt.rfind("\n{% endblock %}")
txt = txt[:last] + PAYMENT_OFFLINE_SCRIPT + txt[last:]
open(path, "w", encoding="utf-8").write(txt)
print(f"[OK] {path}")


# ─── base.html ───────────────────────────────────────────────────────────────

BASE_OPS_LINK_OLD = (
    '        <a href="{{ url_for(\'operations\') }}" class="{{ \'active\' if operations_nav_active else \'\' }}"><i\n'
    '            class="bi bi-arrow-left-right me-1"></i>Op\u00e9rations</a>'
)
BASE_OPS_LINK_NEW = (
    '        <a href="{{ url_for(\'operations\') }}" class="{{ \'active\' if operations_nav_active else \'\' }}"><i\n'
    '            class="bi bi-arrow-left-right me-1"></i>Op\u00e9rations'
    '<span id="offline-pending-badge" class="badge bg-warning text-dark ms-1" hidden title="Op\u00e9rations en attente de synchronisation"></span>'
    '<span id="network-status-icon" class="ms-1" title="Statut r\u00e9seau">'
    '<i class="bi bi-wifi" id="icon-online" style="color:#4ade80;font-size:.75rem"></i>'
    '<i class="bi bi-wifi-off d-none" id="icon-offline" style="color:#fb923c;font-size:.75rem"></i>'
    '</span></a>'
)

BASE_BODY_CLOSE_OLD = "  {% block scripts %}{% endblock %}\n</body>"
BASE_BODY_CLOSE_NEW = (
    "  {% block scripts %}{% endblock %}\n"
    "  {% if g.user %}\n"
    "  <script type=\"module\">\n"
    "    import { initOfflineSync } from '/static/js/offline-sync.js';\n"
    "    initOfflineSync();\n"
    "    function updateNetworkIcon() {\n"
    "      const online = navigator.onLine;\n"
    "      document.getElementById('icon-online')?.classList.toggle('d-none', !online);\n"
    "      document.getElementById('icon-offline')?.classList.toggle('d-none', online);\n"
    "    }\n"
    "    window.addEventListener('online',  updateNetworkIcon);\n"
    "    window.addEventListener('offline', updateNetworkIcon);\n"
    "    document.addEventListener('DOMContentLoaded', updateNetworkIcon);\n"
    "  </script>\n"
    "  {% endif %}\n"
    "</body>"
)

path = "templates/base.html"
txt = open(path, encoding="utf-8").read()

if BASE_OPS_LINK_OLD in txt:
    txt = txt.replace(BASE_OPS_LINK_OLD, BASE_OPS_LINK_NEW, 1)
    print(f"[OK] base.html ops link patched")
else:
    print(f"[WARN] base.html ops link not found — skipped badge injection")

if BASE_BODY_CLOSE_OLD in txt:
    txt = txt.replace(BASE_BODY_CLOSE_OLD, BASE_BODY_CLOSE_NEW, 1)
    print(f"[OK] base.html body close patched")
else:
    print(f"[WARN] base.html body close not found")

open(path, "w", encoding="utf-8").write(txt)
print(f"[OK] {path}")
