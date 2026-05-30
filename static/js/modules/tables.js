function queueGridTask(fn) {
  if ('requestAnimationFrame' in window) {
    window.requestAnimationFrame(fn);
    return;
  }
  window.setTimeout(fn, 0);
}

function hiddenPanel(el) { return !!el.closest('[hidden]'); }

function cleanText(text) {
  return (text || '').trim().replace(/\s+/g, ' ');
}

function normalizeText(text) {
  return cleanText(text).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function externalFilter(table) {
  const card = table.closest('.card');
  if (!card) return false;
  return Array.from(card.querySelectorAll('form')).some(function (form) {
    return (form.method || 'get').toLowerCase() === 'get' && !!(form.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
}

function columnKind(th, index, rows) {
  const className = (th.className || '').toLowerCase();
  const label = normalizeText(th.textContent);
  const firstRow = rows.find(function (row) { return !!row.cells[index]; });
  const cellClass = firstRow && firstRow.cells[index] ? (firstRow.cells[index].className || '').toLowerCase() : '';
  if (className.includes('col-date') || cellClass.includes('col-date') || /\b(date|cree|created|derniere)\b/.test(label)) {
    return 'date';
  }
  if (
    className.includes('col-money') ||
    className.includes('col-balance') ||
    cellClass.includes('cell-num') ||
    cellClass.includes('col-money') ||
    cellClass.includes('col-balance') ||
    /(total|solde|reste|paye|versement|montant|prix|cout|qte|quantite|stock|jour|duree|vente|dette|creance|benefice|profit|chiffre|%|id)/.test(label)
  ) {
    return 'number';
  }
  return 'text';
}

function parseDate(text) {
  const clean = cleanText(text);
  if (!clean) return null;
  let match = clean.match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
  if (match) {
    const date = new Date(+match[1], +match[2] - 1, +match[3], +(match[4] || 0), +(match[5] || 0), +(match[6] || 0));
    return isNaN(date.getTime()) ? null : date.getTime();
  }
  match = clean.match(/(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
  if (match) {
    const year = match[3].length === 2 ? 2000 + (+match[3]) : +match[3];
    const date = new Date(year, +match[2] - 1, +match[1], +(match[4] || 0), +(match[5] || 0), +(match[6] || 0));
    return isNaN(date.getTime()) ? null : date.getTime();
  }
  const fallback = Date.parse(clean);
  return isNaN(fallback) ? null : fallback;
}

function parseNumber(text) {
  const clean = cleanText(text).replace(/\u00a0/g, ' ');
  if (!clean || /^[-\u2013\u2014]$/.test(clean) || normalizeText(clean) === 'ok') return null;
  const tokenMatch = clean.match(/[-+]?\d[\d\s.,]*/);
  if (!tokenMatch) return null;
  let token = tokenMatch[0].replace(/\s+/g, '');
  const comma = token.lastIndexOf(',');
  const dot = token.lastIndexOf('.');
  if (comma > -1 && dot > -1) {
    if (comma > dot) {
      token = token.replace(/\./g, '').replace(',', '.');
    } else {
      token = token.replace(/,/g, '');
    }
  } else if (comma > -1) {
    token = token.replace(',', '.');
  } else if ((token.match(/\./g) || []).length > 1) {
    const last = token.lastIndexOf('.');
    token = token.slice(0, last).replace(/\./g, '') + '.' + token.slice(last + 1);
  }
  const value = Number(token);
  return isNaN(value) ? null : value;
}

function parseCell(cell, kind) {
  const text = cell ? (cell.getAttribute('data-sort-value') || cell.textContent) : '';
  if (kind === 'date') return parseDate(text);
  if (kind === 'number') return parseNumber(text);
  return normalizeText(text);
}

function rowSortSequence(row) {
  if (!row || row.dataset.sortSequence === undefined) return null;
  const value = Number(row.dataset.sortSequence);
  return isNaN(value) ? null : value;
}

function compareValues(left, right, kind, direction) {
  const leftMissing = left === null || left === undefined || left === '';
  const rightMissing = right === null || right === undefined || right === '';
  if (leftMissing && rightMissing) return 0;
  if (leftMissing) return 1;
  if (rightMissing) return -1;
  let cmp;
  if (kind === 'text') {
    cmp = String(left).localeCompare(String(right), 'fr', { numeric: true, sensitivity: 'base' });
  } else {
    cmp = left > right ? 1 : left < right ? -1 : 0;
  }
  return direction === 'asc' ? cmp : -cmp;
}

function defaultDirection(kind) {
  return kind === 'text' ? 'asc' : 'desc';
}

function scrollSortedTableToStart(table) {
  const shell = table.closest('.table-shell') || table.closest('.table-responsive') || table;
  const top = Math.max(0, shell.getBoundingClientRect().top + window.scrollY - 76);
  const scroller = table.closest('.table-responsive');
  if (scroller) scroller.scrollLeft = 0;
  window.scrollTo({ top: top, behavior: 'auto' });
}

function setupGrid(table) {
  if (table.dataset.enhanced || table.classList.contains('no-grid')) return;
  table.dataset.enhanced = '1';
  const tbody = table.tBodies[0]; if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll('tr')).filter(function (row) { return !row.querySelector('td[colspan]'); });
  rows.forEach(function (row, position) {
    row.dataset.originalIndex = row.dataset.originalIndex || String(position);
    row.dataset.searchText = row.dataset.searchText || normalizeText(row.textContent);
  });
  const wrap = document.createElement('div');
  wrap.className = 'table-shell';
  const showSearch = !externalFilter(table);
  const bar = document.createElement('div');
  bar.className = 'table-search';
  bar.innerHTML = '<input class="form-control form-control-sm" placeholder="Rechercher...">';
  const existing = table.parentElement && table.parentElement.classList.contains('table-responsive') ? table.parentElement : null;
  const scroller = existing || document.createElement('div');
  scroller.classList.add('table-scroll', 'table-responsive');
  table.classList.add('table-sticky', 'table-row-hover');
  if (existing) {
    existing.parentNode.insertBefore(wrap, existing);
    if (showSearch) wrap.appendChild(bar);
    wrap.appendChild(existing);
  } else {
    table.parentNode.insertBefore(wrap, table);
    if (showSearch) wrap.appendChild(bar);
    wrap.appendChild(scroller);
    scroller.appendChild(table);
  }
  const input = showSearch ? bar.querySelector('input') : null;
  
  if (input) {
    const urlParams = new URLSearchParams(window.location.search);
    const initialQ = urlParams.get('q') || '';
    if (initialQ) {
      input.value = initialQ;
    }
  }

  let currentRows = [...rows];
  function applyFilter() {
    const q = input ? normalizeText(input.value) : '';
    currentRows.forEach(function (row) { row.style.display = !q || (row.dataset.searchText || '').includes(q) ? '' : 'none'; });
    
    if (input && q !== (new URLSearchParams(window.location.search)).get('q')) {
      const url = new URL(window.location);
      if (q) url.searchParams.set('q', input.value);
      else url.searchParams.delete('q');
      window.history.replaceState({}, '', url);
    }
  }
  if (input) input.addEventListener('input', applyFilter);
  
  window.addEventListener('popstate', function () {
    if (input) {
      const urlParams = new URLSearchParams(window.location.search);
      input.value = urlParams.get('q') || '';
      applyFilter();
    }
  });

  Array.from(table.querySelectorAll('thead th')).forEach(function (th, index) {
    if (th.colSpan > 1 || th.querySelector('a')) return;
    th.dataset.sortable = '1';
    th.setAttribute('aria-sort', 'none');
    th.title = 'Trier';
    th.addEventListener('click', function () {
      const kind = columnKind(th, index, currentRows);
      const next = th.dataset.sortDir ? (th.dataset.sortDir === 'asc' ? 'desc' : 'asc') : defaultDirection(kind);
      table.querySelectorAll('thead th[data-sortable="1"]').forEach(function (header) {
        delete header.dataset.sortDir;
        header.setAttribute('aria-sort', 'none');
      });
      th.dataset.sortDir = next;
      th.setAttribute('aria-sort', next === 'asc' ? 'ascending' : 'descending');
      currentRows.sort(function (a, b) {
        const av = parseCell(a.cells[index], kind);
        const bv = parseCell(b.cells[index], kind);
        const cmp = compareValues(av, bv, kind, next);
        if (cmp) return cmp;
        if (kind === 'date') {
          const aSequence = rowSortSequence(a);
          const bSequence = rowSortSequence(b);
          if (aSequence !== null && bSequence !== null && aSequence !== bSequence) {
            return next === 'asc' ? aSequence - bSequence : bSequence - aSequence;
          }
        }
        return Number(a.dataset.originalIndex || 0) - Number(b.dataset.originalIndex || 0);
      });
      currentRows.forEach(function (row) { tbody.appendChild(row); });
      applyFilter();
      scrollSortedTableToStart(table);
    });
  });
  applyFilter();
}

export function initDataGrids(root) {
  (root || document).querySelectorAll('table.js-datagrid').forEach(function (table) {
    if (table.dataset.enhanced || table.classList.contains('no-grid') || hiddenPanel(table)) return;
    queueGridTask(function () { setupGrid(table); });
  });
}

export function initTablesModule() {
  document.addEventListener('fab:panel-open', function (event) {
    if (event.detail && event.detail.panel) initDataGrids(event.detail.panel);
  });
  queueGridTask(function () { initDataGrids(document); });
}
