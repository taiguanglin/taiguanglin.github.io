import { createPlayer } from './audio.js';
import { getFile, putFile } from './github.js';
import { getPat, setPat } from './storage.js';

const MAP_BASE = '../tool/word2ebook/data/audio_map/';
const MONTHS = [
  '2025-06', '2025-07', '2025-08', '2025-09',
  '2025-11', '2025-12',
  '2026-01', '2026-02', '2026-03',
];

const els = {
  monthSelect: document.querySelector('#monthSelect'),
  sessionList: document.querySelector('#sessionList'),
  welcome: document.querySelector('#welcome'),
  editor: document.querySelector('#editor'),
  cards: document.querySelector('#cards'),
  sessionTitle: document.querySelector('#sessionTitle'),
  sessionMeta: document.querySelector('#sessionMeta'),
  statusMsg: document.querySelector('#statusMsg'),
  reloadBtn: document.querySelector('#reloadBtn'),
  downloadBtn: document.querySelector('#downloadBtn'),
  saveGithubBtn: document.querySelector('#saveGithubBtn'),
  settingsBtn: document.querySelector('#settingsBtn'),
  settingsBtn2: document.querySelector('#settingsBtn2'),
  settingsDialog: document.querySelector('#settingsDialog'),
  patInput: document.querySelector('#patInput'),
  savePatBtn: document.querySelector('#savePatBtn'),
  stopAtEnd: document.querySelector('#stopAtEnd'),
  miniPlayer: document.querySelector('#miniPlayer'),
  playerTitle: document.querySelector('#playerTitle'),
  playerRange: document.querySelector('#playerRange'),
  playerToggle: document.querySelector('#playerToggle'),
  playerClose: document.querySelector('#playerClose'),
  audioEl: document.querySelector('#audioEl'),
};

const state = {
  month: MONTHS[0],
  map: null,
  remoteSha: null,
  sessionId: null,
  dirty: false,
};

const player = createPlayer({
  audio: els.audioEl,
  titleEl: els.playerTitle,
  rangeEl: els.playerRange,
  stopCheckbox: els.stopAtEnd,
  playerRoot: els.miniPlayer,
  toggleBtn: els.playerToggle,
});

els.playerClose.addEventListener('click', () => player.stop());

function setStatus(msg, ok = true) {
  els.statusMsg.textContent = msg || '';
  els.statusMsg.style.color = ok ? '' : 'var(--bad)';
}

function mapPath(month) {
  return `tool/word2ebook/data/audio_map/${month}.json`;
}

function fmt(sec) {
  if (sec == null || Number.isNaN(sec)) return '';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${s.toFixed(3).padStart(6, '0')}`;
}

function parseTimeInput(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function counts(session) {
  let matched = 0;
  let missing = 0;
  for (const seg of session.segments || []) {
    if (seg.start != null && seg.status !== 'missing') matched += 1;
    else missing += 1;
  }
  return { matched, missing };
}

function currentSession() {
  return state.map?.sessions?.find((s) => s.session_id === state.sessionId) || null;
}

function markDirty() {
  state.dirty = true;
  setStatus('有未儲存變更');
}

async function loadMonth(month) {
  setStatus('載入中…');
  const url = `${MAP_BASE}${month}.json`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`無法載入 ${month}.json (${res.status})`);
  state.map = await res.json();
  state.month = month;
  state.remoteSha = null;
  state.sessionId = null;
  state.dirty = false;
  renderSessionList();
  els.welcome.classList.remove('hidden');
  els.editor.classList.add('hidden');
  setStatus(`已載入 ${month}（${state.map.sessions?.length || 0} sessions）`);
}

function renderSessionList() {
  els.sessionList.innerHTML = '';
  for (const session of state.map?.sessions || []) {
    const { matched, missing } = counts(session);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'session-item' + (session.session_id === state.sessionId ? ' active' : '');
    btn.innerHTML = `<div class="name">${session.date} ${session.source}</div>
      <div class="counts">✓${matched} · ✗${missing} · ${session.segments?.length || 0} 題</div>`;
    btn.addEventListener('click', () => selectSession(session.session_id));
    els.sessionList.append(btn);
  }
}

function selectSession(sessionId) {
  state.sessionId = sessionId;
  renderSessionList();
  renderEditor();
}

function renderEditor() {
  const session = currentSession();
  if (!session) return;
  els.welcome.classList.add('hidden');
  els.editor.classList.remove('hidden');
  els.sessionTitle.textContent = `${session.date} ${session.source}`;
  els.sessionMeta.textContent = `${session.audio_file} · ${session.section_id} · ${session.chapter_file}`;
  els.cards.innerHTML = '';

  if (session.opening) {
    els.cards.append(renderCard(session, 'opening', session.opening, '開場'));
  }
  for (const seg of session.segments || []) {
    els.cards.append(renderCard(session, seg.index, seg, `#${seg.index}`));
  }
}

function renderCard(session, key, item, title) {
  const card = document.createElement('article');
  const status = item.status || 'missing';
  const low = (item.confidence || 0) < 0.45 && status !== 'missing';
  card.className = 'card' + (low ? ' low-conf' : '');
  card.dataset.status = status;

  const preview = item.q_preview || item.text_preview || '';
  card.innerHTML = `
    <div class="card-top">
      <strong>${title}</strong>
      <span class="badge">${status}${low ? ' · low' : ''}${item.locked ? ' · locked' : ''}</span>
    </div>
    ${preview ? `<p class="q-preview">${escapeHtml(preview)}</p>` : ''}
    ${item.srt_preview ? `<div class="srt-preview">${escapeHtml(item.srt_preview)}</div>` : ''}
    <div class="row">
      <label>start (sec)<input type="number" step="0.001" data-field="start" value="${item.start ?? ''}"></label>
      <label>end (sec)<input type="number" step="0.001" data-field="end" value="${item.end ?? ''}"></label>
      <button type="button" class="btn" data-act="play">▶ 播放</button>
      <button type="button" class="btn" data-act="snap-prev">吸附上一段 end</button>
      <button type="button" class="btn" data-act="snap-next">吸附下一段 start</button>
      <label class="check"><input type="checkbox" data-field="locked" ${item.locked ? 'checked' : ''}> locked</label>
    </div>
    <label class="field">notes
      <textarea class="notes" data-field="notes">${escapeHtml(item.notes || '')}</textarea>
    </label>
  `;

  card.querySelectorAll('[data-field]').forEach((input) => {
    const eventName = input.type === 'checkbox' ? 'change' : 'change';
    input.addEventListener(eventName, () => {
      applyField(item, input);
      item.status = item.start != null && item.end != null ? 'manual' : 'missing';
      item.start_label = item.start != null ? fmt(item.start) : null;
      item.end_label = item.end != null ? fmt(item.end) : null;
      markDirty();
      card.dataset.status = item.status;
      card.querySelector('.badge').textContent =
        `${item.status}${((item.confidence || 0) < 0.45 && item.status !== 'missing') ? ' · low' : ''}${item.locked ? ' · locked' : ''}`;
      renderSessionList();
    });
  });

  card.querySelector('[data-act="play"]').addEventListener('click', () => {
    if (item.start == null || item.end == null) {
      setStatus('此段尚無起訖時間', false);
      return;
    }
    player.playRange(
      session.audio_file,
      item.start,
      item.end,
      `${fmt(item.start)} - ${fmt(item.end)}`,
    );
  });

  card.querySelector('[data-act="snap-prev"]').addEventListener('click', () => {
    const prevEnd = previousEnd(session, key);
    if (prevEnd == null) return;
    item.start = prevEnd;
    item.start_label = fmt(prevEnd);
    item.status = item.end != null ? 'manual' : item.status;
    markDirty();
    renderEditor();
  });

  card.querySelector('[data-act="snap-next"]').addEventListener('click', () => {
    const nextStart = nextStartTime(session, key);
    if (nextStart == null) return;
    item.end = nextStart;
    item.end_label = fmt(nextStart);
    item.status = item.start != null ? 'manual' : item.status;
    markDirty();
    renderEditor();
  });

  return card;
}

function applyField(item, input) {
  const field = input.dataset.field;
  if (field === 'locked') {
    item.locked = input.checked;
    return;
  }
  if (field === 'notes') {
    item.notes = input.value;
    return;
  }
  const value = parseTimeInput(input.value);
  item[field] = value;
}

function previousEnd(session, key) {
  if (key === 'opening') return null;
  const idx = Number(key);
  if (idx === 1) return session.opening?.end ?? null;
  const prev = session.segments.find((s) => s.index === idx - 1);
  return prev?.end ?? null;
}

function nextStartTime(session, key) {
  if (key === 'opening') {
    const first = session.segments.find((s) => s.start != null);
    return first?.start ?? null;
  }
  const idx = Number(key);
  const next = session.segments.find((s) => s.index === idx + 1 && s.start != null);
  return next?.start ?? null;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function downloadMap() {
  if (!state.map) return;
  const blob = new Blob([JSON.stringify(state.map, null, 2) + '\n'], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${state.month}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus(`已下載 ${state.month}.json`);
}

async function saveGithub() {
  if (!state.map) return;
  if (!getPat()) {
    els.settingsDialog.showModal();
    setStatus('請先設定 PAT', false);
    return;
  }
  setStatus('上傳中…');
  const path = mapPath(state.month);
  try {
    if (!state.remoteSha) {
      const remote = await getFile(path);
      state.remoteSha = remote.sha;
    }
    const text = JSON.stringify(state.map, null, 2) + '\n';
    const result = await putFile(path, text, state.remoteSha, `Update audio_map ${state.month}`);
    state.remoteSha = result.content?.sha || state.remoteSha;
    state.dirty = false;
    setStatus(`已存到 GitHub：${path}`);
  } catch (err) {
    setStatus(err.message || String(err), false);
  }
}

function openSettings() {
  els.patInput.value = getPat();
  els.settingsDialog.showModal();
}

els.monthSelect.innerHTML = MONTHS.map((m) => `<option value="${m}">${m}</option>`).join('');
els.monthSelect.addEventListener('change', async () => {
  try {
    await loadMonth(els.monthSelect.value);
  } catch (err) {
    setStatus(err.message || String(err), false);
  }
});
els.reloadBtn.addEventListener('click', () => loadMonth(state.month).catch((e) => setStatus(e.message, false)));
els.downloadBtn.addEventListener('click', downloadMap);
els.saveGithubBtn.addEventListener('click', () => saveGithub());
els.settingsBtn.addEventListener('click', openSettings);
els.settingsBtn2.addEventListener('click', openSettings);
els.savePatBtn.addEventListener('click', (e) => {
  e.preventDefault();
  setPat(els.patInput.value.trim());
  els.settingsDialog.close();
  setStatus(getPat() ? 'PAT 已儲存' : '已清除 PAT');
});

loadMonth(MONTHS[0]).catch((err) => setStatus(err.message || String(err), false));
