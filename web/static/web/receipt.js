(() => {
  const parse = v => { const n = parseFloat(String(v).replace(',', '.').replace(/\s/g, '')); return Number.isFinite(n) ? n : null; };

  function check(card) {
    let diffs = 0;
    card.querySelectorAll('tr[data-doc]').forEach(row => {
      const fact = parse(row.querySelector('[data-fact]').value);
      const comment = row.querySelector('[data-comment]');
      const diff = fact !== null && fact !== parse(row.dataset.doc);
      row.classList.toggle('diff', diff);
      comment.placeholder = diff ? 'обязательно' : 'Нужен, если факт отличается';
      comment.classList.toggle('required', diff && !comment.value.trim());
      if (diff) diffs++;
    });
    card.querySelector('[data-diff-count]').textContent = diffs ? `Расхождений: ${diffs}` : '';
  }

  document.querySelectorAll('[data-receipt]').forEach(card => {
    card.addEventListener('input', () => check(card));
    check(card);
  });
})();
