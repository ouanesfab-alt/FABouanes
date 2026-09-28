import { absoluteUrl } from './api.js';

export function initContextMenuModule() {
  const menu = document.getElementById('contextMenu');
  const titleEl = document.getElementById('contextTitle');
  const viewLink = document.getElementById('contextView');
  const printLink = document.getElementById('contextPrint');
  const editLink = document.getElementById('contextEdit');
  const dividerEl = document.getElementById('contextDivider');
  const deleteForm = document.getElementById('contextDeleteForm');
  const deleteBtn = document.getElementById('contextDelete');

  function hide() {
    if (menu) menu.style.display = 'none';
  }

  function show(x, y, target, options) {
    if (!menu) return;
    const secondaryOnly = !!(options && options.secondaryOnly);
    const editUrl = target.dataset.editUrl || '';
    const editAction = target.dataset.editAction || '';
    const deleteUrl = target.dataset.deleteUrl || '';
    const printUrl = absoluteUrl(target.dataset.printUrl || '');
    const deleteLabel = target.dataset.deleteLabel || 'cet élément';

    // Détection d'un lien de détail ou consultation (fiche client, fiche fournisseur, etc.)
    let detailUrl = target.dataset.detailUrl || '';
    if (!detailUrl) {
      const link = target.querySelector('a.contacts-link, td.col-name a, a.table-link');
      if (link && link.href && !link.href.endsWith('#') && !link.classList.contains('btn-danger')) {
        detailUrl = link.href;
      }
    }

    // Détection d'une URL d'édition si non renseignée
    let resolvedEditUrl = editUrl;
    if (!resolvedEditUrl && !editAction) {
      const editAnchor = target.querySelector('.col-actions a[href*="edit"], td:last-child a[href*="edit"]');
      if (editAnchor && editAnchor.href) {
        resolvedEditUrl = editAnchor.href;
      }
    }

    // Libellé de titre du menu contextuel
    let label = target.dataset.label || '';
    if (!label) {
      const nameCell = target.querySelector('td.col-name, td.col-designation, td:first-child, td:nth-child(2)');
      if (nameCell) label = (nameCell.textContent || '').trim().replace(/\s+/g, ' ');
    }
    if (titleEl) {
      titleEl.textContent = label ? (label.length > 26 ? label.slice(0, 24) + '…' : label) : 'Actions';
    }

    // 1. Consulter la fiche / détail
    const detailLink = document.getElementById('contextDetail');
    if (detailLink) {
      detailLink.style.display = (detailUrl && !secondaryOnly) ? 'flex' : 'none';
      if (detailUrl) detailLink.href = detailUrl;
    }

    // 2. Voir la facture / document
    if (viewLink) {
      viewLink.style.display = (printUrl && !secondaryOnly) ? 'flex' : 'none';
      if (printUrl) viewLink.href = printUrl;
    }

    // 3. Imprimer
    if (printLink) {
      printLink.style.display = (printUrl && !secondaryOnly) ? 'flex' : 'none';
      if (printUrl) {
        printLink.href = printUrl;
        const isAndroidWebView = /Android/i.test(navigator.userAgent) && window.location.hostname === '127.0.0.1';
        printLink.target = isAndroidWebView ? '_self' : '_blank';
      }
    }

    // 4. Modifier
    const hasEdit = !!(resolvedEditUrl || editAction);
    if (editLink) {
      editLink.style.display = hasEdit ? 'flex' : 'none';
      editLink.onclick = null;
      if (resolvedEditUrl) {
        editLink.href = resolvedEditUrl;
      } else if (editAction) {
        editLink.href = '#';
        editLink.onclick = function (event) {
          event.preventDefault();
          hide();
          const handler = window[editAction];
          if (typeof handler === 'function') handler(target);
        };
      }
    }

    // 5. Supprimer
    const hasDelete = !!deleteUrl;
    if (deleteForm) deleteForm.style.display = hasDelete ? 'block' : 'none';
    if (deleteBtn && hasDelete) {
      deleteForm.action = deleteUrl;
      deleteBtn.style.display = 'flex';
      deleteBtn.onclick = function (event) {
        if (!confirm('Supprimer ' + deleteLabel + ' ?')) event.preventDefault();
      };
    }

    // Séparateur
    const hasTopItems = !!(detailUrl || printUrl || hasEdit);
    if (dividerEl) dividerEl.style.display = (hasTopItems && hasDelete) ? 'block' : 'none';

    // Si aucune action n'est disponible pour cette ligne, ne pas ouvrir
    if (!detailUrl && !printUrl && !hasEdit && !hasDelete) {
      hide();
      return;
    }

    menu.style.display = 'block';
    const menuWidth = menu.offsetWidth || 210;
    const menuHeight = menu.offsetHeight || 160;
    const posX = Math.max(8, Math.min(x, window.innerWidth - menuWidth - 12));
    const posY = Math.max(8, Math.min(y, window.innerHeight - menuHeight - 12));

    menu.style.left = posX + 'px';
    menu.style.top = posY + 'px';
  }

  // Clic droit : Menu contextuel universel sur les tableaux
  document.addEventListener('contextmenu', function (event) {
    if (!menu) return;

    // Laisser le menu natif du navigateur dans les champs de texte
    if (event.target.closest('input, textarea, select, [contenteditable="true"]')) return;

    // Détecter un conteneur cible ou une ligne de tableau
    const target = event.target.closest('.context-target, tbody tr');
    if (!target) {
      hide();
      return;
    }

    // Ignorer les lignes d'en-tête (th) ou d'état vide
    if (target.closest('thead, tfoot') || target.querySelector('th') || target.querySelector('td[colspan]')) {
      hide();
      return;
    }

    event.preventDefault();
    show(event.clientX, event.clientY, target);
  });

  // Double-clic : Navigation et ouverture directe sur toutes les lignes de tableaux
  document.addEventListener('dblclick', function (event) {
    // Ne pas déclencher si l'utilisateur double-clique sur un formulaire ou un bouton de suppression
    if (event.target.closest('input, select, textarea, button, form, .btn-danger, [data-delete-url]')) return;

    // Trouver la ligne de tableau ciblée
    const target = event.target.closest('tr');
    if (!target) return;

    // Ignorer les lignes d'en-tête (th) ou d'état vide
    if (target.closest('thead, tfoot') || target.querySelector('th') || target.querySelector('td[colspan]')) return;

    // Supprimer la sélection de texte accidentelle provoquée par le double-clic
    if (window.getSelection) {
      const sel = window.getSelection();
      if (sel && sel.removeAllRanges) sel.removeAllRanges();
    }

    hide();

    // 1. Action personnalisée JS
    const editAction = target.dataset.editAction;
    if (editAction && typeof window[editAction] === 'function') {
      event.preventDefault();
      window[editAction](target);
      return;
    }

    // 2. Lien de détail prioritaire (Fiche client / Fiche fournisseur)
    const detailUrl = target.dataset.detailUrl;
    if (detailUrl) {
      event.preventDefault();
      window.location.href = detailUrl;
      return;
    }

    // 3. Lien principal au sein de la ligne (ex: lien nom client/fournisseur ou document)
    const primaryLink = target.querySelector('a.contacts-link, a.table-link, td.col-name a, td:first-child a:not(.btn), td:nth-child(2) a:not(.btn)');
    if (primaryLink && primaryLink.href && !primaryLink.href.endsWith('#') && !primaryLink.classList.contains('btn-danger')) {
      event.preventDefault();
      window.location.href = primaryLink.href;
      return;
    }

    // 4. URL d'édition
    const editUrl = target.dataset.editUrl;
    if (editUrl) {
      event.preventDefault();
      window.location.href = editUrl;
      return;
    }

    // 5. Lien d'action d'édition ou de consultation dans la colonne d'actions
    const actionLink = target.querySelector('.col-actions a:not(.btn-danger):not([href="#"]), td:last-child a:not(.btn-danger):not([href="#"])');
    if (actionLink && actionLink.href) {
      event.preventDefault();
      window.location.href = actionLink.href;
      return;
    }
  });

  let pressTimer;
  document.addEventListener('touchstart', function (event) {
    if (!menu) return;
    const target = event.target.closest('.context-target');
    if (!target) return;
    pressTimer = setTimeout(function () {
      const touch = event.touches[0];
      show(touch.clientX, touch.clientY, target);
    }, 500);
  }, { passive: true });
  document.addEventListener('touchend', function () { clearTimeout(pressTimer); }, { passive: true });
  document.addEventListener('touchmove', function () { clearTimeout(pressTimer); }, { passive: true });
  document.addEventListener('click', function (event) { if (menu && !event.target.closest('.context-menu')) hide(); });
  window.addEventListener('scroll', hide, true);
  window.addEventListener('resize', hide);
}

