import { createAudioController } from './audio.js';
import { getFile, isConflict, listQaFiles, putFile, testToken } from './github.js';
import { cloneDocument, extractMeta, fileTitleFromPath, injectMeta, parseDocument, parseRanges, serializeDocument } from './parser.js';
import { clearDraft, clearPat, getDraft, getPat, getPrefs, listDraftPaths, setDraft, setPat, setPrefs } from './storage.js';

const EMPTY_META = { lastPlayed: '', lastEdited: '' };

const state = {
    files: [],
    currentFile: null,
    currentSha: '',
    originalText: '',
    originalStripped: '',
    originalMeta: { ...EMPTY_META },
    meta: { ...EMPTY_META },
    document: null,
    originalDocument: null,
    dirty: false,
    prefs: getPrefs(),
    draftPaths: listDraftPaths(),
    draftTimer: null,
};

const els = {
    fileList: document.querySelector('#fileList'),
    fileSearch: document.querySelector('#fileSearch'),
    welcomePanel: document.querySelector('#welcomePanel'),
    documentPanel: document.querySelector('#documentPanel'),
    documentPath: document.querySelector('#documentPath'),
    documentTitle: document.querySelector('#documentTitle'),
    segmentCount: document.querySelector('#segmentCount'),
    draftBadge: document.querySelector('#draftBadge'),
    metaLastPlayed: document.querySelector('#metaLastPlayed'),
    metaLastEdited: document.querySelector('#metaLastEdited'),
    editorRoot: document.querySelector('#editorRoot'),
    saveButton: document.querySelector('#saveButton'),
    saveStatus: document.querySelector('#saveStatus'),
    settingsButton: document.querySelector('#settingsButton'),
    settingsDialog: document.querySelector('#settingsDialog'),
    patInput: document.querySelector('#patInput'),
    showReportsSetting: document.querySelector('#showReportsSetting'),
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
    miniPlayerToggle: document.querySelector('#miniPlayerToggle'),
    miniPlayerCurrent: document.querySelector('#miniPlayerCurrent'),
    miniPlayerDuration: document.querySelector('#miniPlayerDuration'),
    seekBar: document.querySelector('#seekBar'),
};

const audio = createAudioController({
    audio: els.audioPlayer,
    titleEl: els.audioTitle,
    rangeEl: els.audioRange,
    rateSelect: els.playbackRate,
    stopCheckbox: els.stopAtRangeEnd,
});

bootstrap();

async function bootstrap() {
    bindEvents();
    setupMiniPlayer();
    applyPrefs();
    await loadFileList();
}

function bindEvents() {
    els.fileSearch.addEventListener('input', renderFileList);
    els.saveButton.addEventListener('click', () => saveCurrentFile());
    els.settingsButton.addEventListener('click', () => openSettings());
    els.saveSettingsButton.addEventListener('click', () => {
        setPat(els.patInput.value);
        const showReports = els.showReportsSetting.checked;
        setPrefs({ showReports });
        state.prefs.showReports = showReports;
        loadFileList();
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
    document.addEventListener('keydown', (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
            event.preventDefault();
            saveCurrentFile();
        }
        if (event.key === 'Escape' && state.dirty) {
            event.preventDefault();
            renderDocument();
        }
    });
    window.addEventListener('beforeunload', (event) => {
        if (!state.dirty) return;
        event.preventDefault();
        event.returnValue = '';
    });
}

function applyPrefs() {
    els.showReportsSetting.checked = state.prefs.showReports === true;
    audio.setPlaybackRate(state.prefs.playbackRate);
    audio.setStopAtRangeEnd(state.prefs.stopAtRangeEnd);
    els.opusWarning.classList.toggle('hidden', audio.supportsOpus);
}

async function loadFileList() {
    setStatus('正在載入檔案列表...', 'loading');
    try {
        state.files = await listQaFiles({ showReports: state.prefs.showReports === true });
        state.draftPaths = listDraftPaths();
        renderFileList();
        setStatus(`已載入 ${state.files.length} 個檔案`, 'ok');
    } catch (error) {
        els.fileList.innerHTML = `<div class="empty-state error">載入失敗：${escapeHtml(error.message)}</div>`;
        setStatus('檔案列表載入失敗', 'error');
    }
}

function renderFileList() {
    const query = els.fileSearch.value.trim().toLowerCase();
    const files = state.files.filter((file) => !query || file.name.toLowerCase().includes(query));

    if (files.length === 0) {
        els.fileList.innerHTML = '<div class="empty-state">沒有符合條件的檔案。</div>';
        return;
    }

    const groups = groupFiles(files);
    els.fileList.innerHTML = '';
    for (const [group, groupFilesForMonth] of groups) {
        const section = document.createElement('section');
        section.className = 'file-group';
        section.innerHTML = `<h3>${escapeHtml(group)}</h3>`;
        for (const file of groupFilesForMonth) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'file-item';
            button.classList.toggle('active', state.currentFile?.path === file.path);
            button.innerHTML = `
                <span class="draft-dot ${state.draftPaths.has(file.path) ? '' : 'hidden'}"></span>
                <span class="file-name">${escapeHtml(file.name.replace(/\.txt$/i, ''))}</span>
            `;
            button.addEventListener('click', () => loadDocument(file));
            section.append(button);
        }
        els.fileList.append(section);
    }
}

async function loadDocument(file, { preferDraft = null } = {}) {
    if (state.dirty && !confirm('目前檔案有未儲存修改，確定切換檔案？')) {
        return;
    }

    setStatus(`正在載入 ${file.name}...`, 'loading');
    try {
        const remote = await getFile(file.path);
        const { meta: remoteMeta, stripped: remoteStripped } = extractMeta(remote.text);
        const draft = getDraft(file.path);
        let workingText = remoteStripped;
        let workingMeta = { ...remoteMeta };
        let useDraft = false;

        if (draft && preferDraft === null) {
            const choice = await askDraftChoice(file.path, draft);
            if (choice === 'draft') useDraft = true;
            if (choice === 'discard') clearDraft(file.path);
        } else if (draft && preferDraft === true) {
            useDraft = true;
        }

        if (useDraft) {
            workingText = typeof draft.text === 'string' ? draft.text : workingText;
            workingMeta = draft.meta ? { ...EMPTY_META, ...draft.meta } : workingMeta;
        }

        state.currentFile = file;
        state.currentSha = remote.sha;
        state.originalText = remote.text;
        state.originalStripped = remoteStripped;
        state.originalMeta = { ...remoteMeta };
        state.meta = { ...workingMeta };
        state.originalDocument = parseDocument(remoteStripped, file.path);
        state.document = parseDocument(workingText, file.path);
        state.dirty = useDraft && (workingText !== remoteStripped || metaDiffers(workingMeta, remoteMeta));
        state.draftPaths = listDraftPaths();
        renderFileList();
        renderDocument();
        setStatus(state.dirty ? '已載入本機草稿' : '已載入遠端最新版', state.dirty ? 'dirty' : 'ok');
    } catch (error) {
        setStatus(`載入失敗：${error.message}`, 'error');
    }
}

function metaDiffers(a, b) {
    return (a?.lastPlayed || '') !== (b?.lastPlayed || '') || (a?.lastEdited || '') !== (b?.lastEdited || '');
}

function renderDocument() {
    if (!state.document || !state.currentFile) return;

    els.welcomePanel.classList.add('hidden');
    els.documentPanel.classList.remove('hidden');
    els.documentPath.textContent = state.currentFile.path;
    els.documentTitle.textContent = state.document.title || fileTitleFromPath(state.currentFile.path);
    els.segmentCount.textContent = `${state.document.segments.length} 段`;
    els.draftBadge.classList.toggle('hidden', !state.draftPaths.has(state.currentFile.path));
    els.saveButton.disabled = !state.dirty;
    refreshMetaStrip();
    els.editorRoot.innerHTML = '';

    if (state.document.header) {
        els.editorRoot.append(renderIntroCard());
    }

    state.document.segments.forEach((segment, segmentIndex) => {
        els.editorRoot.append(renderSegmentCard(segment, segmentIndex));
    });

    refreshDirtyUI();
}

function renderIntroCard() {
    const card = document.createElement('article');
    card.className = 'segment-card intro-card';
    const ranges = state.document.headerRanges || parseRanges(state.document.header);
    card.innerHTML = `
        <header class="segment-header">
            <div>
                <p class="segment-number">開場</p>
                <h3 class="segment-title">檔案開頭與說明（含「開場時間」等可編輯標記）</h3>
            </div>
        </header>
        <div class="range-buttons"></div>
        <textarea class="editor-textarea" data-header="true" spellcheck="false"></textarea>
    `;
    const rangeContainer = card.querySelector('.range-buttons');
    rangeContainer.append(...renderRangeButtons(ranges, '開場'));
    const textarea = card.querySelector('textarea');
    textarea.value = state.document.header;
    textarea.addEventListener('input', () => {
        state.document.header = textarea.value;
        state.document.headerRanges = parseRanges(textarea.value);
        rangeContainer.innerHTML = '';
        rangeContainer.append(...renderRangeButtons(state.document.headerRanges, '開場'));
        markDirty();
        autoGrow(textarea);
    });
    queueMicrotask(() => autoGrow(textarea));
    return card;
}

function renderSegmentCard(segment, segmentIndex) {
    const node = els.segmentTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.segmentIndex = String(segmentIndex);
    node.querySelector('.segment-number').textContent = segment.number ? `第 ${segment.number} 段` : '全文';
    node.querySelector('.segment-title').textContent = segment.title;
    node.querySelector('.copy-segment').addEventListener('click', () => {
        navigator.clipboard.writeText(segment.raw);
        setStatus('已複製原始段落', 'ok');
    });
    node.querySelector('.reset-segment').addEventListener('click', () => resetSegment(segmentIndex));

    const body = node.querySelector('.segment-body');
    for (const [partIndex, part] of segment.parts.entries()) {
        if (part.type === 'marker') {
            body.append(renderMarker(part.text, segment, segmentIndex, partIndex, node));
        } else {
            const textarea = document.createElement('textarea');
            textarea.className = 'editor-textarea';
            textarea.spellcheck = false;
            textarea.value = part.text;
            textarea.dataset.segmentIndex = String(segmentIndex);
            textarea.dataset.partIndex = String(partIndex);
            textarea.addEventListener('input', () => {
                state.document.segments[segmentIndex].parts[partIndex].text = textarea.value;
                markDirty();
                autoGrow(textarea);
            });
            body.append(textarea);
            queueMicrotask(() => autoGrow(textarea));
        }
    }

    return node;
}

function renderMarker(text, segment, segmentIndex, partIndex, card) {
    const marker = document.createElement('div');
    marker.className = 'marker-line';

    const endsWithNewline = /\n$/.test(text);
    const displayValue = endsWithNewline ? text.slice(0, -1) : text;

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'marker-input';
    input.value = displayValue;
    input.spellcheck = false;
    input.dataset.segmentIndex = String(segmentIndex);
    input.dataset.partIndex = String(partIndex);
    const kind = detectMarkerKind(displayValue);
    if (kind === 'heading') {
        input.setAttribute('aria-label', '段落標題（格式：### N. 標題）');
        input.title = '格式：### N. 標題';
    } else if (kind === 'time') {
        input.setAttribute('aria-label', '段落時間（格式：時間：HH:MM:SS.mmm - HH:MM:SS.mmm）');
        input.title = '格式：時間：HH:MM:SS.mmm - HH:MM:SS.mmm';
    }
    marker.append(input);

    let playButton = null;
    if (kind === 'time') {
        playButton = document.createElement('button');
        playButton.type = 'button';
        playButton.className = 'button button-secondary play-range';
        playButton.dataset.segmentIndex = String(segmentIndex);
        marker.append(playButton);
        updatePlayButton(playButton, displayValue, segment);
    }

    input.addEventListener('input', () => {
        const newValue = input.value;
        const newText = endsWithNewline ? `${newValue}\n` : newValue;
        state.document.segments[segmentIndex].parts[partIndex].text = newText;

        if (kind === 'heading') {
            const match = newValue.match(/^###\s+(\d+)\.\s*(.*)$/);
            if (match) {
                segment.number = match[1];
                segment.title = match[2];
            } else {
                segment.number = '';
                segment.title = newValue.trim();
            }
            updateSegmentCardHeader(card, segment);
        }

        if (playButton) {
            updatePlayButton(playButton, newValue, segment);
        }

        segment.ranges = collectSegmentRanges(state.document.segments[segmentIndex]);
        markDirty();
    });

    return marker;
}

function detectMarkerKind(line) {
    if (/^###\s+/.test(line)) return 'heading';
    if (/^(時間|開場時間)：/.test(line)) return 'time';
    return 'other';
}

function updateSegmentCardHeader(card, segment) {
    const number = card.querySelector('.segment-number');
    const title = card.querySelector('.segment-title');
    if (number) number.textContent = segment.number ? `第 ${segment.number} 段` : '段落';
    if (title) title.textContent = segment.title || '（未命名）';
}

function collectSegmentRanges(segment) {
    return segment.parts
        .filter((part) => part.type === 'marker')
        .flatMap((part) => parseRanges(part.text));
}

function updatePlayButton(button, markerText, segment) {
    const range = parseRanges(markerText)[0];
    if (!range) {
        button.textContent = '▶ 時間格式無效';
        button.disabled = true;
        button.onclick = null;
        return;
    }
    button.disabled = false;
    button.textContent = `▶ ${range.label}`;
    button.onclick = async () => {
        try {
            await audio.playRange(state.currentFile.path, range, `${segment.number}. ${segment.title}`);
            recordPlayback();
        } catch (error) {
            setStatus(`播放失敗：${error.message}`, 'error');
        }
    };
}

function renderRangeButtons(ranges, label) {
    if (!ranges.length) {
        const empty = document.createElement('span');
        empty.className = 'hint';
        empty.textContent = '沒有時間標記';
        return [empty];
    }
    return ranges.map((range) => renderPlayButton(range, label));
}

function renderPlayButton(range, label) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'button button-secondary play-range';
    button.textContent = `▶ ${range.label}`;
    button.addEventListener('click', async () => {
        try {
            await audio.playRange(state.currentFile.path, range, label);
            recordPlayback();
        } catch (error) {
            setStatus(`播放失敗：${error.message}`, 'error');
        }
    });
    return button;
}

function recordPlayback() {
    if (!state.currentFile) return;
    state.meta.lastPlayed = formatTimestamp();
    markDirty();
}

function resetSegment(segmentIndex) {
    const original = state.originalDocument?.segments?.[segmentIndex];
    if (!original) return;
    state.document.segments[segmentIndex] = cloneDocument({ segments: [original] }).segments[0];
    markDirty();
    renderDocument();
}

function markDirty() {
    if (!state.document) return;

    const text = serializeDocument(state.document);
    const textChanged = text !== state.originalStripped;
    state.meta.lastEdited = textChanged
        ? formatTimestamp()
        : (state.originalMeta.lastEdited || '');

    const metaChanged = metaDiffers(state.meta, state.originalMeta);
    state.dirty = textChanged || metaChanged;

    if (state.dirty && state.currentFile) {
        scheduleDraftSave(text);
    } else if (state.currentFile) {
        clearDraft(state.currentFile.path);
        state.draftPaths = listDraftPaths();
    }
    refreshMetaStrip();
    refreshDirtyUI();
}

function scheduleDraftSave(text) {
    clearTimeout(state.draftTimer);
    state.draftTimer = setTimeout(() => {
        if (!state.currentFile) return;
        setDraft(state.currentFile.path, text, state.currentSha, state.meta);
        state.draftPaths = listDraftPaths();
        els.draftBadge.classList.remove('hidden');
        renderFileList();
    }, 500);
}

function refreshMetaStrip() {
    if (els.metaLastPlayed) {
        els.metaLastPlayed.textContent = state.meta.lastPlayed || '—';
    }
    if (els.metaLastEdited) {
        els.metaLastEdited.textContent = state.meta.lastEdited || '—';
    }
}

function formatTimestamp(date = new Date()) {
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

async function saveCurrentFile({ force = false } = {}) {
    if (!state.currentFile || !state.document) return;

    const strippedText = serializeDocument(state.document);
    const metaForSave = { ...state.meta };
    if (metaDiffers(state.meta, state.originalMeta) && !metaForSave.lastEdited) {
        metaForSave.lastEdited = formatTimestamp();
    }
    const finalText = injectMeta(strippedText, metaForSave);

    if (!force && finalText === state.originalText) {
        setStatus('沒有需要儲存的修改', 'ok');
        state.dirty = false;
        refreshDirtyUI();
        return;
    }

    if (!getPat()) {
        openSettings('請先設定 GitHub PAT 才能儲存。');
        return;
    }

    els.saveButton.disabled = true;
    setStatus('正在儲存到 GitHub...', 'loading');
    try {
        const message = `qa: edit ${state.currentFile.name} via web editor (${new Date().toLocaleString('zh-TW')})`;
        const result = await putFile(state.currentFile.path, finalText, state.currentSha, message, { force });
        state.currentSha = result.content.sha;
        state.originalText = finalText;
        state.originalStripped = strippedText;
        state.originalMeta = { ...metaForSave };
        state.meta = { ...metaForSave };
        state.originalDocument = parseDocument(strippedText, state.currentFile.path);
        state.document = parseDocument(strippedText, state.currentFile.path);
        state.dirty = false;
        clearDraft(state.currentFile.path);
        state.draftPaths = listDraftPaths();
        renderFileList();
        renderDocument();
        setStatus('已儲存並建立 GitHub commit', 'ok');
    } catch (error) {
        if (isConflict(error)) {
            await handleConflict(finalText);
        } else {
            setStatus(`儲存失敗：${error.message}`, 'error');
            els.saveButton.disabled = false;
        }
    }
}

async function handleConflict(localText) {
    setStatus('遠端檔案已更新，等待處理衝突', 'error');
    try {
        const remote = await getFile(state.currentFile.path);
        els.conflictPreview.textContent = buildConflictPreview(remote.text, localText);
    } catch {
        els.conflictPreview.textContent = '無法載入遠端預覽。';
    }

    const choice = await showDialogAndWait(els.conflictDialog);
    if (choice === 'force') {
        await saveCurrentFile({ force: true });
        return;
    }
    if (choice === 'reload') {
        state.dirty = false;
        await loadDocument(state.currentFile, { preferDraft: false });
    }
}

function refreshDirtyUI() {
    els.saveButton.disabled = !state.dirty;
    els.draftBadge.classList.toggle('hidden', !(state.currentFile && state.draftPaths.has(state.currentFile.path)));
    setStatus(state.dirty ? '有未儲存修改' : '已同步', state.dirty ? 'dirty' : 'ok');

    const originalSegments = state.originalDocument?.segments || [];
    for (const card of els.editorRoot.querySelectorAll('.segment-card[data-segment-index]')) {
        const index = Number(card.dataset.segmentIndex);
        const current = segmentText(state.document.segments[index]);
        const original = segmentText(originalSegments[index]);
        card.querySelector('.segment-dirty')?.classList.toggle('hidden', current === original);
    }
}

function setStatus(message, type = 'ok') {
    els.saveStatus.textContent = message;
    els.saveStatus.dataset.type = type;
}

function openSettings(message = '') {
    els.patInput.value = getPat();
    els.showReportsSetting.checked = state.prefs.showReports === true;
    els.settingsMessage.textContent = typeof message === 'string' ? message : '';
    els.settingsDialog.showModal();
}

async function askDraftChoice(path, draft) {
    const date = draft.savedAt ? new Date(draft.savedAt).toLocaleString('zh-TW') : '未知時間';
    els.draftMessage.textContent = `${path} 有本機草稿，最後暫存時間：${date}。`;
    return showDialogAndWait(els.draftDialog);
}

function showDialogAndWait(dialog) {
    return new Promise((resolve) => {
        const onClose = () => {
            dialog.removeEventListener('close', onClose);
            resolve(dialog.returnValue);
        };
        dialog.addEventListener('close', onClose);
        dialog.showModal();
    });
}

function groupFiles(files) {
    const groups = new Map();
    for (const file of files) {
        const match = file.name.match(/^(\d{4})年(\d{1,2})月/);
        const group = match ? `${match[1]} 年 ${match[2].padStart(2, '0')} 月` : '其他';
        if (!groups.has(group)) groups.set(group, []);
        groups.get(group).push(file);
    }
    return groups;
}

function autoGrow(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.max(80, textarea.scrollHeight + 2)}px`;
}

function segmentText(segment) {
    return segment?.parts?.map((part) => part.text).join('') || '';
}

function buildConflictPreview(remoteText, localText) {
    const remoteLines = remoteText.split(/\r?\n/);
    const localLines = localText.split(/\r?\n/);
    const rows = Array.from({ length: remoteLines.length + 1 }, () => Array(localLines.length + 1).fill(0));
    for (let i = remoteLines.length - 1; i >= 0; i -= 1) {
        for (let j = localLines.length - 1; j >= 0; j -= 1) {
            rows[i][j] = remoteLines[i] === localLines[j]
                ? rows[i + 1][j + 1] + 1
                : Math.max(rows[i + 1][j], rows[i][j + 1]);
        }
    }

    const lines = [];
    let i = 0;
    let j = 0;

    while ((i < remoteLines.length || j < localLines.length) && lines.length < 120) {
        if (remoteLines[i] === localLines[j]) {
            i += 1;
            j += 1;
        } else if (j >= localLines.length || (i < remoteLines.length && rows[i + 1][j] >= rows[i][j + 1])) {
            lines.push(`- 遠端第 ${i + 1} 行：${remoteLines[i]}`);
            i += 1;
        } else {
            lines.push(`+ 本地第 ${j + 1} 行：${localLines[j]}`);
            j += 1;
        }
    }

    return lines.length ? lines.join('\n') : '無法產生差異摘要，但 sha 已不一致。';
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    }[char]));
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

    toggle.addEventListener('click', async () => {
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
    });

    for (const button of mini.querySelectorAll('[data-seek]')) {
        button.addEventListener('click', () => {
            const delta = Number(button.dataset.seek);
            if (!Number.isFinite(delta) || !player.src) return;
            const duration = Number.isFinite(player.duration) ? player.duration : Infinity;
            const next = Math.min(Math.max(player.currentTime + delta, 0), duration);
            player.currentTime = next;
        });
    }

    seekBar.addEventListener('pointerdown', () => {
        seeking = true;
    });
    seekBar.addEventListener('pointerup', () => {
        seeking = false;
    });
    seekBar.addEventListener('input', () => {
        if (!player.src) return;
        const next = Number(seekBar.value);
        if (Number.isFinite(next)) {
            player.currentTime = next;
        }
    });

    handle.addEventListener('pointerdown', (event) => {
        if (event.target.closest('button, input, select, label, a')) return;
        dragging = true;
        dragOffset = {
            x: event.clientX - mini.offsetLeft,
            y: event.clientY - mini.offsetTop,
        };
        handle.classList.add('dragging');
        handle.setPointerCapture(event.pointerId);
    });

    handle.addEventListener('pointermove', (event) => {
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
        handle.classList.remove('dragging');
        try {
            handle.releasePointerCapture(event.pointerId);
        } catch {
            // pointer was already released
        }
        setPrefs({
            miniPlayerPos: {
                left: parseFloat(mini.style.left) || 0,
                top: parseFloat(mini.style.top) || 0,
            },
        });
    };
    handle.addEventListener('pointerup', stopDrag);
    handle.addEventListener('pointercancel', stopDrag);

    player.addEventListener('play', () => {
        toggle.textContent = '⏸';
    });
    player.addEventListener('pause', () => {
        toggle.textContent = '▶';
    });
    player.addEventListener('ended', () => {
        toggle.textContent = '▶';
    });
    player.addEventListener('loadedmetadata', () => {
        durationEl.textContent = formatClock(player.duration);
        if (Number.isFinite(player.duration)) {
            seekBar.max = String(player.duration);
        }
    });
    player.addEventListener('durationchange', () => {
        durationEl.textContent = formatClock(player.duration);
        if (Number.isFinite(player.duration)) {
            seekBar.max = String(player.duration);
        }
    });
    player.addEventListener('timeupdate', () => {
        currentEl.textContent = formatClock(player.currentTime);
        if (!seeking) {
            seekBar.value = String(player.currentTime);
        }
    });
    player.addEventListener('emptied', () => {
        currentEl.textContent = '00:00';
        durationEl.textContent = '00:00';
        seekBar.value = '0';
        seekBar.max = '0';
    });
}

function restoreMiniPlayerPosition() {
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

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function formatClock(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) return '00:00';
    const total = Math.floor(seconds);
    const minutes = Math.floor(total / 60);
    const secs = total % 60;
    if (minutes >= 60) {
        const hours = Math.floor(minutes / 60);
        return `${String(hours).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}
