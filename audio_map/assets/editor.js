import { createAudioController } from './audio.js';
import { getFile, isConflict, putFile, testToken } from './github.js';
import { parseRanges, secondsToTimecode, timecodeToSeconds } from '../../qa/assets/parser.js';
import {
    clearDraft,
    clearPat,
    getDraft,
    getPat,
    getPrefs,
    listDraftPaths,
    setDraft,
    setPat,
    setPrefs,
} from './storage.js';

const MAP_BASE = '../tool/word2ebook/data/audio_map/';
const MONTHS = [
    '2025-06', '2025-07', '2025-08', '2025-09',
    '2025-11', '2025-12',
    '2026-01', '2026-02', '2026-03',
];

const HISTORY_LIMIT = 50;
const history = {
    undo: [],
    redo: [],
    committed: null,
    timer: null,
};

const state = {
    month: MONTHS[0],
    map: null,
    originalMap: null,
    currentSha: '',
    sessionId: null,
    dirty: false,
    prefs: getPrefs(),
    draftPaths: listDraftPaths(),
    draftTimer: null,
    activeSegmentIndex: null,
    usingDraft: false,
};

const els = {
    app: document.querySelector('#app'),
    sidebar: document.querySelector('#sidebar'),
    sidebarToggle: document.querySelector('#sidebarToggle'),
    sidebarToggleIcon: document.querySelector('#sidebarToggle .sidebar-toggle-icon'),
    sidebarResizer: document.querySelector('#sidebarResizer'),
    sidebarBackdrop: document.querySelector('#sidebarBackdrop'),
    monthSelect: document.querySelector('#monthSelect'),
    fileList: document.querySelector('#fileList'),
    fileSearch: document.querySelector('#fileSearch'),
    welcomePanel: document.querySelector('#welcomePanel'),
    documentPanel: document.querySelector('#documentPanel'),
    documentPath: document.querySelector('#documentPath'),
    documentTitle: document.querySelector('#documentTitle'),
    segmentCount: document.querySelector('#segmentCount'),
    draftBadge: document.querySelector('#draftBadge'),
    metaTotalCount: document.querySelector('#metaTotalCount'),
    metaBothCount: document.querySelector('#metaBothCount'),
    metaPlayedOnlyCount: document.querySelector('#metaPlayedOnlyCount'),
    metaEditedOnlyCount: document.querySelector('#metaEditedOnlyCount'),
    metaNoneCount: document.querySelector('#metaNoneCount'),
    editorRoot: document.querySelector('#editorRoot'),
    saveButton: document.querySelector('#saveButton'),
    savePlayedButton: document.querySelector('#savePlayedButton'),
    saveStatus: document.querySelector('#saveStatus'),
    settingsButton: document.querySelector('#settingsButton'),
    settingsDialog: document.querySelector('#settingsDialog'),
    patInput: document.querySelector('#patInput'),
    settingsMessage: document.querySelector('#settingsMessage'),
    clearPatButton: document.querySelector('#clearPatButton'),
    testPatButton: document.querySelector('#testPatButton'),
    saveSettingsButton: document.querySelector('#saveSettingsButton'),
    draftDialog: document.querySelector('#draftDialog'),
    draftMessage: document.querySelector('#draftMessage'),
    conflictDialog: document.querySelector('#conflictDialog'),
    conflictPreview: document.querySelector('#conflictPreview'),
    reloadRemoteButton: document.querySelector('#reloadRemoteButton'),
    forceSaveButton: document.querySelector('#forceSaveButton'),
    opusWarning: document.querySelector('#opusWarning'),
    conflictBanner: document.querySelector('#conflictBanner'),
    audioPlayer: document.querySelector('#audioPlayer'),
    audioTitle: document.querySelector('#audioTitle'),
    audioRange: document.querySelector('#audioRange'),
    playbackRate: document.querySelector('#playbackRate'),
    stopAtRangeEnd: document.querySelector('#stopAtRangeEnd'),
    segmentTemplate: document.querySelector('#segmentTemplate'),
    miniPlayer: document.querySelector('#miniPlayer'),
    miniPlayerHandle: document.querySelector('#miniPlayerHandle'),
    miniPlayerHide: document.querySelector('#miniPlayerHide'),
    miniPlayerExpand: document.querySelector('#miniPlayerExpand'),
    miniPlayerToggle: document.querySelector('#miniPlayerToggle'),
    miniPlayerCurrent: document.querySelector('#miniPlayerCurrent'),
    miniPlayerDuration: document.querySelector('#miniPlayerDuration'),
    playerToggle: document.querySelector('#playerToggle'),
    seekBar: document.querySelector('#seekBar'),
    setStartButton: document.querySelector('#setStartButton'),
    setEndButton: document.querySelector('#setEndButton'),
    undoButton: document.querySelector('#undoButton'),
    redoButton: document.querySelector('#redoButton'),
    discardDraftButton: document.querySelector('#discardDraftButton'),
    loadRemoteButton: document.querySelector('#loadRemoteButton'),
    loadDraftButton: document.querySelector('#loadDraftButton'),
};

const audio = createAudioController({
    audio: els.audioPlayer,
    titleEl: els.audioTitle,
    rangeEl: els.audioRange,
    rateSelect: els.playbackRate,
    stopCheckbox: els.stopAtRangeEnd,
});

const mobileDockQuery = window.matchMedia('(max-width: 900px)');

bootstrap();

async function bootstrap() {
    els.monthSelect.innerHTML = MONTHS.map((m) => `<option value="${m}">${m}</option>`).join('');
    bindEvents();
    setupMiniPlayer();
    setupSidebarControls();
    applyPrefs();
    const savedMonth = MONTHS.includes(state.prefs.lastMonth) ? state.prefs.lastMonth : MONTHS[0];
    const savedSessionId = state.prefs.lastSessionId;
    await loadMonth(savedMonth);
    if (
        savedSessionId
        && state.map?.sessions?.some((session) => session.session_id === savedSessionId)
    ) {
        selectSession(savedSessionId);
    }
}

function bindEvents() {
    els.monthSelect.addEventListener('change', () => {
        state.prefs.lastSessionId = null;
        setPrefs({ lastSessionId: null });
        loadMonth(els.monthSelect.value);
    });
    els.fileSearch.addEventListener('input', renderSessionList);
    els.saveButton.addEventListener('click', () => saveCurrentMap());
    els.savePlayedButton?.addEventListener('click', () => saveCurrentMap({ reason: 'played' }));
    els.settingsButton.addEventListener('click', () => openSettings());
    els.saveSettingsButton.addEventListener('click', () => {
        setPat(els.patInput.value);
    });
    els.clearPatButton.addEventListener('click', () => {
        clearPat();
        els.patInput.value = '';
        els.settingsMessage.textContent = 'PAT 已移除。';
    });
    els.testPatButton.addEventListener('click', async () => {
        setPat(els.patInput.value);
        els.settingsMessage.textContent = '正在測試...';
        try {
            const user = await testToken();
            els.settingsMessage.textContent = `PAT 可用：${user.login}`;
        } catch (error) {
            els.settingsMessage.textContent = `PAT 測試失敗：${error.message}`;
        }
    });
    els.playbackRate.addEventListener('change', () => {
        setPrefs({ playbackRate: Number(els.playbackRate.value) });
    });
    els.stopAtRangeEnd.addEventListener('change', () => {
        setPrefs({ stopAtRangeEnd: els.stopAtRangeEnd.checked });
    });
    els.playerToggle?.addEventListener('click', () => {
        setMiniPlayerHidden(!state.prefs.miniPlayerHidden);
    });
    els.miniPlayerHide?.addEventListener('click', () => {
        setMiniPlayerHidden(true);
    });
    els.miniPlayerExpand?.addEventListener('click', () => {
        setMiniPlayerExpanded(!state.prefs.miniPlayerExpanded);
    });
    els.undoButton?.addEventListener('click', () => undoEdit());
    els.redoButton?.addEventListener('click', () => redoEdit());
    els.reloadRemoteButton?.addEventListener('click', async (event) => {
        event.preventDefault();
        els.conflictDialog.close();
        await loadMonth(state.month, { forceRemote: true });
    });
    els.forceSaveButton?.addEventListener('click', async (event) => {
        event.preventDefault();
        els.conflictDialog.close();
        await saveCurrentMap({ force: true });
    });
    window.addEventListener('beforeunload', (event) => {
        if (!state.dirty) return;
        event.preventDefault();
        event.returnValue = '';
    });
}

function applyPrefs() {
    audio.setPlaybackRate(state.prefs.playbackRate);
    audio.setStopAtRangeEnd(state.prefs.stopAtRangeEnd);
    els.opusWarning.classList.toggle('hidden', audio.supportsOpus);
    applyMiniPlayerVisibility();
    applySidebarPrefs();
    if (isMobileDock() && !state.sessionId) {
        setSidebarOpen(true);
    }
}

function applySidebarPrefs() {
    const width = clamp(Number(state.prefs.sidebarWidth) || 320, 200, sidebarMaxWidth());
    els.app.style.setProperty('--sidebar-width', `${width}px`);
    els.app.classList.toggle('sidebar-collapsed', state.prefs.sidebarCollapsed === true);
    updateSidebarToggleLabel();
}

function sidebarMaxWidth() {
    return Math.min(600, Math.max(280, Math.floor(window.innerWidth * 0.6)));
}

function updateSidebarToggleLabel() {
    if (!els.sidebarToggle) return;
    const mobile = isMobileDock();
    const open = mobile
        ? els.app.classList.contains('sidebar-open')
        : !els.app.classList.contains('sidebar-collapsed');
    els.sidebarToggle.setAttribute('aria-expanded', String(open));
    if (els.sidebarToggleIcon) {
        els.sidebarToggleIcon.textContent = mobile ? '☰' : (open ? '⟨' : '☰');
    }
    els.sidebarToggle.title = open ? '隱藏檔案列表' : '顯示檔案列表';
}

function setSidebarOpen(open) {
    const next = Boolean(open);
    els.app.classList.toggle('sidebar-open', next);
    if (els.sidebarBackdrop) els.sidebarBackdrop.hidden = !next;
    updateSidebarToggleLabel();
}

function applyMiniPlayerVisibility() {
    const hidden = state.prefs.miniPlayerHidden === true;
    els.miniPlayer?.classList.toggle('hidden', hidden);
    if (els.playerToggle) {
        const text = hidden ? '顯示播放器' : '隱藏播放器';
        const label = els.playerToggle.querySelector('.btn-label');
        if (label) label.textContent = text; else els.playerToggle.textContent = text;
        els.playerToggle.setAttribute('aria-pressed', String(!hidden));
        els.playerToggle.setAttribute('aria-label', text);
        els.playerToggle.title = text;
    }
    applyMiniPlayerExpanded();
    updateMiniPlayerHeight();
}

function setMiniPlayerHidden(hidden) {
    const next = Boolean(hidden);
    if (state.prefs.miniPlayerHidden === next) return;
    state.prefs.miniPlayerHidden = next;
    setPrefs({ miniPlayerHidden: next });
    applyMiniPlayerVisibility();
}

function isMobileDock() {
    return mobileDockQuery.matches;
}

function applyMiniPlayerExpanded() {
    if (!els.miniPlayer) return;
    const expanded = state.prefs.miniPlayerExpanded === true;
    els.miniPlayer.classList.toggle('mini-player--expanded', expanded);
    if (els.miniPlayerExpand) {
        els.miniPlayerExpand.textContent = expanded ? '▾' : '▴';
        els.miniPlayerExpand.setAttribute('aria-expanded', String(expanded));
        els.miniPlayerExpand.setAttribute('aria-label', expanded ? '收合播放器' : '展開播放器');
    }
}

function setMiniPlayerExpanded(expanded) {
    const next = Boolean(expanded);
    state.prefs.miniPlayerExpanded = next;
    setPrefs({ miniPlayerExpanded: next });
    applyMiniPlayerExpanded();
    updateMiniPlayerHeight();
}

function updateMiniPlayerHeight() {
    if (!els.app || !els.miniPlayer) return;
    const docked = isMobileDock()
        && state.prefs.miniPlayerHidden !== true
        && !els.miniPlayer.classList.contains('hidden');
    const height = docked ? els.miniPlayer.offsetHeight : 0;
    els.app.style.setProperty('--mini-player-height', `${height}px`);
}

function setupSidebarControls() {
    els.sidebarToggle.addEventListener('click', () => {
        if (isMobileDock()) {
            setSidebarOpen(!els.app.classList.contains('sidebar-open'));
            return;
        }
        const collapsed = !els.app.classList.contains('sidebar-collapsed');
        els.app.classList.toggle('sidebar-collapsed', collapsed);
        state.prefs.sidebarCollapsed = collapsed;
        setPrefs({ sidebarCollapsed: collapsed });
        updateSidebarToggleLabel();
    });

    els.sidebarBackdrop?.addEventListener('click', () => setSidebarOpen(false));

    let resizing = false;
    let startX = 0;
    let startWidth = 0;

    els.sidebarResizer.addEventListener('pointerdown', (event) => {
        if (els.app.classList.contains('sidebar-collapsed')) return;
        resizing = true;
        startX = event.clientX;
        startWidth = els.sidebar.getBoundingClientRect().width;
        els.sidebarResizer.setPointerCapture(event.pointerId);
        els.sidebarResizer.classList.add('dragging');
        document.body.classList.add('resizing-sidebar');
        event.preventDefault();
    });

    els.sidebarResizer.addEventListener('pointermove', (event) => {
        if (!resizing) return;
        const next = clamp(startWidth + (event.clientX - startX), 200, sidebarMaxWidth());
        els.app.style.setProperty('--sidebar-width', `${next}px`);
    });

    const stopResize = (event) => {
        if (!resizing) return;
        resizing = false;
        els.sidebarResizer.classList.remove('dragging');
        document.body.classList.remove('resizing-sidebar');
        try { els.sidebarResizer.releasePointerCapture(event.pointerId); } catch { /* ignore */ }
        const raw = els.app.style.getPropertyValue('--sidebar-width');
        const width = parseInt(raw, 10);
        if (Number.isFinite(width)) {
            state.prefs.sidebarWidth = width;
            setPrefs({ sidebarWidth: width });
        }
    };

    els.sidebarResizer.addEventListener('pointerup', stopResize);
    els.sidebarResizer.addEventListener('pointercancel', stopResize);

    window.addEventListener('resize', () => {
        const current = parseInt(els.app.style.getPropertyValue('--sidebar-width'), 10) || 320;
        const max = sidebarMaxWidth();
        if (current > max) {
            els.app.style.setProperty('--sidebar-width', `${max}px`);
        }
        handleDockModeChange();
    });
}

function mapPath(month) {
    return `tool/word2ebook/data/audio_map/${month}.json`;
}

function serializeMap(map) {
    return `${JSON.stringify(map, null, 2)}\n`;
}

function cloneMap(map) {
    return JSON.parse(JSON.stringify(map));
}

/** Round to millisecond precision used by labels / inject. */
function roundSeconds(value) {
    if (value == null || !Number.isFinite(value)) return null;
    return Math.round(Math.max(0, value) * 1000) / 1000;
}

/**
 * Parse a time marker line. Accepts fullwidth/halfwidth colon and optional spaces
 * (qa parser only matches fullwidth `：`).
 */
function parseTimeMarkerValue(text) {
    const fromQa = parseRanges(text || '')[0];
    if (fromQa) return fromQa;
    const match = String(text || '').match(
        /(?:開場時間|時間)\s*[:：]\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})/,
    );
    if (!match) return null;
    const startLabel = match[1].replace(',', '.');
    const endLabel = match[2].replace(',', '.');
    return {
        label: `${startLabel} - ${endLabel}`,
        startLabel,
        endLabel,
        start: timecodeToSeconds(startLabel),
        end: timecodeToSeconds(endLabel),
    };
}

/** Write start/end + labels onto a map item from a parsed range. */
function applyRangeToItem(item, range, { markManual = true } = {}) {
    const start = roundSeconds(range.start);
    const end = roundSeconds(range.end);
    item.start = start;
    item.end = end;
    item.start_label = start != null ? secondsToTimecode(start) : null;
    item.end_label = end != null ? secondsToTimecode(end) : null;
    if (markManual || item.status === 'missing') item.status = 'manual';
}

/** Keep numeric seconds and label strings in sync for one item. */
function normalizeItemTimes(item) {
    if (!item || typeof item !== 'object') return;
    let start = item.start;
    let end = item.end;
    if ((start == null || end == null) && item.start_label && item.end_label) {
        start = timecodeToSeconds(String(item.start_label).replace(',', '.'));
        end = timecodeToSeconds(String(item.end_label).replace(',', '.'));
    }
    if (start == null || end == null || !Number.isFinite(start) || !Number.isFinite(end)) {
        return;
    }
    start = roundSeconds(start);
    end = roundSeconds(end);
    if (end < start) end = start;
    item.start = start;
    item.end = end;
    item.start_label = secondsToTimecode(start);
    item.end_label = secondsToTimecode(end);
    if (item.status === 'missing') item.status = 'manual';
}

function normalizeMapTimes(map) {
    for (const session of map?.sessions || []) {
        if (session.opening) normalizeItemTimes(session.opening);
        for (const seg of session.segments || []) normalizeItemTimes(seg);
    }
    return map;
}

/**
 * Pull times from visible marker inputs into state.map (so Save works even if
 * the input was edited but not blurred / change-committed yet).
 * @returns {{ ok: true } | { ok: false, message: string }}
 */
function flushEditorTimesIntoMap() {
    const items = sessionItems();
    for (const card of els.editorRoot.querySelectorAll('.segment-card')) {
        const idx = Number(card.dataset.segmentIndex);
        const entry = items[idx];
        const input = card.querySelector('.marker-input');
        if (!entry || !input) continue;
        const range = parseTimeMarkerValue(input.value);
        if (!range || !Number.isFinite(range.start) || !Number.isFinite(range.end)) {
            const label = entry.kind === 'opening' ? '開場' : `第 ${entry.number} 段`;
            return {
                ok: false,
                message: `${label} 時間格式無效，請使用 00:00:00.000 - 00:00:00.000`,
            };
        }
        const hadTimes = entry.item.start != null && entry.item.end != null;
        const nextStart = roundSeconds(range.start);
        const nextEnd = roundSeconds(range.end);
        // Placeholder "00:00:00.000 - 00:00:00.000" for unset items must not be written.
        if (!hadTimes && nextStart === 0 && nextEnd === 0) {
            continue;
        }
        const prevStart = roundSeconds(entry.item.start);
        const prevEnd = roundSeconds(entry.item.end);
        const changed = prevStart !== nextStart || prevEnd !== nextEnd;
        applyRangeToItem(entry.item, range, { markManual: changed || entry.item.status === 'manual' });
        input.value = formatTimeMarker(entry.item, entry.kind);
        input.dataset.startTc = entry.item.start_label;
        input.dataset.endTc = entry.item.end_label;
        const playButton = input.closest('.marker-line')?.querySelector('.play-range');
        if (playButton) updatePlayButton(playButton, input.value, idx, entry.title);
    }
    normalizeMapTimes(state.map);
    return { ok: true };
}

function prepareMapForSave() {
    const flush = flushEditorTimesIntoMap();
    if (!flush.ok) return flush;
    normalizeMapTimes(state.map);
    return { ok: true };
}

function currentSession() {
    return state.map?.sessions?.find((s) => s.session_id === state.sessionId) || null;
}

function originalSession() {
    return state.originalMap?.sessions?.find((s) => s.session_id === state.sessionId) || null;
}

function sessionItems() {
    const session = currentSession();
    if (!session) return [];
    const items = [];
    if (session.opening) {
        items.push({ kind: 'opening', item: session.opening, number: '開場', title: '開場' });
    }
    for (const seg of session.segments || []) {
        const q = seg.q_text || seg.q_preview || '';
        const title = seg.questioner ? `${seg.questioner}：${q}` : q;
        items.push({
            kind: 'segment',
            item: seg,
            number: String(seg.index),
            title: title || `第 ${seg.index} 題`,
        });
    }
    return items;
}

async function loadMonth(month, { forceRemote = false } = {}) {
    if (state.dirty && !forceRemote) {
        const ok = window.confirm('目前有未儲存變更，確定要切換月份並丟棄嗎？');
        if (!ok) {
            els.monthSelect.value = state.month;
            return;
        }
    }

    setStatus('正在載入…', 'loading');
    state.month = month;
    els.monthSelect.value = month;
    state.sessionId = null;
    state.activeSegmentIndex = null;
    state.usingDraft = false;

    const path = mapPath(month);
    const draft = forceRemote ? null : getDraft(path);

    try {
        // Prefer local working-tree JSON (has PDF answer_text). GitHub is only
        // used for save SHA / optional force-remote pull.
        let text;
        let sha = '';
        let localMap = null;

        const localRes = await fetch(`${MAP_BASE}${month}.json`, { cache: 'no-store' });
        if (!localRes.ok) throw new Error(`無法載入 ${month}.json (${localRes.status})`);
        const localText = await localRes.text();
        localMap = JSON.parse(localText);
        text = localText;

        try {
            const remote = await getFile(path);
            sha = remote.sha;
            if (forceRemote) {
                text = remote.text;
            }
        } catch {
            // Public fetch / no PAT: save will re-fetch sha later.
        }

        if (draft && draft.text && draft.text !== text) {
            const choice = await askDraftChoice(path, draft);
            if (choice === 'draft') {
                text = draft.text;
                sha = draft.sha || sha;
                state.usingDraft = true;
            } else if (choice === 'discard') {
                clearDraft(path);
            }
        }

        let map = JSON.parse(text);
        // Drafts / GitHub copies may predate answer_text — overlay PDF text from local.
        map = mergePdfTextFrom(map, localMap);
        state.map = map;
        state.originalMap = cloneMap(map);
        state.currentSha = sha;
        state.dirty = false;
        state.draftPaths = listDraftPaths();
        resetHistory();
        state.prefs.lastMonth = month;
        setPrefs({ lastMonth: month });
        renderSessionList();
        els.welcomePanel.classList.remove('hidden');
        els.documentPanel.classList.add('hidden');
        els.editorRoot.innerHTML = '';
        els.saveButton.disabled = true;
        els.draftBadge.classList.toggle('hidden', !state.usingDraft);
        setStatus(`已載入 ${month}（${state.map.sessions?.length || 0} sessions）`, 'ok');
    } catch (error) {
        els.fileList.innerHTML = `<div class="empty-state error">載入失敗：${escapeHtml(error.message)}</div>`;
        setStatus(`載入失敗：${error.message}`, 'error');
    }
}

/** Copy PDF question/answer fields from `source` onto `target` (by session/stable_key). */
function mergePdfTextFrom(target, source) {
    if (!target || !source) return target;
    const srcById = new Map((source.sessions || []).map((s) => [s.session_id, s]));
    const out = cloneMap(target);
    for (const session of out.sessions || []) {
        const src = srcById.get(session.session_id);
        if (!src) continue;
        if (src.opening) {
            session.opening = session.opening || {};
            for (const k of ['text', 'text_preview']) {
                if (src.opening[k]) session.opening[k] = src.opening[k];
            }
        }
        const srcSegs = new Map(
            (src.segments || []).map((seg) => [seg.stable_key || `#${seg.index}`, seg]),
        );
        for (const seg of session.segments || []) {
            const ss = srcSegs.get(seg.stable_key || `#${seg.index}`);
            if (!ss) continue;
            for (const k of ['q_text', 'q_preview', 'answer_text', 'answer_preview', 'questioner', 'question_time']) {
                if (ss[k] != null && ss[k] !== '') seg[k] = ss[k];
            }
        }
    }
    return out;
}

function askDraftChoice(path, draft) {
    return new Promise((resolve) => {
        const date = draft.savedAt ? new Date(draft.savedAt).toLocaleString('zh-TW') : '未知時間';
        els.draftMessage.textContent = `${path} 有本機草稿，最後暫存時間：${date}。`;
        const onClose = () => {
            els.draftDialog.removeEventListener('close', onClose);
            resolve(els.draftDialog.returnValue || 'remote');
        };
        els.draftDialog.addEventListener('close', onClose);
        els.draftDialog.showModal();
    });
}

function renderSessionList() {
    const query = (els.fileSearch.value || '').trim().toLowerCase();
    els.fileList.innerHTML = '';
    const sessions = state.map?.sessions || [];
    let shown = 0;
    for (const session of sessions) {
        const label = `${session.date} ${session.source}`;
        if (query && !label.toLowerCase().includes(query) && !(session.session_id || '').toLowerCase().includes(query)) {
            continue;
        }
        shown += 1;
        const stats = countSessionMeta(session);
        const row = document.createElement('div');
        row.className = 'file-row';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'file-item' + (session.session_id === state.sessionId ? ' active' : '');
        btn.innerHTML = `
            <span class="draft-dot hidden"></span>
            <div class="file-item-body">
                <span class="file-name">${escapeHtml(label)}</span>
                <span class="file-stats">✓${stats.matched} · ✗${stats.missing} · ${stats.total} 題 · 完成 ${stats.completed}</span>
            </div>
        `;
        btn.addEventListener('click', () => selectSession(session.session_id));
        row.append(btn);
        els.fileList.append(row);
    }
    if (!shown) {
        els.fileList.innerHTML = '<div class="empty-state">沒有符合的 session</div>';
    }
}

function countSessionMeta(session) {
    const items = [];
    if (session.opening) items.push(session.opening);
    items.push(...(session.segments || []));
    let matched = 0;
    let missing = 0;
    let completed = 0;
    let both = 0;
    let played = 0;
    let edited = 0;
    let none = 0;
    for (const item of items) {
        if (item.start != null && item.status !== 'missing') matched += 1;
        else missing += 1;
        const hasPlayed = Boolean(item?.meta?.lastPlayed);
        const hasEdited = Boolean(item?.meta?.lastEdited);
        // 「完成」= 聽過即可（不需再校過）
        if (hasPlayed) completed += 1;
        if (hasPlayed && hasEdited) both += 1;
        else if (hasPlayed) played += 1;
        else if (hasEdited) edited += 1;
        else none += 1;
    }
    return {
        matched,
        missing,
        total: session.segments?.length || 0,
        completed,
        both,
        played,
        edited,
        none,
        all: items.length,
    };
}

function selectSession(sessionId) {
    state.sessionId = sessionId;
    state.activeSegmentIndex = null;
    state.prefs.lastMonth = state.month;
    state.prefs.lastSessionId = sessionId;
    setPrefs({ lastMonth: state.month, lastSessionId: sessionId });
    setActiveSegment(null);
    renderSessionList();
    els.fileList.querySelector('.file-item.active')?.scrollIntoView({ block: 'nearest' });
    renderEditor();
    if (isMobileDock()) setSidebarOpen(false);
}

function renderEditor() {
    const session = currentSession();
    if (!session) return;
    els.welcomePanel.classList.add('hidden');
    els.documentPanel.classList.remove('hidden');
    els.documentPath.textContent = mapPath(state.month);
    els.documentTitle.textContent = `${session.date} ${session.source}`;
    els.segmentCount.textContent = session.audio_file || '';
    els.conflictBanner.classList.add('hidden');

    const items = sessionItems();
    updateMetaStrip(items);
    els.editorRoot.innerHTML = '';
    items.forEach((entry, index) => {
        els.editorRoot.append(renderSegmentCard(entry, index));
    });
    recomputeDirty();
    updateHistoryButtons();
}

function updateMetaStrip(items) {
    let completed = 0;
    let played = 0;
    let edited = 0;
    let none = 0;
    for (const { item } of items) {
        const hasPlayed = Boolean(item?.meta?.lastPlayed);
        const hasEdited = Boolean(item?.meta?.lastEdited);
        // 「完成」= 聽過即可
        if (hasPlayed) completed += 1;
        if (hasPlayed && !hasEdited) played += 1;
        else if (!hasPlayed && hasEdited) edited += 1;
        else if (!hasPlayed && !hasEdited) none += 1;
    }
    els.metaTotalCount.textContent = String(items.length);
    els.metaBothCount.textContent = String(completed);
    els.metaPlayedOnlyCount.textContent = String(played);
    els.metaEditedOnlyCount.textContent = String(edited);
    els.metaNoneCount.textContent = String(none);
}

function renderSegmentCard(entry, segmentIndex) {
    const { item, number, title, kind } = entry;
    const node = els.segmentTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.segmentIndex = String(segmentIndex);
    node.dataset.kind = kind;
    node.querySelector('.segment-number').textContent =
        kind === 'opening' ? '開場' : `第 ${number} 段`;

    const titleField = node.querySelector('.segment-title');
    titleField.value = title;
    titleField.readOnly = true;
    titleField.dataset.locked = '1';
    queueMicrotask(() => autoGrow(titleField, { allowShrink: true }));

    updateSegmentMetaChips(node, item);
    node.querySelector('.segment-edit-toggle')?.addEventListener('click', () => toggleSegmentEditing(node));
    node.querySelector('.reset-segment').addEventListener('click', () => resetSegment(segmentIndex));
    for (const button of node.querySelectorAll('.seg-meta-clear')) {
        button.addEventListener('click', () => clearSegmentMeta(segmentIndex, button.dataset.field));
    }
    node.querySelector('.copy-segment')?.addEventListener('click', (event) => {
        copySegmentAnswer(segmentIndex, event.currentTarget);
    });

    const lockInput = node.querySelector('.lock-input');
    if (lockInput) {
        lockInput.checked = Boolean(item.locked);
        lockInput.addEventListener('change', () => {
            commitHistory();
            item.locked = lockInput.checked;
            onSegmentEdit(segmentIndex);
            commitHistory();
        });
    }

    const body = node.querySelector('.segment-body');

    // Time marker line (qa style)
    const timeLine = document.createElement('div');
    timeLine.className = 'marker-line';
    const timeInput = document.createElement('input');
    timeInput.type = 'text';
    timeInput.className = 'marker-input';
    timeInput.spellcheck = false;
    timeInput.value = formatTimeMarker(item, kind);
    timeInput.setAttribute('aria-label', '段落時間（格式：時間：HH:MM:SS.mmm - HH:MM:SS.mmm）');
    timeInput.title = '格式：時間：HH:MM:SS.mmm - HH:MM:SS.mmm';
    const initRange = parseTimeMarkerValue(timeInput.value);
    if (initRange) {
        timeInput.dataset.startTc = initRange.startLabel;
        timeInput.dataset.endTc = initRange.endLabel;
    }
    const playButton = document.createElement('button');
    playButton.type = 'button';
    playButton.className = 'button button-secondary play-range';
    updatePlayButton(playButton, timeInput.value, segmentIndex, title);
    timeInput.addEventListener('change', () => {
        const range = parseTimeMarkerValue(timeInput.value);
        if (!range) {
            setStatus('時間格式無效，請使用 時間：00:00:00.000 - 00:00:00.000', 'error');
            timeInput.value = formatTimeMarker(item, kind);
            return;
        }
        const startChanged = range.startLabel !== timeInput.dataset.startTc;
        const endChanged = range.endLabel !== timeInput.dataset.endTc;
        commitHistory();
        applyRangeToItem(item, range);
        timeInput.value = formatTimeMarker(item, kind);
        timeInput.dataset.startTc = item.start_label;
        timeInput.dataset.endTc = item.end_label;
        if (startChanged) setSegmentEdge(segmentIndex - 1, 'end', range.start, { markEdited: false });
        if (endChanged) setSegmentEdge(segmentIndex + 1, 'start', range.end, { markEdited: false });
        updatePlayButton(playButton, timeInput.value, segmentIndex, title);
        onSegmentEdit(segmentIndex);
        commitHistory();
        renderSessionList();
    });
    timeInput.addEventListener('input', () => {
        updatePlayButton(playButton, timeInput.value, segmentIndex, title);
    });
    timeLine.append(timeInput, playButton);
    body.append(timeLine);

    // PDF answer (or opening text) — read-only block (div, not textarea) so
    // mouse wheel scrolls the page instead of an inner scrollbar.
    const answer = kind === 'opening'
        ? (item.text || item.text_preview || '')
        : (item.answer_text || item.answer_preview || '');
    const answerEl = document.createElement('div');
    answerEl.className = 'editor-textarea answer-body';
    answerEl.setAttribute('role', 'region');
    answerEl.setAttribute('aria-label', kind === 'opening' ? '開場文字（PDF）' : '回答（PDF 校對稿）');
    if (answer) {
        answerEl.textContent = answer;
    } else {
        answerEl.classList.add('answer-body--empty');
        answerEl.textContent = kind === 'opening'
            ? '（此段開場文字缺失，請重新載入本地 audio_map JSON）'
            : '（此段尚無 PDF 回答文字，請重新載入本地 audio_map JSON）';
    }
    body.append(answerEl);

    applySegmentEditability(node);
    return node;
}

function formatTimeMarker(item, kind) {
    const prefix = kind === 'opening' ? '開場時間' : '時間';
    const start = item.start != null ? secondsToTimecode(roundSeconds(item.start)) : '00:00:00.000';
    const end = item.end != null ? secondsToTimecode(roundSeconds(item.end)) : '00:00:00.000';
    return `${prefix}：${start} - ${end}`;
}

function updatePlayButton(button, markerText, segmentIndex, title) {
    const range = parseTimeMarkerValue(markerText);
    if (!range) {
        button.textContent = '▶ 時間格式無效';
        button.disabled = true;
        button.onclick = null;
        return;
    }
    button.disabled = false;
    button.textContent = `▶ ${range.label}`;
    button.onclick = async () => {
        const session = currentSession();
        if (!session?.audio_file) {
            setStatus('此 session 沒有音檔', 'error');
            return;
        }
        try {
            setMiniPlayerHidden(false);
            await audio.playRange(session.audio_file, range, title);
            if (isSegmentEditable(segmentIndex)) onSegmentPlayed(segmentIndex);
            setActiveSegment(segmentIndex);
        } catch (error) {
            setStatus(`播放失敗：${error.message}`, 'error');
        }
    };
}

function setActiveSegment(index) {
    state.activeSegmentIndex = index == null ? null : index;
    const disabled = state.activeSegmentIndex == null;
    if (els.setStartButton) els.setStartButton.disabled = disabled;
    if (els.setEndButton) els.setEndButton.disabled = disabled;
}

function playerCurrentTime() {
    const player = els.audioPlayer;
    if (!player || !player.src) return null;
    const t = player.currentTime;
    return Number.isFinite(t) ? t : null;
}

function setSegmentEdge(segmentIndex, edge, seconds, { markEdited = true } = {}) {
    const items = sessionItems();
    const entry = items[segmentIndex];
    if (!entry || seconds == null || !Number.isFinite(seconds)) return false;
    const item = entry.item;
    const value = roundSeconds(seconds);
    if (edge === 'start') {
        item.start = value;
        item.start_label = secondsToTimecode(value);
        if (item.end == null || item.end < value) {
            item.end = value;
            item.end_label = secondsToTimecode(value);
        }
    } else {
        item.end = value;
        item.end_label = secondsToTimecode(value);
        if (item.start == null || item.start > value) {
            item.start = value;
            item.start_label = secondsToTimecode(value);
        }
    }
    item.status = 'manual';
    normalizeItemTimes(item);
    const card = els.editorRoot.querySelector(`.segment-card[data-segment-index="${segmentIndex}"]`);
    const input = card?.querySelector('.marker-input');
    if (input) {
        input.value = formatTimeMarker(item, entry.kind);
        input.dataset.startTc = item.start_label;
        input.dataset.endTc = item.end_label;
        const playButton = input.closest('.marker-line')?.querySelector('.play-range');
        if (playButton) updatePlayButton(playButton, input.value, segmentIndex, entry.title);
    }
    if (markEdited) onSegmentEdit(segmentIndex);
    else recomputeDirty();
    return true;
}

function applyPlayerTime(segmentIndex, edge, seconds) {
    commitHistory();
    if (!setSegmentEdge(segmentIndex, edge, seconds)) return;
    if (edge === 'start') setSegmentEdge(segmentIndex - 1, 'end', seconds, { markEdited: false });
    if (edge === 'end') setSegmentEdge(segmentIndex + 1, 'start', seconds, { markEdited: false });
    const entry = sessionItems()[segmentIndex];
    const label = edge === 'start' ? '起始' : '結束';
    setStatus(`已將第 ${entry?.number || segmentIndex + 1} 段${label}時間設為 ${secondsToTimecode(seconds)}`, 'ok');
    commitHistory();
    renderSessionList();
}

function applyPlayerTimeSingle(segmentIndex, edge, seconds) {
    commitHistory();
    if (!setSegmentEdge(segmentIndex, edge, seconds)) return;
    const entry = sessionItems()[segmentIndex];
    const label = edge === 'start' ? '起始' : '結束';
    const note = edge === 'start' ? '（未連動上一段結束）' : '（未連動下一段起始）';
    setStatus(`已將第 ${entry?.number || segmentIndex + 1} 段${label}時間設為 ${secondsToTimecode(seconds)}${note}`, 'ok');
    commitHistory();
    renderSessionList();
}

function toggleSegmentEditing(card) {
    if (!card) return;
    const editing = !card.classList.contains('editing');
    card.classList.toggle('editing', editing);
    const toggle = card.querySelector('.segment-edit-toggle');
    if (toggle) {
        toggle.setAttribute('aria-expanded', String(editing));
        toggle.textContent = editing ? '✓' : '✎';
        toggle.setAttribute('aria-label', editing ? '完成編輯這一段' : '編輯這一段');
        toggle.title = editing ? '完成編輯（收合控制項）' : '編輯這一段';
    }
    applySegmentEditability(card);
}

function applySegmentEditability(card) {
    if (!card) return;
    const editable = !isMobileDock() || card.classList.contains('editing');
    for (const field of card.querySelectorAll('.segment-title, .marker-input')) {
        if (field.dataset.locked === '1') {
            field.readOnly = true;
        } else {
            field.readOnly = !editable;
        }
    }
}

function isSegmentEditable(segmentIndex) {
    if (!isMobileDock()) return true;
    const card = els.editorRoot.querySelector(`.segment-card[data-segment-index="${segmentIndex}"]`);
    return Boolean(card && card.classList.contains('editing'));
}

function ensureMeta(item) {
    if (!item.meta || typeof item.meta !== 'object') item.meta = {};
    return item.meta;
}

function nowStamp() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function onSegmentPlayed(segmentIndex) {
    const entry = sessionItems()[segmentIndex];
    if (!entry) return;
    ensureMeta(entry.item).lastPlayed = nowStamp();
    refreshSegmentMetaChips(segmentIndex);
    updateMetaStrip(sessionItems());
    scheduleDraft();
    recomputeDirty();
    renderSessionList();
}

function onSegmentEdit(segmentIndex) {
    const entry = sessionItems()[segmentIndex];
    if (!entry) return;
    ensureMeta(entry.item).lastEdited = nowStamp();
    refreshSegmentMetaChips(segmentIndex);
    updateMetaStrip(sessionItems());
    scheduleDraft();
    recomputeDirty();
}

function clearSegmentMeta(segmentIndex, field) {
    const entry = sessionItems()[segmentIndex];
    if (!entry) return;
    commitHistory();
    const meta = ensureMeta(entry.item);
    if (field === 'played') meta.lastPlayed = '';
    if (field === 'edited') meta.lastEdited = '';
    refreshSegmentMetaChips(segmentIndex);
    updateMetaStrip(sessionItems());
    setStatus(field === 'played' ? '已清除最後播放時間' : '已清除最後編輯時間', 'ok');
    commitHistory();
    renderSessionList();
}

function updateSegmentMetaChips(card, item) {
    const played = card.querySelector('.seg-meta-played');
    const edited = card.querySelector('.seg-meta-edited');
    const hasPlayed = Boolean(item?.meta?.lastPlayed);
    const hasEdited = Boolean(item?.meta?.lastEdited);
    if (played) played.textContent = item?.meta?.lastPlayed || '—';
    if (edited) edited.textContent = item?.meta?.lastEdited || '—';
    const clearPlayed = card.querySelector('.seg-meta-clear[data-field="played"]');
    const clearEdited = card.querySelector('.seg-meta-clear[data-field="edited"]');
    if (clearPlayed) clearPlayed.classList.toggle('hidden', !hasPlayed);
    if (clearEdited) clearEdited.classList.toggle('hidden', !hasEdited);
    let status = 'none';
    if (hasPlayed && hasEdited) status = 'both';
    else if (hasPlayed) status = 'played';
    else if (hasEdited) status = 'edited';
    card.dataset.status = status;
}

function refreshSegmentMetaChips(segmentIndex) {
    const card = els.editorRoot.querySelector(`.segment-card[data-segment-index="${segmentIndex}"]`);
    const entry = sessionItems()[segmentIndex];
    if (!card || !entry) return;
    updateSegmentMetaChips(card, entry.item);
}

function resetSegment(segmentIndex) {
    const session = currentSession();
    const orig = originalSession();
    if (!session || !orig) return;
    const items = sessionItems();
    const entry = items[segmentIndex];
    if (!entry) return;
    commitHistory();
    if (entry.kind === 'opening') {
        session.opening = cloneMap(orig.opening);
    } else {
        const idx = entry.item.index;
        const o = (orig.segments || []).find((s) => s.index === idx);
        if (!o) return;
        const pos = (session.segments || []).findIndex((s) => s.index === idx);
        if (pos >= 0) session.segments[pos] = cloneMap(o);
    }
    renderEditor();
    setStatus('已還原這一段', 'ok');
    commitHistory();
}

async function copySegmentAnswer(segmentIndex, button) {
    const entry = sessionItems()[segmentIndex];
    if (!entry) return;
    const text = entry.kind === 'opening'
        ? (entry.item.text || entry.item.text_preview || '')
        : (entry.item.answer_text || entry.item.answer_preview || '');
    try {
        await navigator.clipboard.writeText(text);
        const prev = button.textContent;
        button.textContent = '✓';
        setTimeout(() => { button.textContent = prev; }, 1200);
        setStatus('已複製回答', 'ok');
    } catch (error) {
        setStatus(`複製失敗：${error.message}`, 'error');
    }
}

function recomputeDirty() {
    const dirty = serializeMap(state.map) !== serializeMap(state.originalMap);
    state.dirty = dirty;
    els.saveButton.disabled = !dirty && !state.usingDraft;
    els.savePlayedButton?.classList.toggle('hidden', !dirty);
    els.draftBadge.classList.toggle('hidden', !state.usingDraft && !getDraft(mapPath(state.month)));
    for (const card of els.editorRoot.querySelectorAll('.segment-card')) {
        const dirtyMark = card.querySelector('.segment-dirty');
        if (!dirtyMark) continue;
        const idx = Number(card.dataset.segmentIndex);
        const cur = sessionItems()[idx]?.item;
        const origItems = (() => {
            const session = originalSession();
            if (!session) return [];
            const list = [];
            if (session.opening) list.push(session.opening);
            list.push(...(session.segments || []));
            return list;
        })();
        const orig = origItems[idx];
        const changed = JSON.stringify(cur) !== JSON.stringify(orig);
        dirtyMark.classList.toggle('hidden', !changed);
    }
    if (!dirty) setStatus(state.usingDraft ? '已載入本機草稿' : '沒有未存變更', 'ok');
    else setStatus('有未儲存變更', 'ok');
}

function scheduleDraft() {
    clearTimeout(state.draftTimer);
    state.draftTimer = setTimeout(() => {
        if (!state.map) return;
        // Best-effort: include any in-progress marker edits in the local draft.
        flushEditorTimesIntoMap();
        setDraft(mapPath(state.month), serializeMap(state.map), state.currentSha);
        state.draftPaths = listDraftPaths();
        els.draftBadge.classList.remove('hidden');
    }, 800);
}

function resetHistory() {
    history.undo = [];
    history.redo = [];
    history.committed = serializeMap(state.map);
    updateHistoryButtons();
}

function commitHistory() {
    clearTimeout(history.timer);
    if (!state.map) return;
    const snap = serializeMap(state.map);
    if (snap === history.committed) return;
    history.undo.push(history.committed);
    if (history.undo.length > HISTORY_LIMIT) history.undo.shift();
    history.committed = snap;
    history.redo = [];
    updateHistoryButtons();
    recomputeDirty();
    scheduleDraft();
}

function undoEdit() {
    if (!history.undo.length) return;
    history.redo.push(serializeMap(state.map));
    const prev = history.undo.pop();
    state.map = JSON.parse(prev);
    history.committed = prev;
    renderSessionList();
    if (state.sessionId) renderEditor();
    updateHistoryButtons();
    recomputeDirty();
}

function redoEdit() {
    if (!history.redo.length) return;
    history.undo.push(serializeMap(state.map));
    const next = history.redo.pop();
    state.map = JSON.parse(next);
    history.committed = next;
    renderSessionList();
    if (state.sessionId) renderEditor();
    updateHistoryButtons();
    recomputeDirty();
}

function updateHistoryButtons() {
    if (els.undoButton) els.undoButton.disabled = history.undo.length === 0;
    if (els.redoButton) els.redoButton.disabled = history.redo.length === 0;
}

async function saveCurrentMap({ force = false, reason = 'edit' } = {}) {
    if (!state.map) return;
    if (!getPat()) {
        openSettings();
        setStatus('請先設定 PAT', 'error');
        return;
    }
    const prepared = prepareMapForSave();
    if (!prepared.ok) {
        setStatus(prepared.message, 'error');
        return;
    }
    const path = mapPath(state.month);
    setStatus('上傳中…', 'loading');
    try {
        if (!state.currentSha) {
            try {
                const remote = await getFile(path);
                state.currentSha = remote.sha;
            } catch {
                // new file path unlikely
            }
        }
        // Clone + normalize again so the uploaded payload is self-consistent.
        const payload = normalizeMapTimes(cloneMap(state.map));
        const text = serializeMap(payload);
        const message = reason === 'played'
            ? `Update audio_map listen progress ${state.month}`
            : `Update audio_map ${state.month}`;
        const result = await putFile(path, text, state.currentSha, message, { force });
        state.currentSha = result.content?.sha || state.currentSha;
        state.map = payload;
        state.originalMap = cloneMap(payload);
        state.dirty = false;
        state.usingDraft = false;
        clearDraft(path);
        els.draftBadge.classList.add('hidden');
        resetHistory();
        if (state.sessionId) renderEditor();
        recomputeDirty();
        setStatus(`已存到 GitHub：${path}`, 'ok');
    } catch (error) {
        if (isConflict(error) && !force) {
            els.conflictPreview.textContent = error.message || '遠端版本衝突';
            els.conflictDialog.showModal();
            setStatus('遠端已更新，請選擇處理方式', 'error');
            return;
        }
        setStatus(error.message || String(error), 'error');
    }
}

function openSettings() {
    els.patInput.value = getPat();
    els.settingsMessage.textContent = '';
    els.settingsDialog.showModal();
}

function setStatus(message, kind = 'ok') {
    els.saveStatus.textContent = message || '';
    els.saveStatus.dataset.kind = kind;
}

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function autoGrow(field, { allowShrink = false } = {}) {
    if (!field) return;
    if (allowShrink) field.style.height = 'auto';
    field.style.height = `${field.scrollHeight}px`;
}

function formatClock(seconds) {
    if (!Number.isFinite(seconds)) return '00:00:00.000';
    return secondsToTimecode(Math.max(0, seconds));
}

function showContextMenu(x, y, items) {
    closeContextMenu();
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    for (const item of items) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = item.label;
        btn.addEventListener('click', () => {
            closeContextMenu();
            item.onSelect?.();
        });
        menu.append(btn);
    }
    menu.id = 'audioMapContextMenu';
    document.body.append(menu);
    const closer = (event) => {
        if (!menu.contains(event.target)) closeContextMenu();
    };
    setTimeout(() => {
        document.addEventListener('pointerdown', closer, { once: true });
        window.addEventListener('resize', closeContextMenu, { once: true });
    }, 0);
}

function closeContextMenu() {
    document.querySelector('#audioMapContextMenu')?.remove();
}

function setupMiniPlayer() {
    const player = els.audioPlayer;
    const mini = els.miniPlayer;
    const handle = els.miniPlayerHandle;
    const toggle = els.miniPlayerToggle;
    const currentEl = els.miniPlayerCurrent;
    const durationEl = els.miniPlayerDuration;
    const seekBar = els.seekBar;

    let dragging = false;
    let dragOffset = { x: 0, y: 0 };
    let seeking = false;

    restoreMiniPlayerPosition();
    applyMiniPlayerExpanded();

    if (typeof mobileDockQuery.addEventListener === 'function') {
        mobileDockQuery.addEventListener('change', handleDockModeChange);
    } else if (typeof mobileDockQuery.addListener === 'function') {
        mobileDockQuery.addListener(handleDockModeChange);
    }

    if (typeof ResizeObserver === 'function') {
        const observer = new ResizeObserver(() => updateMiniPlayerHeight());
        observer.observe(mini);
    }
    window.addEventListener('resize', updateMiniPlayerHeight);

    const togglePlay = async () => {
        if (!player.src) return;
        if (player.paused) {
            try {
                await player.play();
            } catch (error) {
                setStatus(`播放失敗：${error.message}`, 'error');
            }
        } else {
            player.pause();
        }
    };

    const seekBy = (delta) => {
        if (!Number.isFinite(delta) || !player.src) return;
        const duration = Number.isFinite(player.duration) ? player.duration : Infinity;
        player.currentTime = Math.min(Math.max(player.currentTime + delta, 0), duration);
    };

    toggle.addEventListener('click', togglePlay);

    for (const button of mini.querySelectorAll('[data-seek]')) {
        button.addEventListener('click', () => {
            seekBy(Number(button.dataset.seek));
        });
    }

    const applySetTime = (edge, { single = false } = {}) => {
        const now = playerCurrentTime();
        if (now === null) {
            setStatus('請先播放音檔，才有可套用的時間', 'error');
            return;
        }
        const idx = state.activeSegmentIndex;
        if (idx == null || !sessionItems()[idx]) {
            setStatus('請先播放某一段的音檔，才知道要設定哪一段的時間', 'error');
            return;
        }
        if (single) applyPlayerTimeSingle(idx, edge, now);
        else applyPlayerTime(idx, edge, now);
    };
    els.setStartButton?.addEventListener('click', () => applySetTime('start'));
    els.setEndButton?.addEventListener('click', () => applySetTime('end'));

    const openSetTimeMenu = (event, edge) => {
        event.preventDefault();
        const label = edge === 'start'
            ? '只設這一段的起始（不連動上一段結束）'
            : '只設這一段的結束（不連動下一段起始）';
        showContextMenu(event.clientX, event.clientY, [
            { label, onSelect: () => applySetTime(edge, { single: true }) },
        ]);
    };
    els.setStartButton?.addEventListener('contextmenu', (event) => openSetTimeMenu(event, 'start'));
    els.setEndButton?.addEventListener('contextmenu', (event) => openSetTimeMenu(event, 'end'));

    document.addEventListener('keydown', (event) => {
        if (event.ctrlKey || event.shiftKey) return;
        if (!player.src) return;
        const alt = event.altKey && !event.metaKey;
        const meta = event.metaKey && !event.altKey;
        if (!alt && !meta) return;
        switch (event.code) {
            case 'KeyP':
                event.preventDefault();
                togglePlay();
                break;
            case 'ArrowLeft':
                if (!alt) return;
                event.preventDefault();
                seekBy(-2);
                break;
            case 'ArrowRight':
                if (!alt) return;
                event.preventDefault();
                seekBy(2);
                break;
        }
    }, true);

    seekBar.addEventListener('pointerdown', () => { seeking = true; });
    seekBar.addEventListener('pointerup', () => { seeking = false; });
    seekBar.addEventListener('input', () => {
        if (!player.src) return;
        const next = Number(seekBar.value);
        if (Number.isFinite(next)) player.currentTime = next;
    });

    mini.addEventListener('pointerdown', (event) => {
        if (isMobileDock()) return;
        if (event.button !== undefined && event.button !== 0) return;
        if (event.target.closest('button, input, select, textarea, label, a')) return;
        dragging = true;
        dragOffset = {
            x: event.clientX - mini.offsetLeft,
            y: event.clientY - mini.offsetTop,
        };
        mini.classList.add('dragging');
        handle.classList.add('dragging');
        try { mini.setPointerCapture(event.pointerId); } catch { /* noop */ }
        event.preventDefault();
    });

    mini.addEventListener('pointermove', (event) => {
        if (!dragging) return;
        const nextLeft = clamp(event.clientX - dragOffset.x, 8, window.innerWidth - mini.offsetWidth - 8);
        const nextTop = clamp(event.clientY - dragOffset.y, 8, window.innerHeight - mini.offsetHeight - 8);
        mini.style.left = `${nextLeft}px`;
        mini.style.top = `${nextTop}px`;
        mini.style.right = 'auto';
        mini.style.bottom = 'auto';
    });

    const stopDrag = (event) => {
        if (!dragging) return;
        dragging = false;
        mini.classList.remove('dragging');
        handle.classList.remove('dragging');
        try { mini.releasePointerCapture(event.pointerId); } catch { /* noop */ }
        setPrefs({
            miniPlayerPos: {
                left: parseFloat(mini.style.left) || 0,
                top: parseFloat(mini.style.top) || 0,
            },
        });
    };
    mini.addEventListener('pointerup', stopDrag);
    mini.addEventListener('pointercancel', stopDrag);

    player.addEventListener('play', () => { toggle.textContent = '⏸'; });
    player.addEventListener('pause', () => { toggle.textContent = '▶'; });
    player.addEventListener('ended', () => { toggle.textContent = '▶'; });
    player.addEventListener('loadedmetadata', () => {
        durationEl.textContent = formatClock(player.duration);
        if (Number.isFinite(player.duration)) seekBar.max = String(player.duration);
    });
    player.addEventListener('durationchange', () => {
        durationEl.textContent = formatClock(player.duration);
        if (Number.isFinite(player.duration)) seekBar.max = String(player.duration);
    });
    player.addEventListener('timeupdate', () => {
        currentEl.textContent = formatClock(player.currentTime);
        if (!seeking) seekBar.value = String(player.currentTime);
    });
    player.addEventListener('emptied', () => {
        currentEl.textContent = '00:00:00.000';
        durationEl.textContent = '00:00:00.000';
        seekBar.value = '0';
        seekBar.max = '0';
    });
}

function restoreMiniPlayerPosition() {
    if (isMobileDock()) return;
    const pos = state.prefs.miniPlayerPos;
    if (!pos || typeof pos !== 'object') return;
    const mini = els.miniPlayer;
    if (Number.isFinite(pos.left)) {
        mini.style.left = `${pos.left}px`;
        mini.style.right = 'auto';
    }
    if (Number.isFinite(pos.top)) {
        mini.style.top = `${pos.top}px`;
        mini.style.bottom = 'auto';
    }
}

function clearMiniPlayerInlinePosition() {
    const mini = els.miniPlayer;
    if (!mini) return;
    mini.style.left = '';
    mini.style.top = '';
    mini.style.right = '';
    mini.style.bottom = '';
}

function handleDockModeChange() {
    const mobile = isMobileDock();
    if (mobile) clearMiniPlayerInlinePosition();
    else restoreMiniPlayerPosition();
    updateMiniPlayerHeight();
    updateSidebarToggleLabel();
    for (const card of els.editorRoot.querySelectorAll('.segment-card')) {
        applySegmentEditability(card);
    }
}
