import { createAudioController } from './audio.js';
import { getFile, isConflict, putFile, testToken } from './github.js';
import { parseRanges, secondsToTimecode, timecodeToSeconds } from './parser.js';
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

const MAP_BASE = './';
const MONTHS = [
    '2024-02', '2024-03', '2024-04', '2024-05', '2024-06',
    '2024-07', '2024-08', '2024-09', '2024-11', '2024-12',
    '2025-01', '2025-02', '2025-03', '2025-05',
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

/** Merge rapid start-nudge clicks into one undo step + one auto-replay. */
const nudgeBurst = {
    timer: null,
    segmentIndex: null,
    started: false,
    /** When true, settle-replay plays only ~3s from the new start. */
    previewShort: false,
};

/** 目前播放音檔在其合併時間軸上的起點偏移（split session 用，單檔為 0）。 */
let activePartBase = 0;

const els = {
    app: document.querySelector('#app'),
    sidebar: document.querySelector('#sidebar'),
    sidebarToggle: document.querySelector('#sidebarToggle'),
    sidebarToggleIcon: document.querySelector('#sidebarToggle .sidebar-toggle-icon'),
    sidebarResizer: document.querySelector('#sidebarResizer'),
    sidebarBackdrop: document.querySelector('#sidebarBackdrop'),
    monthSelect: document.querySelector('#monthSelect'),
    fileList: document.querySelector('#fileList'),
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
    workspace: document.querySelector('.workspace'),
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
    contentFillWidthInput: document.querySelector('#contentFillWidthInput'),
    contentMaxWidthRange: document.querySelector('#contentMaxWidthRange'),
    contentMaxWidthValue: document.querySelector('#contentMaxWidthValue'),
    contentAlignSelect: document.querySelector('#contentAlignSelect'),
    contentRightGutterRange: document.querySelector('#contentRightGutterRange'),
    contentRightGutterValue: document.querySelector('#contentRightGutterValue'),
    autoShowMiniPlayerInput: document.querySelector('#autoShowMiniPlayerInput'),
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
    nudgeStartButtons: document.querySelectorAll('[data-nudge-start]'),
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
    els.saveButton.addEventListener('click', () => saveCurrentMap());
    els.savePlayedButton?.addEventListener('click', () => saveCurrentMap({ reason: 'played' }));
    els.settingsButton.addEventListener('click', () => openSettings());
    els.saveSettingsButton.addEventListener('click', () => {
        setPat(els.patInput.value);
        saveLayoutSettingsFromForm();
        els.settingsMessage.textContent = '設定已儲存。';
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
    els.contentFillWidthInput?.addEventListener('change', () => {
        saveLayoutSettingsFromForm({ live: true });
    });
    els.contentMaxWidthRange?.addEventListener('input', () => {
        if (els.contentFillWidthInput?.checked) return;
        if (els.contentMaxWidthValue) els.contentMaxWidthValue.textContent = els.contentMaxWidthRange.value;
        saveLayoutSettingsFromForm({ live: true });
    });
    els.contentAlignSelect?.addEventListener('change', () => {
        saveLayoutSettingsFromForm({ live: true });
    });
    els.contentRightGutterRange?.addEventListener('input', () => {
        if (els.contentRightGutterValue) {
            els.contentRightGutterValue.textContent = els.contentRightGutterRange.value;
        }
        saveLayoutSettingsFromForm({ live: true });
    });
    els.autoShowMiniPlayerInput?.addEventListener('change', () => {
        const autoShow = Boolean(els.autoShowMiniPlayerInput.checked);
        state.prefs.autoShowMiniPlayer = autoShow;
        setPrefs({ autoShowMiniPlayer: autoShow });
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
    applyContentLayoutPrefs();
    if (isMobileDock() && !state.sessionId) {
        setSidebarOpen(true);
    }
}

function applyContentLayoutPrefs() {
    if (!els.app) return;
    const rawWidth = Number(state.prefs.contentMaxWidth);
    const fill = !Number.isFinite(rawWidth) || rawWidth <= 0;
    const width = fill ? 0 : clamp(rawWidth, 720, 2400);
    const align = state.prefs.contentAlign === 'left' ? 'left' : 'center';
    const gutter = clamp(Number(state.prefs.contentRightGutter) || 0, 0, 480);

    els.app.style.setProperty('--content-max-width', fill ? 'none' : `${width}px`);
    if (align === 'left') {
        els.app.style.setProperty('--content-margin-left', '0');
        els.app.style.setProperty('--content-margin-right', 'auto');
    } else {
        els.app.style.setProperty('--content-margin-left', 'auto');
        els.app.style.setProperty('--content-margin-right', 'auto');
    }
    els.app.style.setProperty('--content-right-gutter', `${gutter}px`);
}

function syncLayoutSettingsForm() {
    const rawWidth = Number(state.prefs.contentMaxWidth);
    const fill = !Number.isFinite(rawWidth) || rawWidth <= 0;
    const width = fill ? 1100 : clamp(rawWidth, 720, 2000);
    const gutter = clamp(Number(state.prefs.contentRightGutter) || 0, 0, 480);
    if (els.contentFillWidthInput) els.contentFillWidthInput.checked = fill;
    if (els.contentMaxWidthRange) {
        els.contentMaxWidthRange.value = String(width);
        els.contentMaxWidthRange.disabled = fill;
    }
    if (els.contentMaxWidthValue) els.contentMaxWidthValue.textContent = fill ? '填滿' : String(width);
    if (els.contentAlignSelect) {
        els.contentAlignSelect.value = state.prefs.contentAlign === 'left' ? 'left' : 'center';
    }
    if (els.contentRightGutterRange) els.contentRightGutterRange.value = String(gutter);
    if (els.contentRightGutterValue) els.contentRightGutterValue.textContent = String(gutter);
    if (els.autoShowMiniPlayerInput) {
        els.autoShowMiniPlayerInput.checked = state.prefs.autoShowMiniPlayer !== false;
    }
}

function saveLayoutSettingsFromForm({ live = false } = {}) {
    const fill = Boolean(els.contentFillWidthInput?.checked);
    const width = fill
        ? 0
        : clamp(Number(els.contentMaxWidthRange?.value) || 1100, 720, 2000);
    const align = els.contentAlignSelect?.value === 'left' ? 'left' : 'center';
    const gutter = clamp(Number(els.contentRightGutterRange?.value) || 0, 0, 480);
    const autoShow = els.autoShowMiniPlayerInput
        ? Boolean(els.autoShowMiniPlayerInput.checked)
        : state.prefs.autoShowMiniPlayer !== false;

    if (els.contentMaxWidthRange) els.contentMaxWidthRange.disabled = fill;
    if (els.contentMaxWidthValue) {
        els.contentMaxWidthValue.textContent = fill ? '填滿' : String(width);
    }
    if (els.contentRightGutterValue) {
        els.contentRightGutterValue.textContent = String(gutter);
    }

    state.prefs.contentMaxWidth = width;
    state.prefs.contentAlign = align;
    state.prefs.contentRightGutter = gutter;
    state.prefs.autoShowMiniPlayer = autoShow;
    setPrefs({
        contentMaxWidth: width,
        contentAlign: align,
        contentRightGutter: gutter,
        autoShowMiniPlayer: autoShow,
    });
    applyContentLayoutPrefs();
    if (!live && els.settingsMessage) {
        els.settingsMessage.textContent = '版面設定已套用。';
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

/** Show the floating player on play, unless the user opted out. */
function revealMiniPlayerIfAllowed() {
    if (state.prefs.autoShowMiniPlayer === false) return;
    setMiniPlayerHidden(false);
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
    return `audio_map2/${month}.json`;
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
        /(?:開場時間|收場時間|時間)\s*[:：]\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})/,
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
        if (session.closing) normalizeItemTimes(session.closing);
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
            const label = entry.kind === 'opening' ? '開場'
                : entry.kind === 'closing' ? '收場'
                : `第 ${entry.number} 段`;
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

/** 把「合併時間軸」上的絕對秒數，對應到實際音檔與該檔內局部秒數。
   audio_map2 的 split session（media_kind=split）把多個音檔串成一條時間軸：
   part[0] 佔 [0, dur0)，part[1] 佔 [dur0, dur0+dur1)… 。單檔則直接回該檔。 */
function resolvePlayback(session, start, end) {
    const parts = session?.media_parts || [];
    if (!parts.length) {
        activePartBase = 0;
        return { file: session?.audio_file || '', start, end };
    }
    if (parts.length === 1) {
        activePartBase = 0;
        return { file: parts[0].audio_file || session?.audio_file || '', start, end };
    }
    let base = 0;
    let hit = parts[0];
    for (const p of parts) {
        const dur = p.duration_est || 0;
        if (start == null || start < base + dur || p === parts[parts.length - 1]) {
            hit = p;
            break;
        }
        base += dur;
    }
    const localStart = start == null ? 0 : Math.max(0, start - base);
    const localEnd = end == null ? undefined : end - base;
    activePartBase = base;
    return { file: hit.audio_file || session?.audio_file || '', start: localStart, end: localEnd };
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
    if (session.closing) {
        items.push({ kind: 'closing', item: session.closing, number: '收場', title: '收場' });
    }
    return items;
}

/** Items that must be listened to before the session counts as complete. */
function mustCalibrateItems(session) {
    const items = [...(session.segments || [])];
    if (session.closing) items.push(session.closing);
    return items;
}

function itemKindLabel(kind, number) {
    if (kind === 'opening') return '開場';
    if (kind === 'closing') return '收場';
    return `第 ${number} 段`;
}

async function loadMonth(month, { forceRemote = false } = {}) {
    if (state.dirty && !forceRemote) {
        const ok = window.confirm('目前有未儲存變更，確定要切換月份並丟棄嗎？');
        if (!ok) {
            els.monthSelect.value = state.month;
            return;
        }
    }

    clearNudgeBurst();
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
        if (src.closing) {
            session.closing = session.closing || {};
            for (const k of ['text', 'text_preview']) {
                if (src.closing[k]) session.closing[k] = src.closing[k];
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
    els.fileList.innerHTML = '';
    const sessions = state.map?.sessions || [];
    let shown = 0;
    for (const session of sessions) {
        const label = `${session.date} ${session.source}`;
        shown += 1;
        const stats = countSessionMeta(session);
        const row = document.createElement('div');
        row.className = 'file-row';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'file-item' + (session.session_id === state.sessionId ? ' active' : '');
        btn.dataset.status = sessionListenStatus(stats);
        btn.innerHTML = `
            <span class="draft-dot hidden"></span>
            <div class="file-item-body">
                <span class="file-name">${escapeHtml(label)}</span>
                <span class="file-stats">✓${stats.matched} · ✗${stats.missing} · ${stats.total} 題 · 完成 ${stats.completed}${stats.hasClosing ? ' · 含收場' : ''}</span>
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

/**
 * Session complete only when every must-calibrate item (all Q&A + 收場) was listened.
 * 開場 is optional and does not gate completion.
 */
function sessionListenStatus(stats) {
    const must = stats.mustTotal || 0;
    const completed = stats.completed || 0;
    if (must === 0) return 'empty';
    if (completed >= must) return 'all';
    if (completed > 0) return 'partial';
    return 'none';
}

function countSessionMeta(session) {
    const rangeItems = [];
    if (session.opening) rangeItems.push(session.opening);
    rangeItems.push(...(session.segments || []));
    if (session.closing) rangeItems.push(session.closing);

    let matched = 0;
    let missing = 0;
    for (const item of rangeItems) {
        if (item.start != null && item.status !== 'missing') matched += 1;
        else missing += 1;
    }

    const mustItems = mustCalibrateItems(session);
    let completed = 0;
    let both = 0;
    let played = 0;
    let edited = 0;
    let none = 0;
    for (const item of mustItems) {
        const hasPlayed = Boolean(item?.meta?.lastPlayed);
        const hasEdited = Boolean(item?.meta?.lastEdited);
        // 「完成」= 必須項已聽過（含收場；不含開場）
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
        all: rangeItems.length,
        mustTotal: mustItems.length,
        hasClosing: Boolean(session.closing),
    };
}

function selectSession(sessionId) {
    clearNudgeBurst({ commit: true });
    state.sessionId = sessionId;
    state.activeSegmentIndex = null;
    state.prefs.lastMonth = state.month;
    state.prefs.lastSessionId = sessionId;
    setPrefs({ lastMonth: state.month, lastSessionId: sessionId });
    setActiveSegment(null);
    renderSessionList();
    els.fileList.querySelector('.file-item.active')?.scrollIntoView({ block: 'nearest' });
    renderEditor();
    scrollEditorToProgress();
    if (isMobileDock()) setSidebarOpen(false);
}

/** 「完成」= 聽過（有 lastPlayed）。捲到最後一段完成處；都沒完成則捲到頂。 */
function scrollEditorToProgress() {
    const workspace = els.workspace;
    if (!workspace) return;
    const items = sessionItems();
    let lastCompleted = -1;
    for (let i = 0; i < items.length; i += 1) {
        if (items[i].item?.meta?.lastPlayed) lastCompleted = i;
    }
    const apply = () => {
        if (lastCompleted < 0) {
            workspace.scrollTop = 0;
            return;
        }
        const card = els.editorRoot.querySelector(
            `.segment-card[data-segment-index="${lastCompleted}"]`,
        );
        if (!card) {
            workspace.scrollTop = 0;
            return;
        }
        const top = card.getBoundingClientRect().top
            - workspace.getBoundingClientRect().top
            + workspace.scrollTop;
        workspace.scrollTop = Math.max(0, top - 8);
    };
    // Wait past title autoGrow microtasks + layout.
    requestAnimationFrame(() => requestAnimationFrame(apply));
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
    // Meta strip tracks must-calibrate items only (segments + 收場).
    const must = items.filter((e) => e.kind === 'segment' || e.kind === 'closing');
    let completed = 0;
    let played = 0;
    let edited = 0;
    let none = 0;
    for (const { item } of must) {
        const hasPlayed = Boolean(item?.meta?.lastPlayed);
        const hasEdited = Boolean(item?.meta?.lastEdited);
        if (hasPlayed) completed += 1;
        if (hasPlayed && !hasEdited) played += 1;
        else if (!hasPlayed && hasEdited) edited += 1;
        else if (!hasPlayed && !hasEdited) none += 1;
    }
    els.metaTotalCount.textContent = String(must.length);
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
    node.querySelector('.segment-number').textContent = itemKindLabel(kind, number);

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
    // ←→ 只移動游標，不要冒泡到微調快捷鍵；↑↓／P／R／S 仍可冒泡生效。
    timeInput.addEventListener('keydown', (event) => {
        if (isArrowLeftRight(event)) event.stopPropagation();
    });
    timeLine.append(timeInput, playButton);
    body.append(timeLine);

    // PDF answer (or opening text) — read-only block (div, not textarea) so
    // mouse wheel scrolls the page instead of an inner scrollbar.
    const answer = (kind === 'opening' || kind === 'closing')
        ? (item.text || item.text_preview || '')
        : (item.answer_text || item.answer_preview || '');
    const answerEl = document.createElement('div');
    answerEl.className = 'editor-textarea answer-body';
    answerEl.setAttribute('role', 'region');
    answerEl.setAttribute(
        'aria-label',
        kind === 'opening' ? '開場文字（Word）'
            : kind === 'closing' ? '收場文字（Word）'
            : '回答（Word）',
    );
    if (answer) {
        answerEl.textContent = answer;
    } else {
        answerEl.classList.add('answer-body--empty');
        answerEl.textContent = kind === 'opening'
            ? '（此段開場文字缺失）'
            : kind === 'closing'
                ? '（此段收場文字缺失）'
                : '（此段尚無回答文字）';
    }
    body.append(answerEl);

    // audio_map2 特有欄位（純顯示，不含 review 按鈕）：信心度 / 狀態 / notes / SRT / 章節對應
    applyAm2CardExtras(node, item, kind);

    // Click question / answer to play (same as ▶); keep text selection for copy.
    bindPlayOnTextClick(titleField, playButton, '點擊播放這一段');
    bindPlayOnTextClick(answerEl, playButton, '點擊播放這一段');
    // Ensure Q/A surfaces never keep form focus that would swallow P / ← / →.
    for (const surface of [titleField, answerEl]) {
        surface.addEventListener('pointerdown', () => {
            blurIfBlocksShortcuts(document.activeElement);
        });
    }

    applySegmentEditability(node);
    return node;
}

/* ── audio_map2 卡片附加欄位（純顯示） ── */
function applyAm2CardExtras(node, item, kind) {
    if (kind !== 'segment') return; // 開場／收場不需信心度等
    const conf = item.confidence ?? 1;
    const lv = conf >= 0.8 ? 'high' : conf >= 0.5 ? 'mid' : 'low';

    node.classList.toggle('low-conf', lv === 'low');

    const metaRow = node.querySelector('.segment-meta');
    if (metaRow) {
        const confChip = document.createElement('span');
        confChip.className = `seg-conf ${lv}`;
        confChip.title = '自動對齊信心分數（低者請仔細聽檔）';
        confChip.textContent = (lv === 'low' ? '⚠ 低信心 ' : '') + conf.toFixed(2);
        metaRow.insertBefore(confChip, metaRow.children[1] || null);

        if (item.chapter_indexes?.length) {
            const idx = [...new Set(item.chapter_indexes)].sort((a, b) => a - b).join('、');
            const chChip = document.createElement('span');
            chChip.className = 'seg-meta-chip';
            chChip.title = '對應電子書前 12 章（由 link_chapters.py 寫回）';
            chChip.textContent = `對應第 ${idx} 章`;
            metaRow.appendChild(chChip);
        }
    }

    const body = node.querySelector('.segment-body');

    if (item.notes) {
        const notesEl = document.createElement('div');
        notesEl.className = 'am2-notes';
        if (/待人工|no-anchor:clamped/.test(item.notes)) notesEl.classList.add('am2-notes--pending');
        notesEl.textContent = `notes：${item.notes}`;
        body.appendChild(notesEl);
    }

    if (item.srt_preview) {
        const det = document.createElement('details');
        det.className = 'am2-srt';
        const sum = document.createElement('summary');
        sum.textContent = 'SRT 對照（僅供時間參考，非校對稿）';
        const pre = document.createElement('div');
        pre.className = 'am2-srt-body';
        pre.textContent = item.srt_preview;
        det.append(sum, pre);
        body.appendChild(det);
    }

    if (lv === 'low') {
        const banner = document.createElement('div');
        banner.className = 'lowconf-banner';
        banner.textContent = '⚠ 低信心配對：請特別仔細聽檔，必要時微調起訖時間。';
        body.appendChild(banner);
    }
}

/** Click-to-play on read-only Q/A text; skip if the user was selecting text. */
function bindPlayOnTextClick(el, playButton, hint) {
    if (!el || !playButton) return;
    el.classList.add('play-on-click');
    const prevTitle = el.getAttribute('title') || '';
    el.title = prevTitle ? `${prevTitle} · ${hint}` : hint;
    el.addEventListener('click', () => {
        if (playButton.disabled) return;
        const sel = window.getSelection();
        if (sel && !sel.isCollapsed) {
            // Only suppress when the selection is inside this field.
            if (el.contains(sel.anchorNode) || el.contains(sel.focusNode)) return;
        }
        // Drop form focus so P / ← / → keep working after click-to-play.
        blurIfBlocksShortcuts(document.activeElement);
        playButton.click();
    });
}

/**
 * True when the user is typing in a real editable control.
 * Read-only 問題、回答區不擋全域音檔快捷鍵。
 * 時間標記列：僅 ←→ 不觸發快捷鍵（留給游標）；P／R／S／↑↓ 仍有效。
 */
function isMarkerTimeInput(el) {
    if (!(el instanceof Element)) return false;
    if (el.classList.contains('marker-input')) return true;
    if (el.closest('.marker-input')) return true;
    return Boolean(el.closest('.marker-line') && el.matches('input'));
}

function isMarkerTimeFocused() {
    return isMarkerTimeInput(document.activeElement);
}

function isArrowLeftRight(event) {
    return event.code === 'ArrowLeft' || event.code === 'ArrowRight'
        || event.key === 'ArrowLeft' || event.key === 'ArrowRight';
}

function isTypingInEditableField(el) {
    if (!(el instanceof HTMLElement)) return false;
    if (el.closest('.answer-body')) return false;
    if (el.closest('textarea.segment-title[readonly]')) return false;
    if (isMarkerTimeInput(el)) return false;
    if (el.isContentEditable) return true;
    const tag = el.tagName;
    if (tag === 'SELECT') return true;
    if (tag === 'TEXTAREA') return !el.readOnly && !el.disabled;
    if (tag === 'INPUT') {
        if (el.readOnly || el.disabled) return false;
        const type = (el.type || 'text').toLowerCase();
        return !['button', 'checkbox', 'radio', 'submit', 'reset', 'file', 'range', 'color', 'hidden'].includes(type);
    }
    return false;
}

function blurIfBlocksShortcuts(el) {
    if (!(el instanceof HTMLElement)) return;
    if (el.matches('input, textarea, select') || el.isContentEditable) {
        try { el.blur(); } catch { /* noop */ }
    }
}

function formatTimeMarker(item, kind) {
    const prefix = kind === 'opening' ? '開場時間'
        : kind === 'closing' ? '收場時間'
        : '時間';
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
        if (!session?.audio_file && !session?.media_parts?.length) {
            setStatus('此 session 沒有音檔', 'error');
            return;
        }
        try {
            revealMiniPlayerIfAllowed();
            const rp = resolvePlayback(session, range.start, range.end);
            await audio.playRange(rp.file, { ...range, start: rp.start, end: rp.end }, title);
            // 聽過即算進度／完成；手機「聽」模式也要記，不可被 editing 閘門擋住。
            onSegmentPlayed(segmentIndex);
            setActiveSegment(segmentIndex);
        } catch (error) {
            setStatus(`播放失敗：${error.message}`, 'error');
        }
    };
}

/** Play a segment from its ▶ button (same as clicking Q/A text). */
function playSegmentByIndex(segmentIndex) {
    const items = sessionItems();
    if (segmentIndex == null || !items[segmentIndex]) return false;
    const card = els.editorRoot.querySelector(`.segment-card[data-segment-index="${segmentIndex}"]`);
    const playBtn = card?.querySelector('.play-range');
    blurIfBlocksShortcuts(document.activeElement);
    if (playBtn && !playBtn.disabled) {
        playBtn.click();
    } else {
        replaySegment(segmentIndex);
    }
    card?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    return true;
}

function setActiveSegment(index) {
    state.activeSegmentIndex = index == null ? null : index;
    const disabled = state.activeSegmentIndex == null;
    if (els.setStartButton) els.setStartButton.disabled = disabled;
    if (els.setEndButton) els.setEndButton.disabled = disabled;
    for (const button of els.nudgeStartButtons || []) {
        button.disabled = disabled;
    }
}

function playerCurrentTime() {
    const player = els.audioPlayer;
    if (!player || !player.src) return null;
    const t = player.currentTime;
    // 換回合併時間軸上的絕對秒數（split session 時加上目前音檔區段的起點偏移）
    return Number.isFinite(t) ? t + activePartBase : null;
}

/**
 * Nudge the active segment's start by `delta` seconds.
 * Chains previous segment end; rapid clicks are merged into one undo + one replay.
 * @param {number} delta
 * @param {{ previewShort?: boolean, button?: HTMLElement }} [opts]
 */
function nudgeSegmentStart(delta, opts = {}) {
    const idx = state.activeSegmentIndex;
    if (idx == null) {
        setStatus('請先播放某一段的音檔，才知道要微調哪一段的起始', 'error');
        return;
    }
    const items = sessionItems();
    const entry = items[idx];
    if (!entry) return;
    const item = entry.item;
    if (item.start == null || !Number.isFinite(item.start)) {
        setStatus('請先用「設起始」設定起始時間', 'error');
        return;
    }
    if (!Number.isFinite(delta) || delta === 0) return;

    const prev = items[idx - 1]?.item;
    const minStart = prev?.start != null && Number.isFinite(prev.start) ? prev.start : 0;
    const maxStart = item.end != null && Number.isFinite(item.end) ? item.end : Infinity;
    const next = roundSeconds(clamp(item.start + delta, minStart, maxStart));
    if (next === roundSeconds(item.start)) {
        setStatus(delta < 0 ? '已到起始下限，無法再提早' : '已到起始上限（本段結束），無法再延後', 'error');
        return;
    }

    // First click in a burst (or after switching segment): snapshot undo baseline.
    if (!nudgeBurst.started || nudgeBurst.segmentIndex !== idx) {
        clearTimeout(nudgeBurst.timer);
        commitHistory();
        nudgeBurst.started = true;
        nudgeBurst.segmentIndex = idx;
        nudgeBurst.previewShort = false;
    }
    if (opts.previewShort) nudgeBurst.previewShort = true;

    const signed = next >= item.start ? `+${(next - item.start).toFixed(3)}` : (next - item.start).toFixed(3);
    setSegmentEdge(idx, 'start', next);
    setSegmentEdge(idx - 1, 'end', next, { markEdited: false });
    const label = itemKindLabel(entry.kind, entry.number);
    const previewNote = opts.previewShort ? ' · 將試播 3 秒' : '';
    setStatus(`已將${label}起始調至 ${secondsToTimecode(next)}（${signed}s）${previewNote}`, 'ok');
    if (els.audioRange && item.start_label && item.end_label) {
        els.audioRange.textContent = ` ${item.start_label} - ${item.end_label}`;
    }

    spawnNudgeFloat(opts.button, delta);

    clearTimeout(nudgeBurst.timer);
    nudgeBurst.timer = setTimeout(() => finishNudgeBurst(), 450);
}

/** Damage-number style float for nudge button feedback. */
function spawnNudgeFloat(button, delta) {
    if (!button || !Number.isFinite(delta)) return;
    const text = delta > 0 ? `+${delta}s` : `−${Math.abs(delta)}s`;
    const floater = document.createElement('span');
    floater.className = 'nudge-float' + (delta < 0 ? ' nudge-float--neg' : ' nudge-float--pos');
    floater.textContent = text;
    floater.setAttribute('aria-hidden', 'true');
    button.append(floater);
    floater.addEventListener('animationend', () => floater.remove(), { once: true });
}

async function finishNudgeBurst() {
    const idx = nudgeBurst.segmentIndex;
    const previewShort = nudgeBurst.previewShort;
    nudgeBurst.timer = null;
    nudgeBurst.started = false;
    nudgeBurst.segmentIndex = null;
    nudgeBurst.previewShort = false;
    commitHistory();
    renderSessionList();
    await replaySegment(idx, previewShort ? { maxDuration: 3 } : undefined);
}

/** Play the segment from its current start→end (same as ▶ / nudge settle). */
async function replaySegment(segmentIndex, { maxDuration } = {}) {
    const entry = sessionItems()[segmentIndex];
    const session = currentSession();
    if (!entry || (!session?.audio_file && !session?.media_parts?.length)) return;
    const start = entry.item.start;
    const end = entry.item.end;
    if (start == null || end == null || !Number.isFinite(start) || !Number.isFinite(end)) return;
    let playEnd = end;
    if (maxDuration != null && Number.isFinite(maxDuration) && maxDuration > 0) {
        playEnd = Math.min(end, roundSeconds(start + maxDuration));
    }
    const range = {
        start,
        end: playEnd,
        startLabel: entry.item.start_label,
        endLabel: entry.item.end_label,
        label: `${entry.item.start_label} - ${entry.item.end_label}`,
    };
    try {
        revealMiniPlayerIfAllowed();
        const rp = resolvePlayback(session, start, playEnd);
        await audio.playRange(
            rp.file,
            { ...range, start: rp.start, end: rp.end },
            entry.title,
            maxDuration != null ? { forceStopAtEnd: true } : undefined,
        );
        setActiveSegment(segmentIndex);
        // 完整重播也算聽過；短試播（maxDuration）不記，避免微調時誤標完成。
        if (maxDuration == null) onSegmentPlayed(segmentIndex);
    } catch (error) {
        setStatus(`重播失敗：${error.message}`, 'error');
    }
}

function clearNudgeBurst({ commit = false } = {}) {
    if (!nudgeBurst.started && !nudgeBurst.timer) return;
    clearTimeout(nudgeBurst.timer);
    nudgeBurst.timer = null;
    const wasStarted = nudgeBurst.started;
    nudgeBurst.started = false;
    nudgeBurst.segmentIndex = null;
    nudgeBurst.previewShort = false;
    if (commit && wasStarted) {
        commitHistory();
        renderSessionList();
    }
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
    if (edge === 'start') replaySegment(segmentIndex);
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
    if (edge === 'start') replaySegment(segmentIndex);
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
    } else if (entry.kind === 'closing') {
        session.closing = cloneMap(orig.closing);
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
    const text = (entry.kind === 'opening' || entry.kind === 'closing')
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
            if (session.closing) list.push(session.closing);
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
    clearNudgeBurst();
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
    clearNudgeBurst();
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
    syncLayoutSettingsForm();
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

/** Long-press ≈ right-click menu (for touch / mobile). */
function bindLongPressMenu(el, onLongPress) {
    if (!el || typeof onLongPress !== 'function') return;
    let timer = null;
    let startX = 0;
    let startY = 0;
    let fired = false;
    const clear = () => {
        if (timer != null) {
            clearTimeout(timer);
            timer = null;
        }
    };
    el.addEventListener('pointerdown', (event) => {
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        fired = false;
        startX = event.clientX;
        startY = event.clientY;
        clear();
        timer = setTimeout(() => {
            timer = null;
            fired = true;
            onLongPress(event);
        }, 550);
    });
    el.addEventListener('pointermove', (event) => {
        if (timer == null) return;
        if (Math.hypot(event.clientX - startX, event.clientY - startY) > 10) clear();
    });
    el.addEventListener('pointerup', clear);
    el.addEventListener('pointercancel', clear);
    el.addEventListener('pointerleave', clear);
    el.addEventListener('click', (event) => {
        if (!fired) return;
        fired = false;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
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

    const seekBy = async (delta) => {
        if (!Number.isFinite(delta) || !player.src) return;
        const duration = Number.isFinite(player.duration) ? player.duration : Infinity;
        player.currentTime = Math.min(Math.max(player.currentTime + delta, 0), duration);
        // Seek alone does not touch start/end; if paused, resume so the jump is audible.
        if (player.paused) {
            try {
                await player.play();
            } catch (error) {
                setStatus(`播放失敗：${error.message}`, 'error');
            }
        }
    };

    toggle.addEventListener('click', togglePlay);

    for (const button of mini.querySelectorAll('[data-seek]')) {
        button.addEventListener('click', () => {
            seekBy(Number(button.dataset.seek));
        });
    }

    for (const button of els.nudgeStartButtons || []) {
        button.addEventListener('click', (event) => {
            // 桌機：Alt／⌘／Ctrl = 試播 3 秒。手機無修飾鍵，微調後預設試播 3 秒。
            const previewShort = isMobileDock()
                || Boolean(event.altKey || event.metaKey || event.ctrlKey);
            nudgeSegmentStart(Number(button.dataset.nudgeStart), {
                previewShort,
                button,
            });
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
    // 手機無右鍵：長按「設起始／設結束」等同桌機右鍵選單。
    bindLongPressMenu(els.setStartButton, (event) => openSetTimeMenu(event, 'start'));
    bindLongPressMenu(els.setEndButton, (event) => openSetTimeMenu(event, 'end'));

    // Bubble phase：時間框只擋 ←→；↑↓／P／R／S 在時間框內仍生效。
    document.addEventListener('keydown', (event) => {
        const inMarker = isMarkerTimeFocused() || isMarkerTimeInput(event.target);
        // 時間輸入框：僅 ←→ 留給游標，其餘快捷鍵照常。
        if (inMarker && isArrowLeftRight(event)) return;
        if (!inMarker && isTypingInEditableField(event.target)) return;
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;

        switch (event.code) {
            case 'KeyP': {
                if (!player.src) return;
                event.preventDefault();
                togglePlay();
                break;
            }
            case 'KeyR': {
                // 重頭播放：等同點擊該段問題／回答（觸發 ▶ 從段首播起）。
                event.preventDefault();
                const idx = state.activeSegmentIndex;
                if (idx == null || !sessionItems()[idx]) {
                    setStatus('請先播放某一段的音檔，才知道要重頭播放哪一段', 'error');
                    break;
                }
                playSegmentByIndex(idx);
                break;
            }
            case 'KeyS': {
                if (!player.src) return;
                event.preventDefault();
                if (!player.paused) player.pause();
                break;
            }
            case 'ArrowLeft': {
                event.preventDefault();
                const btn = document.querySelector('[data-nudge-start="-0.1"]');
                nudgeSegmentStart(-0.1, { previewShort: true, button: btn || undefined });
                break;
            }
            case 'ArrowRight': {
                event.preventDefault();
                const btn = document.querySelector('[data-nudge-start="0.1"]');
                nudgeSegmentStart(0.1, { previewShort: true, button: btn || undefined });
                break;
            }
            case 'ArrowDown': {
                event.preventDefault();
                {
                    const items = sessionItems();
                    if (!items.length) break;
                    const cur = state.activeSegmentIndex;
                    if (cur == null) {
                        playSegmentByIndex(0);
                        break;
                    }
                    if (cur >= items.length - 1) {
                        setStatus('已是最後一段', 'ok');
                        break;
                    }
                    playSegmentByIndex(cur + 1);
                }
                break;
            }
            case 'ArrowUp': {
                event.preventDefault();
                {
                    const items = sessionItems();
                    if (!items.length) break;
                    const cur = state.activeSegmentIndex;
                    if (cur == null) {
                        playSegmentByIndex(0);
                        break;
                    }
                    if (cur <= 0) {
                        setStatus('已是第一段', 'ok');
                        break;
                    }
                    playSegmentByIndex(cur - 1);
                }
                break;
            }
            default:
                break;
        }
    });

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
