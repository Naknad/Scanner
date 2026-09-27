const fileInput = document.getElementById('fileInput');
const preview = document.getElementById('preview');
const uploadZone = document.getElementById('uploadZone');
const statusLine = document.getElementById('statusLine');
const scanRow = document.getElementById('scanRow');
const resultPanel = document.getElementById('resultPanel');

let selectedFile = null;

document.getElementById('takePhotoBtn').addEventListener('click', () => {
  fileInput.setAttribute('capture', 'environment');
  fileInput.click();
});
document.getElementById('chooseFileBtn').addEventListener('click', () => {
  fileInput.removeAttribute('capture');
  fileInput.click();
});
uploadZone.addEventListener('click', () => fileInput.click());

['dragover', 'dragenter'].forEach(evt =>
  uploadZone.addEventListener(evt, e => { e.preventDefault(); uploadZone.classList.add('dragover'); })
);
['dragleave', 'drop'].forEach(evt =>
  uploadZone.addEventListener(evt, e => { e.preventDefault(); uploadZone.classList.remove('dragover'); })
);
uploadZone.addEventListener('drop', e => {
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

function handleFile(file) {
  selectedFile = file;
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';
  scanRow.style.display = 'flex';
  statusLine.textContent = '';
  resultPanel.style.display = 'none';
}

document.getElementById('scanBtn').addEventListener('click', scanLabel);

async function scanLabel() {
  if (!selectedFile) return;
  statusLine.innerHTML = 'Распознаём этикетку…<div class="spinner"></div>';
  resultPanel.style.display = 'none';

  const form = new FormData();
  form.append('file', selectedFile);

  const started = performance.now();
  try {
    const res = await fetch('/api/scan', { method: 'POST', body: form });
    const data = await res.json();
    const elapsed = Math.round(performance.now() - started);
    statusLine.textContent = `Готово за ${elapsed} мс`;
    renderResult(data);
  } catch (err) {
    statusLine.textContent = 'Ошибка распознавания. Попробуйте другое фото.';
    console.error(err);
  }
}

function renderResult(data) {
  resultPanel.style.display = 'block';

  if (data.status === 'found' || data.status === 'ambiguous') {
    resultPanel.innerHTML = cardHtml(data.card) + sommelierHtml(data.card.slug);
    attachSommelierHandlers(data.card.slug);
    return;
  }

  // not_found -> показываем похожие позиции (аналоги), либо честно сообщаем
  let html = `<div class="wine-card"><span class="badge">Точное совпадение не найдено</span>`;
  if (data.similar && data.similar.length) {
    html += `<p>Похоже на одно из этих вин:</p><div class="similar-list">`;
    data.similar.forEach(w => {
      html += `<div class="similar-item"><span>${escapeHtml(w.name)}<br><small>${escapeHtml(w.producer || '')}</small></span></div>`;
    });
    html += `</div>`;
  } else {
    html += `<p>Не удалось найти это вино в каталоге «Своё Вино».</p>`;
  }
  html += `</div>`;
  resultPanel.innerHTML = html;
}

function starRating(rating) {
  const r = Math.round((rating || 0) * 2) / 2;
  const full = Math.floor(r);
  const half = r - full >= 0.5;
  let stars = '★'.repeat(full);
  if (half) stars += '½';
  stars += '☆'.repeat(Math.max(0, 5 - full - (half ? 1 : 0)));
  return stars;
}

function cardHtml(card) {
  const fields = [];
  if (card.region) fields.push(['Регион', card.region]);
  if (card.grape) fields.push(['Сорт винограда', card.grape]);
  if (card.category || card.color) {
    fields.push(['Категория и цвет', [card.category, card.color].filter(Boolean).join(', ')]);
  }
  if (card.serving_temp) fields.push(['Температура подачи', card.serving_temp]);
  if (card.abv) fields.push(['Крепость вина', card.abv]);
  if (card.roskachestvo_score) fields.push(['Роскачество', card.roskachestvo_score + ' баллов']);

  const fieldsHtml = fields.map(([label, value]) => `
    <div class="field-box">
      <div class="field-label">${escapeHtml(label)}</div>
      <div class="field-value">${escapeHtml(value)}</div>
    </div>`).join('');

  const pairingHtml = (card.food_pairing && card.food_pairing.length)
    ? `<div class="pairing-title">Сочетание с блюдами</div>
       <div class="pairing-chips">${card.food_pairing.map(p => `<span class="pairing-chip">${escapeHtml(p)}</span>`).join('')}</div>`
    : '';

  const ratingHtml = card.public_rating
    ? `<div class="rating-badge"><span class="stars">${starRating(card.public_rating)}</span> Народный рейтинг ${card.public_rating.toFixed ? card.public_rating.toFixed(1) : card.public_rating}</div>`
    : '';

  return `
    <div class="wine-card">
      ${card.image_url ? `<img class="wine-image" src="${escapeHtml(card.image_url)}" alt="${escapeHtml(card.name)}">` : ''}
      ${ratingHtml}
      <div class="producer-link">${escapeHtml(card.producer || '')}</div>
      <h1>${escapeHtml(card.name)}</h1>
      <div class="subtitle-row">${escapeHtml(card.category || 'Вино')}${card.vintage ? ' · ' + escapeHtml(card.vintage) : ''}</div>
      <div class="field-grid">${fieldsHtml}</div>
      ${card.description ? `<div class="description">${escapeHtml(card.description)}</div>` : ''}
      ${pairingHtml}
    </div>`;
}

function sommelierHtml(slug) {
  return `
    <div class="sommelier-box" data-slug="${escapeHtml(slug)}">
      <h3>🍷 Цифровой сомелье</h3>
      <input type="text" id="dishInput" placeholder="Что вы готовите? (например, стейк)">
      <input type="text" id="occasionInput" placeholder="Повод? (например, ужин с друзьями)">
      <button class="btn btn-outline" id="askSommelierBtn" style="width:100%;margin-top:6px;background:#fff">Спросить совет</button>
      <div id="sommelierAnswer" style="margin-top:10px;font-size:13.5px"></div>
    </div>`;
}

function attachSommelierHandlers(slug) {
  const btn = document.getElementById('askSommelierBtn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const dish = document.getElementById('dishInput').value;
    const occasion = document.getElementById('occasionInput').value;
    const params = new URLSearchParams();
    if (dish) params.append('dish', dish);
    if (occasion) params.append('occasion', occasion);
    const res = await fetch(`/api/sommelier/${encodeURIComponent(slug)}?${params.toString()}`);
    const data = await res.json();
    const answerBox = document.getElementById('sommelierAnswer');
    let html = '<ul>' + data.tips.map(t => `<li>${escapeHtml(t)}</li>`).join('') + '</ul>';
    if (data.analogs && data.analogs.length) {
      html += '<div>Похожие вина: ' + data.analogs.map(a => escapeHtml(a.name)).join(', ') + '</div>';
    }
    answerBox.innerHTML = html;
  });
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
