(() => {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];

  function updateHint(row) {
    const select = $('select[name="product_id"]', row);
    const hint = $('[data-available-hint]', row);
    const option = select && select.selectedOptions[0];
    if (!hint || !option || !option.dataset.available) return;
    hint.textContent = `Доступно: ${option.dataset.available}`;
  }

  document.addEventListener('change', e => {
    if (e.target.matches('[data-autosubmit]') && e.target.files.length) e.target.form.submit();
    const row = e.target.closest('[data-item-row]');
    if (row && e.target.name === 'product_id') updateHint(row);
  });
  document.addEventListener('click', e => {
    const close = e.target.closest('[data-confirm-close]');
    if (close) close.closest('details').open = false;
  });
  $$('[data-item-row]').forEach(updateHint);

  const form = $('#create-form');
  if (!form) return;
  const steps = $('#route-steps');
  const items = $('#items');
  const docsInput = $('#create-docs');
  const docsList = $('#create-docs-list');
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const size = b => b >= 1048576 ? `${(b / 1048576).toFixed(1).replace('.', ',')} МБ` : `${Math.max(1, Math.round(b / 1024))} КБ`;

  function clone(id) { return $(`#${id}`).content.firstElementChild.cloneNode(true); }

  function summary() {
    const routeSteps = $$('[data-route-step] select', steps);
    const names = [$('[data-step-title]', steps).dataset.stepTitle, ...routeSteps.map(s => s.selectedOptions[0]?.textContent || '')];
    $('#sum-route').textContent = names.join(' → ');
    $('#sum-stages').textContent = routeSteps.length;
    $('#sum-items').textContent = $$('select[name="product_id"]', items).filter(s => s.value).length;
    const files = [...docsInput.files];
    $('#sum-docs').innerHTML = files.length
      ? `<span class="num">${files.length}</span>`
      : '<span class="num">0</span> <span class="muted" style="font-weight:400">· резерв будет недоступен</span>';
    docsList.innerHTML = files.length
      ? files.map(f => `<div class="doc"><span class="ext">${esc((f.name.split('.').pop() || '').toUpperCase().slice(0, 4))}</span>
          <span class="name">${esc(f.name)}</span><span class="by">${size(f.size)}</span></div>`).join('')
      : '<p class="muted" style="margin:0;font-size:14px">Документы не прикреплены.</p>';
    $$('[data-rm-step]', steps).forEach(b => { b.hidden = routeSteps.length < 2; });
  }

  $('#add-step').addEventListener('click', () => { steps.append(clone('route-step-template')); summary(); });
  $('#add-item').addEventListener('click', () => { items.append(clone('item-template')); summary(); });
  form.addEventListener('click', e => {
    const step = e.target.closest('[data-rm-step]');
    if (step) { step.closest('li').remove(); summary(); }
    const item = e.target.closest('[data-rm-item]');
    if (item) { item.closest('[data-item-row]').remove(); summary(); }
  });
  form.addEventListener('change', summary);
  summary();
})();
