(() => {
  const TAGS = {id: 'Перевозка', status: 'Статус', driver: 'Водитель', creator: 'Создал', q: 'везде'};
  const dataNode = document.getElementById('suggest-data');
  const input = document.getElementById('search-input');
  const box = document.getElementById('suggest');

  document.querySelectorAll('tr.row-click').forEach(row => {
    row.addEventListener('click', e => { if (!e.target.closest('a')) location.href = row.dataset.href; });
  });
  if (!input || !dataNode) return;

  const data = JSON.parse(dataNode.textContent);
  const params = new URLSearchParams(location.search);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  let options = [], active = -1;

  const has = (tag, value) => params.getAll(tag).includes(String(value));

  function build(raw) {
    const typed = raw.trim(), q = typed.toLowerCase().replace(/^№/, '');
    if (!q) return [];
    const out = [];
    const add = (tag, value, text) => { if (!has(tag, value)) out.push({tag, value: String(value), text}); };
    if (/^\d+$/.test(q)) data.ids.filter(id => String(id).includes(q)).slice(0, 5).forEach(id => add('id', id, '№' + id));
    data.statuses.filter(([, label]) => label.toLowerCase().includes(q)).forEach(([key, label]) => add('status', key, label));
    data.drivers.filter(d => d.name.toLowerCase().includes(q)).forEach(d => add('driver', d.id, d.name));
    data.creators.filter(c => c.name.toLowerCase().includes(q)).forEach(c => add('creator', c.id, c.name));
    out.push({tag: 'q', value: typed, text: typed, free: true});
    return out;
  }

  function highlight(text, q) {
    const i = q ? text.toLowerCase().indexOf(q) : -1;
    if (i < 0) return esc(text);
    return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) + '</mark>' + esc(text.slice(i + q.length));
  }

  function render() {
    const q = input.value.trim().toLowerCase().replace(/^№/, '');
    box.innerHTML = q
      ? options.map((o, i) => `<div class="opt" role="option" id="opt-${i}" data-opt="${i}" aria-selected="${i === active}">
          <span>${o.free ? `Искать «${esc(o.text)}» во всех полях` : highlight(o.text, q)}</span><span class="tag">${TAGS[o.tag]}</span></div>`).join('')
      : '<div class="suggest-hint">Начните вводить номер, статус, фамилию водителя или того, кто создал. Выберите подсказку, чтобы добавить фильтр. Enter выбирает первую.</div>';
    box.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    input.setAttribute('aria-activedescendant', active >= 0 ? `opt-${active}` : '');
  }

  function close() {
    box.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
  }

  function choose(i) {
    const o = options[i];
    if (!o) return;
    params.append(o.tag, o.value);
    location.search = params.toString();
  }

  function refresh() { options = build(input.value); active = options.length ? 0 : -1; render(); }

  input.addEventListener('input', refresh);
  input.addEventListener('focus', refresh);
  input.addEventListener('blur', () => setTimeout(close, 120));
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' && options.length) { e.preventDefault(); active = (active + 1) % options.length; render(); }
    else if (e.key === 'ArrowUp' && options.length) { e.preventDefault(); active = (active - 1 + options.length) % options.length; render(); }
    else if (e.key === 'Enter') { e.preventDefault(); if (options.length) choose(active >= 0 ? active : 0); }
    else if (e.key === 'Escape') close();
    else if (e.key === 'Backspace' && !input.value) {
      const tokens = document.querySelectorAll('[data-token-remove]');
      if (tokens.length) location.href = tokens[tokens.length - 1].href;
    }
  });
  document.getElementById('search-box').addEventListener('click', e => { if (!e.target.closest('a')) input.focus(); });
  document.addEventListener('mousedown', e => {
    const o = e.target.closest('[data-opt]');
    if (o) { e.preventDefault(); choose(+o.dataset.opt); }
  });
})();
