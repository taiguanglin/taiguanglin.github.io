import { createAudioController } from './audio.js';
import { getFile, isConflict, listQaFiles, putFile, testToken } from './github.js';
import { cloneDocument, fileTitleFromPath, parseDocument, parseRanges, secondsToTimecode, serializeDocument } from './parser.js';
import { findSecondQuestion, mergeWithNext, removeSegment, splitSegment } from './segment-ops.js';
import { clearDraft, clearPat, getDraft, getPat, getPrefs, listDraftPaths, setDraft, setPat, setPrefs } from './storage.js';

const state = {
    files: [],
    currentFile: null,
    currentSha: '',
    originalText: '',
    document: null,
    originalDocument: null,
    dirty: false,
    prefs: getPrefs(),
    draftPaths: listDraftPaths(),
    draftTimer: null,
    fileStats: new Map(),
    statsFetched: false,
    bodyCaret: null,
    editorCaret: null,
    activeSegmentIndex: null,
};

// 編輯歷史：以「整份文件序列化後的文字」為單位做快照，支援上一步／下一步。
// 連續打字會在停頓後合併成一步，結構性操作（合併、拆分、刪除、設時間…）各算一步。
const HISTORY_LIMIT = 50;
const history = {
    undo: [],
    redo: [],
    committed: null,
    timer: null,
};

const els = {
    app: document.querySelector('#app'),
    sidebar: document.querySelector('#sidebar'),
    sidebarToggle: document.querySelector('#sidebarToggle'),
    sidebarResizer: document.querySelector('#sidebarResizer'),
    fileList: document.querySelector('#fileList'),
    fileSearch: document.querySelector('#fileSearch'),
    workspace: document.querySelector('.workspace'),
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
    miniPlayerToggle: document.querySelector('#miniPlayerToggle'),
    miniPlayerCurrent: document.querySelector('#miniPlayerCurrent'),
    miniPlayerDuration: document.querySelector('#miniPlayerDuration'),
    playerToggle: document.querySelector('#playerToggle'),
    seekBar: document.querySelector('#seekBar'),
    setStartButton: document.querySelector('#setStartButton'),
    setEndButton: document.querySelector('#setEndButton'),
    undoButton: document.querySelector('#undoButton'),
    redoButton: document.querySelector('#redoButton'),
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
    setupSidebarControls();
    applyPrefs();
    await loadFileList();
}

function bindEvents() {
    els.fileSearch.addEventListener('input', renderFileList);
    els.saveButton.addEventListener('click', () => saveCurrentFile());
    els.savePlayedButton?.addEventListener('click', () => saveCurrentFile({ reason: 'played' }));
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
    els.undoButton?.addEventListener('click', () => undoEdit());
    els.redoButton?.addEventListener('click', () => redoEdit());
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && state.dirty) {
            event.preventDefault();
            renderDocument();
        }
    });
    // 整體編輯的上一步／下一步僅透過 UI 按鈕觸發，不攔截 ⌘Z／⌘⇧Z 等鍵盤組合，
    // 以免在文字編輯框中造成畫面捲動等干擾。
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
    const collapsed = els.app.classList.contains('sidebar-collapsed');
    els.sidebarToggle.setAttribute('aria-expanded', String(!collapsed));
    els.sidebarToggle.textContent = collapsed ? '☰' : '⟨';
    els.sidebarToggle.title = collapsed ? '展開側邊欄' : '收起側邊欄';
}

function applyMiniPlayerVisibility() {
    const hidden = state.prefs.miniPlayerHidden === true;
    els.miniPlayer?.classList.toggle('hidden', hidden);
    if (els.playerToggle) {
        els.playerToggle.textContent = hidden ? '顯示播放器' : '隱藏播放器';
        els.playerToggle.setAttribute('aria-pressed', String(!hidden));
    }
}

function setMiniPlayerHidden(hidden) {
    const next = Boolean(hidden);
    if (state.prefs.miniPlayerHidden === next) return;
    state.prefs.miniPlayerHidden = next;
    setPrefs({ miniPlayerHidden: next });
    applyMiniPlayerVisibility();
}

function setupSidebarControls() {
    els.sidebarToggle.addEventListener('click', () => {
        const collapsed = !els.app.classList.contains('sidebar-collapsed');
        els.app.classList.toggle('sidebar-collapsed', collapsed);
        state.prefs.sidebarCollapsed = collapsed;
        setPrefs({ sidebarCollapsed: collapsed });
        updateSidebarToggleLabel();
    });

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
    });
}

async function loadFileList() {
    setStatus('正在載入檔案列表...', 'loading');
    try {
        state.files = await listQaFiles();
        state.draftPaths = listDraftPaths();
        renderFileList();
        setStatus(`已載入 ${state.files.length} 個檔案`, 'ok');
        if (!state.statsFetched) {
            state.statsFetched = true;
            fetchAllFileStats(state.files);
        }
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
            const hasDraft = state.draftPaths.has(file.path);
            const row = document.createElement('div');
            row.className = 'file-row';

            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'file-item';
            button.dataset.path = file.path;
            button.classList.toggle('active', state.currentFile?.path === file.path);
            button.innerHTML = `
                <span class="draft-dot ${hasDraft ? '' : 'hidden'}"></span>
                <div class="file-item-body">
                    <span class="file-name">${escapeHtml(file.name.replace(/\.txt$/i, ''))}</span>
                    <span class="file-stats"></span>
                </div>
            `;
            applyFileStats(button, state.fileStats.get(file.path));
            button.addEventListener('click', () => loadDocument(file));
            row.append(button);

            // 有本機草稿時才顯示「恢復原樣」按鈕，一鍵捨棄草稿（例如只是點進去聽一下而誤產生的草稿）。
            const discardButton = document.createElement('button');
            discardButton.type = 'button';
            discardButton.className = `file-discard${hasDraft ? '' : ' hidden'}`;
            discardButton.textContent = '↺';
            discardButton.setAttribute('aria-label', `捨棄草稿並恢復原樣：${file.name.replace(/\.txt$/i, '')}`);
            discardButton.title = '捨棄本機草稿，恢復成上次儲存（遠端）的內容';
            discardButton.addEventListener('click', () => discardDraftFor(file));
            row.append(discardButton);

            section.append(row);
        }
        els.fileList.append(section);
    }
}

function applyFileStats(item, stats) {
    const statsEl = item.querySelector('.file-stats');
    if (!statsEl) return;
    if (!stats) {
        statsEl.textContent = '計算中…';
        item.dataset.status = 'loading';
        return;
    }
    if (stats.error) {
        statsEl.textContent = '讀取失敗';
        item.dataset.status = 'error';
        return;
    }
    statsEl.textContent = `聽 ${stats.played}／校 ${stats.edited}／共 ${stats.total} 段`;
    if (stats.total === 0) {
        item.dataset.status = 'empty';
    } else if (stats.edited >= stats.total && stats.played >= stats.total) {
        item.dataset.status = 'all';
    } else if (stats.played > 0 || stats.edited > 0) {
        item.dataset.status = 'partial';
    } else {
        item.dataset.status = 'none';
    }
}

function computeFileStats(doc) {
    const segments = doc?.segments || [];
    const total = segments.length;
    const played = segments.filter((segment) => segment?.meta?.lastPlayed).length;
    const edited = segments.filter((segment) => segment?.meta?.lastEdited).length;
    return { played, edited, total };
}

function updateFileStatsDom(path) {
    if (!els.fileList) return;
    const item = els.fileList.querySelector(`.file-item[data-path="${CSS.escape(path)}"]`);
    if (!item) return;
    applyFileStats(item, state.fileStats.get(path));
}

async function fetchAllFileStats(files) {
    const queue = files.map((file) => file.path).filter((path) => !state.fileStats.has(path));
    const worker = async () => {
        while (queue.length) {
            const path = queue.shift();
            try {
                state.fileStats.set(path, await fetchFileStats(path));
            } catch (error) {
                state.fileStats.set(path, { error: true });
            }
            updateFileStatsDom(path);
        }
    };
    const concurrency = Math.min(8, queue.length);
    await Promise.all(Array.from({ length: concurrency }, worker));
}

async function fetchFileStats(path) {
    if (state.currentFile?.path === path && state.document) {
        return computeFileStats(state.document);
    }
    const draft = getDraft(path);
    if (draft?.text) {
        try {
            return computeFileStats(parseDocument(draft.text, path));
        } catch { /* fall through to remote fetch */ }
    }
    const filename = path.replace(/^qa\//, '');
    const url = `./${encodeURIComponent(filename)}`;
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const text = await response.text();
    return computeFileStats(parseDocument(text, path));
}

function refreshCurrentFileStats() {
    if (!state.currentFile || !state.document) return;
    state.fileStats.set(state.currentFile.path, computeFileStats(state.document));
    updateFileStatsDom(state.currentFile.path);
}

async function loadDocument(file, { preferDraft = null } = {}) {
    if (state.dirty && !confirm('目前檔案有未儲存修改，確定切換檔案？')) {
        return;
    }

    setStatus(`正在載入 ${file.name}...`, 'loading');
    try {
        const remote = await getFile(file.path);
        const draft = getDraft(file.path);
        let workingText = remote.text;
        let useDraft = false;

        if (draft && preferDraft === null) {
            const choice = await askDraftChoice(file.path, draft);
            if (choice === 'draft') useDraft = true;
            if (choice === 'discard') clearDraft(file.path);
        } else if (draft && preferDraft === true) {
            useDraft = true;
        }

        if (useDraft && typeof draft.text === 'string') {
            workingText = draft.text;
        }

        state.currentFile = file;
        state.currentSha = remote.sha;
        state.originalText = remote.text;
        state.originalDocument = parseDocument(remote.text, file.path);
        state.document = parseDocument(workingText, file.path);
        state.dirty = contentText(serializeDocument(state.document)) !== contentText(remote.text);
        state.draftPaths = listDraftPaths();
        renderFileList();
        renderDocument();
        refreshCurrentFileStats();
        historyReset(serializeDocument(state.document));
        setStatus(state.dirty ? '已載入本機草稿' : '已載入遠端最新版', state.dirty ? 'dirty' : 'ok');
    } catch (error) {
        setStatus(`載入失敗：${error.message}`, 'error');
    }
}

// 從側邊欄直接捨棄某個檔案的本機草稿，恢復成上次儲存（遠端）的內容。
// 主要用來清掉「只是點進去聽一下」誤產生、其實沒有真正校稿的草稿。
function discardDraftFor(file) {
    if (!file || !state.draftPaths.has(file.path)) return;
    const displayName = file.name.replace(/\.txt$/i, '');
    if (!window.confirm(`確定捨棄「${displayName}」的本機草稿，恢復成上次儲存（遠端）的內容嗎？`)) {
        return;
    }

    clearDraft(file.path);
    state.draftPaths = listDraftPaths();

    if (state.currentFile?.path === file.path) {
        // 正在開啟的就是這個檔案：直接還原成遠端原樣，並取消尚未寫入的草稿暫存。
        clearTimeout(state.draftTimer);
        state.document = parseDocument(state.originalText, file.path);
        state.originalDocument = parseDocument(state.originalText, file.path);
        state.dirty = false;
        renderDocument();
        renderFileList();
        refreshCurrentFileStats();
        historyReset(serializeDocument(state.document));
        setStatus('已捨棄草稿，恢復成遠端原樣', 'ok');
        return;
    }

    // 其他檔案：移除草稿標記，再用遠端內容重新計算「聽／校」統計。
    state.fileStats.delete(file.path);
    renderFileList();
    fetchFileStats(file.path)
        .then((stats) => state.fileStats.set(file.path, stats))
        .catch(() => state.fileStats.set(file.path, { error: true }))
        .finally(() => updateFileStatsDom(file.path));
    setStatus(`已捨棄「${displayName}」的本機草稿`, 'ok');
}

// 在重繪期間維持 .workspace 的捲動位置。重繪會清空再重建 #editorRoot，內文框
// 先以最小高度出現、之後才用 microtask 自動長回，這段期間整份內容高度會瞬間
// 塌縮，捲動位置因而被瀏覽器夾到較上面（畫面看起來自己往上捲）。
//
// 與其事後還原，不如直接避免塌縮：重建前先把容器的最小高度鎖在目前高度，整個
// 重建＋長回過程高度都不會掉，捲動位置自然不被夾掉；等文字框長回後（microtask
// 之後的 animation frame）再解除鎖定，並保險地把捲動位置設回原值。
function preserveWorkspaceScroll(render) {
    const scroller = els.workspace;
    if (!scroller) {
        render();
        return;
    }
    const savedScrollTop = scroller.scrollTop;
    const root = els.editorRoot;
    const lockedHeight = root ? root.offsetHeight : 0;
    if (root && lockedHeight) {
        root.style.minHeight = `${lockedHeight}px`;
    }
    try {
        render();
    } finally {
        scroller.scrollTop = savedScrollTop;
        requestAnimationFrame(() => {
            if (root) root.style.minHeight = '';
            scroller.scrollTop = savedScrollTop;
        });
    }
}

function renderDocument() {
    if (!state.document || !state.currentFile) return;

    // Play buttons are re-created here, so any previously active segment is gone.
    setActiveSegment(null);
    els.welcomePanel.classList.add('hidden');
    els.documentPanel.classList.remove('hidden');
    els.documentPath.textContent = state.currentFile.path;
    els.documentTitle.textContent = state.document.title || fileTitleFromPath(state.currentFile.path);
    els.segmentCount.textContent = `${state.document.segments.length} 段`;
    els.draftBadge.classList.toggle('hidden', !state.draftPaths.has(state.currentFile.path));
    els.saveButton.disabled = !state.dirty;
    refreshMetaSummary();
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
    // 開頭與第一段之間同樣靠結尾空白行分隔，編輯框不顯示這些尾端空行，儲存時補回。
    const headerTrailing = state.document.header.match(/\s*$/)[0];
    textarea.value = state.document.header.slice(0, state.document.header.length - headerTrailing.length);
    const trackHeaderCaret = () => {
        state.editorCaret = {
            kind: 'header',
            offset: textarea.selectionStart ?? textarea.value.length,
            end: textarea.selectionEnd ?? undefined,
        };
    };
    textarea.addEventListener('input', () => {
        state.document.header = textarea.value + headerTrailing;
        state.document.headerRanges = parseRanges(state.document.header);
        rangeContainer.innerHTML = '';
        rangeContainer.append(...renderRangeButtons(state.document.headerRanges, '開場'));
        trackHeaderCaret();
        scheduleHistoryCommit();
        recomputeDirty();
        autoGrow(textarea);
    });
    textarea.addEventListener('focus', trackHeaderCaret);
    textarea.addEventListener('click', trackHeaderCaret);
    textarea.addEventListener('keyup', trackHeaderCaret);
    attachTextareaIME(textarea);
    queueMicrotask(() => autoGrow(textarea, { allowShrink: true }));
    return card;
}

function renderSegmentCard(segment, segmentIndex) {
    const node = els.segmentTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.segmentIndex = String(segmentIndex);
    node.querySelector('.segment-number').textContent = segment.number ? `第 ${segment.number} 段` : '全文';
    setupSegmentTitle(node, segment, segmentIndex);
    updateSegmentMetaChips(node, segment);
    node.querySelector('.reset-segment').addEventListener('click', () => resetSegment(segmentIndex));
    for (const button of node.querySelectorAll('.seg-meta-clear')) {
        button.addEventListener('click', () => clearSegmentMeta(segmentIndex, button.dataset.field));
    }

    const copyButton = node.querySelector('.copy-segment');
    copyButton?.addEventListener('click', () => copySegmentAnswer(segmentIndex, copyButton));

    const mergeUpButton = node.querySelector('.merge-up');
    const mergeDownButton = node.querySelector('.merge-down');
    const splitButton = node.querySelector('.split-segment');
    const deleteButton = node.querySelector('.delete-segment');
    const structuralEnabled = state.document.mode === 'segments';
    if (!structuralEnabled) {
        for (const button of [mergeUpButton, mergeDownButton, splitButton, deleteButton]) {
            button?.classList.add('hidden');
        }
    } else {
        if (mergeUpButton) {
            mergeUpButton.disabled = segmentIndex === 0;
            mergeUpButton.addEventListener('click', () => mergeSegmentWithNext(segmentIndex - 1));
        }
        if (mergeDownButton) {
            mergeDownButton.disabled = segmentIndex >= state.document.segments.length - 1;
            mergeDownButton.addEventListener('click', () => mergeSegmentWithNext(segmentIndex));
        }
        splitButton?.addEventListener('click', () => splitSegmentHere(segmentIndex));
        if (deleteButton) {
            deleteButton.disabled = state.document.segments.length <= 1;
            deleteButton.addEventListener('click', () => deleteSegmentAt(segmentIndex));
        }
    }

    const body = node.querySelector('.segment-body');
    for (const [partIndex, part] of segment.parts.entries()) {
        if (part.type === 'marker') {
            // 「### N.」標題已併入卡片上方的可編輯大標題，不再於內文重複顯示。
            if (/^###\s+/.test(part.text)) continue;
            body.append(renderMarker(part.text, segment, segmentIndex, partIndex, node));
        } else {
            const textarea = document.createElement('textarea');
            textarea.className = 'editor-textarea';
            textarea.spellcheck = false;
            // 段落之間靠結尾的空白行分隔（屬於檔案格式）。編輯框只顯示實際文字、
            // 結尾不放這些空白行，避免框尾多出空行；儲存時再原樣補回，內容不變。
            const trailing = part.text.match(/\s*$/)[0];
            textarea.value = part.text.slice(0, part.text.length - trailing.length);
            textarea.dataset.segmentIndex = String(segmentIndex);
            textarea.dataset.partIndex = String(partIndex);
            textarea.addEventListener('input', () => {
                state.document.segments[segmentIndex].parts[partIndex].text = textarea.value + trailing;
                recordBodyCaret(segmentIndex, partIndex, textarea);
                scheduleHistoryCommit();
                onSegmentEdit(segmentIndex);
                autoGrow(textarea);
            });
            const trackCaret = () => recordBodyCaret(segmentIndex, partIndex, textarea);
            textarea.addEventListener('focus', trackCaret);
            textarea.addEventListener('click', trackCaret);
            textarea.addEventListener('keyup', trackCaret);
            textarea.addEventListener('select', trackCaret);
            attachTextareaIME(textarea);
            body.append(textarea);
            queueMicrotask(() => autoGrow(textarea, { allowShrink: true }));
        }
    }

    return node;
}

// 卡片上方的大標題就是該段的「### N. 提問」，可直接編輯。編輯時只改提問文字，
// 段號（N）維持不變並寫回對應的標題列，避免內文再重複顯示一次標題。
function setupSegmentTitle(node, segment, segmentIndex) {
    const field = node.querySelector('.segment-title');
    if (!field) return;
    field.value = segment.title || '';

    const headingPartIndex = segment.parts.findIndex(
        (part) => part.type === 'marker' && /^###\s+/.test(part.text)
    );
    if (headingPartIndex < 0) {
        // 沒有「### N.」標題的段落（例如全文模式）：標題僅供顯示，不可編輯。
        field.readOnly = true;
        queueMicrotask(() => autoGrow(field, { allowShrink: true }));
        return;
    }

    const trackTitleCaret = () => {
        state.editorCaret = {
            kind: 'title',
            segmentIndex,
            offset: field.selectionStart ?? field.value.length,
            end: field.selectionEnd ?? undefined,
        };
    };
    // 標題維持單行：按 Enter 不換行。
    field.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') event.preventDefault();
    });
    field.addEventListener('input', () => {
        if (field.value.includes('\n')) {
            const caret = field.selectionStart;
            field.value = field.value.replace(/\n+/g, ' ');
            try { field.setSelectionRange(caret, caret); } catch (_) { /* noop */ }
        }
        const title = field.value;
        segment.title = title;
        const headingPart = segment.parts[headingPartIndex];
        const endsWithNewline = /\n$/.test(headingPart.text);
        const heading = segment.number ? `### ${segment.number}. ${title}` : `### ${title}`;
        headingPart.text = endsWithNewline ? `${heading}\n` : heading;
        trackTitleCaret();
        scheduleHistoryCommit();
        onSegmentEdit(segmentIndex);
        autoGrow(field, { allowShrink: true });
    });
    field.addEventListener('focus', trackTitleCaret);
    field.addEventListener('click', trackTitleCaret);
    field.addEventListener('keyup', trackTitleCaret);
    attachTextareaIME(field);
    queueMicrotask(() => autoGrow(field, { allowShrink: true }));
}

function updateSegmentMetaChips(card, segment) {
    const played = card.querySelector('.seg-meta-played');
    const edited = card.querySelector('.seg-meta-edited');
    const hasPlayed = Boolean(segment?.meta?.lastPlayed);
    const hasEdited = Boolean(segment?.meta?.lastEdited);
    if (played) played.textContent = segment?.meta?.lastPlayed || '—';
    if (edited) edited.textContent = segment?.meta?.lastEdited || '—';
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
    if (!card) return;
    updateSegmentMetaChips(card, state.document?.segments?.[segmentIndex]);
}

function renderMarker(text, segment, segmentIndex, partIndex, card) {
    const marker = document.createElement('div');
    marker.className = 'marker-line';

    const endsWithNewline = /\n$/.test(text);
    const displayValue = endsWithNewline ? text.slice(0, -1) : text;
    const kind = detectMarkerKind(displayValue);
    const isHeading = kind === 'heading';

    // Format A: the heading carries the (possibly long) question, so render it
    // as a wrapping, auto-growing textarea. Time/other markers stay single-line.
    const field = document.createElement(isHeading ? 'textarea' : 'input');
    if (!isHeading) field.type = 'text';
    field.className = isHeading ? 'marker-input marker-heading' : 'marker-input';
    field.value = displayValue;
    field.spellcheck = false;
    field.dataset.segmentIndex = String(segmentIndex);
    field.dataset.partIndex = String(partIndex);
    if (isHeading) {
        field.rows = 1;
        field.setAttribute('aria-label', '段落提問（格式：### N. 提問內容）');
        field.title = '段落提問（格式：### N. 提問內容）';
    } else if (kind === 'time') {
        field.setAttribute('aria-label', '段落時間（格式：時間：HH:MM:SS.mmm - HH:MM:SS.mmm）');
        field.title = '格式：時間：HH:MM:SS.mmm - HH:MM:SS.mmm';
    }
    marker.append(field);

    let playButton = null;
    if (kind === 'time') {
        playButton = document.createElement('button');
        playButton.type = 'button';
        playButton.className = 'button button-secondary play-range';
        playButton.dataset.segmentIndex = String(segmentIndex);
        marker.append(playButton);
        updatePlayButton(playButton, displayValue, segment);

        // Baseline for detecting which edge the user changed on manual edits.
        const initRange = parseRanges(displayValue)[0];
        if (initRange) {
            field.dataset.startTc = initRange.startLabel;
            field.dataset.endTc = initRange.endLabel;
        }

        // Keep the shared boundary with the neighbour in sync when the time is
        // edited by hand (committed on blur), so it only needs editing once.
        field.addEventListener('change', () => {
            const range = parseRanges(field.value)[0];
            if (!range) return;
            const startChanged = range.startLabel !== field.dataset.startTc;
            const endChanged = range.endLabel !== field.dataset.endTc;
            field.dataset.startTc = range.startLabel;
            field.dataset.endTc = range.endLabel;
            if (startChanged) setSegmentEdge(segmentIndex - 1, 'end', range.start, { markEdited: false });
            if (endChanged) setSegmentEdge(segmentIndex + 1, 'start', range.end, { markEdited: false });
            commitHistory();
        });
    }

    const trackMarkerCaret = () => {
        state.editorCaret = {
            kind: 'marker',
            segmentIndex,
            partIndex,
            offset: field.selectionStart ?? field.value.length,
            end: field.selectionEnd ?? undefined,
        };
    };
    field.addEventListener('focus', trackMarkerCaret);
    field.addEventListener('click', trackMarkerCaret);
    field.addEventListener('keyup', trackMarkerCaret);

    if (isHeading) {
        // Keep the heading on one logical line.
        field.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') event.preventDefault();
        });
    }

    field.addEventListener('input', () => {
        if (isHeading && field.value.includes('\n')) {
            const caret = field.selectionStart;
            field.value = field.value.replace(/\n+/g, ' ');
            try { field.setSelectionRange(caret, caret); } catch (_) { /* noop */ }
        }
        const newValue = field.value;
        const newText = endsWithNewline ? `${newValue}\n` : newValue;
        state.document.segments[segmentIndex].parts[partIndex].text = newText;

        if (isHeading) {
            const match = newValue.match(/^###\s+(\d+)\.\s*(.*)$/);
            if (match) {
                segment.number = match[1];
                segment.title = match[2];
            } else {
                segment.number = '';
                segment.title = newValue.trim();
            }
            updateSegmentCardHeader(card, segment);
            autoGrow(field, { allowShrink: true });
        }

        if (playButton) {
            updatePlayButton(playButton, newValue, segment);
        }

        segment.ranges = collectSegmentRanges(state.document.segments[segmentIndex]);
        trackMarkerCaret();
        scheduleHistoryCommit();
        onSegmentEdit(segmentIndex);
    });

    if (isHeading) {
        attachTextareaIME(field);
        queueMicrotask(() => autoGrow(field, { allowShrink: true }));
    }

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
            setMiniPlayerHidden(false);
            await audio.playRange(state.currentFile.path, range, `${segment.number}. ${segment.title}`);
            onSegmentPlayed(segment.index);
            setActiveSegment(segment.index);
        } catch (error) {
            setStatus(`播放失敗：${error.message}`, 'error');
        }
    };
}

// Remember which segment the player is working on so the floating「設起始／設結束」
// buttons know which segment's time to update. null disables those buttons.
function setActiveSegment(index) {
    state.activeSegmentIndex = index == null ? null : index;
    const disabled = state.activeSegmentIndex == null;
    if (els.setStartButton) els.setStartButton.disabled = disabled;
    if (els.setEndButton) els.setEndButton.disabled = disabled;
}

// Current playhead position of the floating player, in seconds, or null when
// no audio file has been loaded yet.
function playerCurrentTime() {
    const player = els.audioPlayer;
    if (!player || !player.src) return null;
    const t = player.currentTime;
    return Number.isFinite(t) ? t : null;
}

// Set one edge (start/end) of a segment's 時間 marker to `seconds`, keeping the
// other edge. Updates the data model, the rendered field and its play button.
// Returns false when the segment has no time marker (e.g. out of range).
function setSegmentEdge(segmentIndex, edge, seconds, { markEdited = true } = {}) {
    const segment = state.document?.segments?.[segmentIndex];
    if (!segment) return false;
    const partIndex = segment.parts.findIndex(
        (part) => part.type === 'marker' && /^(時間|開場時間)：/.test(part.text)
    );
    if (partIndex < 0) return false;
    const range = parseRanges(segment.parts[partIndex].text)[0] || { start: 0, end: 0 };
    const start = edge === 'start' ? seconds : range.start;
    const end = edge === 'end' ? seconds : range.end;
    writeSegmentRange(segment, segmentIndex, partIndex, start, end, { markEdited });
    return true;
}

function writeSegmentRange(segment, segmentIndex, partIndex, startSeconds, endSeconds, { markEdited = true } = {}) {
    const part = segment.parts[partIndex];
    const endsWithNewline = /\n$/.test(part.text);
    const prefix = /^開場時間/.test(part.text) ? '開場時間' : '時間';
    const startTc = secondsToTimecode(Math.max(0, startSeconds));
    const endTc = secondsToTimecode(Math.max(0, endSeconds));
    const display = `${prefix}：${startTc} - ${endTc}`;
    part.text = endsWithNewline ? `${display}\n` : display;
    segment.ranges = collectSegmentRanges(segment);

    const card = els.editorRoot.querySelector(`.segment-card[data-segment-index="${segmentIndex}"]`);
    const input = card?.querySelector(`.marker-input[data-part-index="${partIndex}"]`);
    if (input) {
        input.value = display;
        input.dataset.startTc = startTc;
        input.dataset.endTc = endTc;
        const playButton = input.closest('.marker-line')?.querySelector('.play-range');
        if (playButton) updatePlayButton(playButton, display, segment);
    }
    if (markEdited) {
        onSegmentEdit(segmentIndex);
    } else {
        // 共用邊界連動：鄰段時間被自動跟著調整，不算使用者手動編輯，
        // 所以不更新該段「最後編輯」時間（仍會標記未存、需要儲存）。
        recomputeDirty();
    }
}

// Apply the player's current time to one edge of a segment, then propagate the
// shared boundary to the neighbour so it does not have to be edited twice.
function applyPlayerTime(segmentIndex, edge, seconds) {
    commitHistory();
    if (!setSegmentEdge(segmentIndex, edge, seconds)) return;
    if (edge === 'start') setSegmentEdge(segmentIndex - 1, 'end', seconds, { markEdited: false });
    else setSegmentEdge(segmentIndex + 1, 'start', seconds, { markEdited: false });
    const segment = state.document.segments[segmentIndex];
    const label = edge === 'start' ? '起始' : '結束';
    setStatus(`已將第 ${segment.number || segmentIndex + 1} 段${label}時間設為 ${secondsToTimecode(seconds)}`, 'ok');
    state.editorCaret = { kind: 'title', segmentIndex };
    commitHistory();
}

// 只設定這一段的起始／結束時間，不連動相鄰段落的共用邊界（「設起始／設結束」
// 按鈕的右鍵選單會走這條路）。
function applyPlayerTimeSingle(segmentIndex, edge, seconds) {
    commitHistory();
    if (!setSegmentEdge(segmentIndex, edge, seconds)) return;
    const segment = state.document.segments[segmentIndex];
    const label = edge === 'start' ? '起始' : '結束';
    const note = edge === 'start' ? '（未連動上一段結束）' : '（未連動下一段起始）';
    setStatus(`已將第 ${segment.number || segmentIndex + 1} 段${label}時間設為 ${secondsToTimecode(seconds)}${note}`, 'ok');
    state.editorCaret = { kind: 'title', segmentIndex };
    commitHistory();
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
            setMiniPlayerHidden(false);
            await audio.playRange(state.currentFile.path, range, label);
            // Header / generic ranges are not tied to a segment edge.
            setActiveSegment(null);
        } catch (error) {
            setStatus(`播放失敗：${error.message}`, 'error');
        }
    });
    return button;
}

function onSegmentEdit(segmentIndex) {
    const segment = state.document?.segments?.[segmentIndex];
    if (!segment) {
        recomputeDirty();
        return;
    }
    const original = state.originalDocument?.segments?.[segmentIndex];
    const bodyNow = segmentBodyText(segment);
    const bodyOriginal = segmentBodyText(original);
    segment.meta = segment.meta || { lastPlayed: '', lastEdited: '' };
    if (bodyNow !== bodyOriginal) {
        segment.meta.lastEdited = formatTimestamp();
    } else {
        segment.meta.lastEdited = original?.meta?.lastEdited || '';
    }
    refreshSegmentMetaChips(segmentIndex);
    recomputeDirty();
}

function onSegmentPlayed(segmentIndex) {
    const segment = state.document?.segments?.[segmentIndex];
    if (!segment) return;
    // 先把尚未收尾的打字收成一步，避免播放標記把它一起吃掉。
    commitHistory();
    segment.meta = segment.meta || { lastPlayed: '', lastEdited: '' };
    segment.meta.lastPlayed = formatTimestamp();
    refreshSegmentMetaChips(segmentIndex);
    recomputeDirty();
    // 「最後播放」只是收聽進度，不列入可復原的編輯步驟。
    syncHistoryBaseline();
}

function clearSegmentMeta(segmentIndex, field) {
    const segment = state.document?.segments?.[segmentIndex];
    if (!segment) return;
    segment.meta = segment.meta || { lastPlayed: '', lastEdited: '' };
    commitHistory();
    if (field === 'played') {
        if (!segment.meta.lastPlayed) return;
        segment.meta.lastPlayed = '';
        setStatus('已清除最後播放時間', 'ok');
    } else if (field === 'edited') {
        if (!segment.meta.lastEdited) return;
        segment.meta.lastEdited = '';
        setStatus('已清除最後編輯時間', 'ok');
    } else {
        return;
    }
    refreshSegmentMetaChips(segmentIndex);
    recomputeDirty();
    state.editorCaret = { kind: 'title', segmentIndex };
    commitHistory();
}

function resetSegment(segmentIndex) {
    const original = state.originalDocument?.segments?.[segmentIndex];
    if (!original) return;
    commitHistory();
    state.document.segments[segmentIndex] = cloneDocument({ segments: [original] }).segments[0];
    recomputeDirty();
    renderDocument();
    state.editorCaret = { kind: 'title', segmentIndex };
    commitHistory();
}

function recordBodyCaret(segmentIndex, partIndex, textarea) {
    const offset = textarea.selectionStart ?? textarea.value.length;
    state.bodyCaret = { segmentIndex, partIndex, offset };
    state.editorCaret = {
        kind: 'body',
        segmentIndex,
        partIndex,
        offset,
        end: textarea.selectionEnd ?? undefined,
    };
}

function afterStructuralChange(message, caret = null) {
    state.bodyCaret = null;
    // 讓復原／重做能捲回這次結構變更影響的段落。
    if (caret) state.editorCaret = caret;
    recomputeDirty();
    renderDocument();
    setStatus(message, 'ok');
    commitHistory();
}

function mergeSegmentWithNext(firstIndex) {
    const segments = state.document?.segments || [];
    if (firstIndex < 0 || firstIndex >= segments.length - 1) return;
    commitHistory();
    mergeWithNext(state.document, firstIndex);
    afterStructuralChange(
        `已合併第 ${firstIndex + 1}、${firstIndex + 2} 段，請確認時間與內容`,
        { kind: 'title', segmentIndex: firstIndex }
    );
}

function deleteSegmentAt(segmentIndex) {
    const segments = state.document?.segments || [];
    if (segmentIndex < 0 || segmentIndex >= segments.length) return;
    if (segments.length <= 1) {
        setStatus('至少要保留一段，無法刪除最後一段', 'error');
        return;
    }
    const segment = segments[segmentIndex];
    const name = segment?.title ? `第 ${segmentIndex + 1} 段「${segment.title}」` : `第 ${segmentIndex + 1} 段`;
    if (!window.confirm(`確定要刪除${name}嗎？刪除後其餘段落會重新編號，需按「儲存到 GitHub」才會真正寫回。`)) {
        return;
    }
    commitHistory();
    removeSegment(state.document, segmentIndex);
    const focusIndex = Math.min(segmentIndex, state.document.segments.length - 1);
    afterStructuralChange(
        `已刪除${name}，後面的段落已重新編號`,
        { kind: 'title', segmentIndex: Math.max(0, focusIndex) }
    );
}

function splitSegmentHere(segmentIndex) {
    const segment = state.document?.segments?.[segmentIndex];
    if (!segment) return;

    let partIndex;
    let offset;
    const caret = state.bodyCaret;
    if (caret && caret.segmentIndex === segmentIndex) {
        ({ partIndex, offset } = caret);
    } else {
        const fallback = findSecondQuestion(segment);
        if (!fallback) {
            setStatus('請先把游標點在這一段裡要拆分的位置，再按「從游標拆分」', 'error');
            return;
        }
        ({ partIndex, offset } = fallback);
    }

    const part = segment.parts[partIndex];
    if (!part || part.type !== 'chunk') {
        setStatus('請把游標停在段落內文（不是標題或時間列）再拆分', 'error');
        return;
    }
    const before = part.text.slice(0, offset);
    const after = part.text.slice(offset);
    if (!before.trim() || !after.trim()) {
        setStatus('拆分點在段落最前或最後，沒有可分出的內容', 'error');
        return;
    }

    commitHistory();
    splitSegment(state.document, segmentIndex, partIndex, offset);
    afterStructuralChange(
        `已將第 ${segmentIndex + 1} 段拆成兩段，請補上新段提問並校正時間`,
        { kind: 'title', segmentIndex: segmentIndex + 1 }
    );
}

// 比較內文時忽略「最後播放」時間：單純聽過不算修改。只有真正改到內文／結構／
// 時間／最後編輯時，文件才會被視為有未存修改，也才會自動存成本機草稿。
function contentText(text) {
    return String(text).replace(/^最後播放：[ \t]*(?:\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})?[ \t]*\r?\n?/gm, '');
}

function recomputeDirty() {
    if (!state.document) return;
    const text = serializeDocument(state.document);
    state.dirty = contentText(text) !== contentText(state.originalText);
    if (state.dirty && state.currentFile) {
        scheduleDraftSave(text);
    } else if (state.currentFile) {
        // 還原成原樣（或只是聽過）時，取消尚未寫入的草稿暫存並清掉既有草稿。
        clearTimeout(state.draftTimer);
        clearDraft(state.currentFile.path);
        state.draftPaths = listDraftPaths();
        els.draftBadge.classList.add('hidden');
    }
    refreshMetaSummary();
    refreshCurrentFileStats();
    refreshDirtyUI();
}

function scheduleDraftSave(text) {
    clearTimeout(state.draftTimer);
    state.draftTimer = setTimeout(() => {
        if (!state.currentFile) return;
        setDraft(state.currentFile.path, text, state.currentSha);
        state.draftPaths = listDraftPaths();
        els.draftBadge.classList.remove('hidden');
        renderFileList();
    }, 500);
}

// ---- 編輯歷史（上一步／下一步） ----------------------------------------
// 載入或儲存檔案時呼叫，把目前文件設成歷史基準並清空上一步／下一步堆疊。
function historyReset(text) {
    history.undo = [];
    history.redo = [];
    history.committed = { text, caret: null };
    clearTimeout(history.timer);
    history.timer = null;
    state.editorCaret = null;
    updateHistoryButtons();
}

function currentEditorCaret() {
    return state.editorCaret ? { ...state.editorCaret } : null;
}

// 把目前文件狀態收成一步歷史；若內容與上一個基準相同則略過（避免空步）。
function commitHistory() {
    clearTimeout(history.timer);
    history.timer = null;
    if (!state.document) return;
    const text = serializeDocument(state.document);
    if (!history.committed) {
        history.committed = { text, caret: currentEditorCaret() };
        updateHistoryButtons();
        return;
    }
    if (text === history.committed.text) return;
    history.undo.push(history.committed);
    if (history.undo.length > HISTORY_LIMIT) history.undo.shift();
    history.redo = [];
    history.committed = { text, caret: currentEditorCaret() };
    updateHistoryButtons();
}

// 連續打字：停頓一段時間後才合併成一步，避免每個字都變成一步。
function scheduleHistoryCommit() {
    clearTimeout(history.timer);
    history.timer = setTimeout(commitHistory, 600);
}

// 純聽過所產生的「最後播放」更新不該變成可復原的一步：直接併入基準。
function syncHistoryBaseline() {
    if (!state.document) return;
    const text = serializeDocument(state.document);
    if (!history.committed) {
        history.committed = { text, caret: currentEditorCaret() };
    } else {
        history.committed.text = text;
    }
}

function undoEdit() {
    commitHistory();
    if (!history.undo.length) {
        setStatus('沒有可復原的步驟', 'ok');
        return;
    }
    // 被「撤銷」的那一步，其變更位置記在我們正要離開的快照上（它的 caret 是
    // 產生這一步時的游標處），所以復原後要捲到這個位置，才會對到改變處。
    const leaving = history.committed;
    history.redo.push(leaving);
    history.committed = history.undo.pop();
    restoreHistorySnapshot(history.committed, leaving.caret);
    setStatus('已復原上一步', 'ok');
}

function redoEdit() {
    commitHistory();
    if (!history.redo.length) {
        setStatus('沒有可重做的步驟', 'ok');
        return;
    }
    history.undo.push(history.committed);
    // 被「重做」的那一步，其變更位置就記在要還原的目標快照上。
    const target = history.redo.pop();
    history.committed = target;
    restoreHistorySnapshot(target, target.caret);
    setStatus('已重做下一步', 'ok');
}

function restoreHistorySnapshot(snapshot, caret) {
    if (!snapshot || !state.currentFile) return;
    state.document = parseDocument(snapshot.text, state.currentFile.path);
    state.bodyCaret = null;
    recomputeDirty();
    renderDocument();
    restoreEditorCaret(caret === undefined ? snapshot.caret : caret);
    updateHistoryButtons();
}

// 復原／重做後，盡量把游標放回原本編輯的欄位與位置。
function restoreEditorCaret(caret) {
    if (!caret) return;
    let field = null;
    if (caret.kind === 'header') {
        field = els.editorRoot.querySelector('textarea[data-header="true"]');
    } else {
        const card = els.editorRoot.querySelector(
            `.segment-card[data-segment-index="${caret.segmentIndex}"]`
        );
        if (!card) return;
        if (caret.kind === 'title') {
            field = card.querySelector('.segment-title');
        } else if (caret.partIndex != null) {
            field = card.querySelector(`[data-part-index="${caret.partIndex}"]`);
        }
    }
    if (!field) return;
    try {
        field.focus({ preventScroll: true });
        const len = field.value.length;
        const start = Math.min(caret.offset ?? len, len);
        const end = Math.min(caret.end ?? start, len);
        field.setSelectionRange(start, end);
    } catch (_) { /* 某些欄位不支援選取範圍，略過 */ }
    // 重繪後各文字框會以 microtask 自動調整高度，會改變版面位置；等下一個
    // 動畫影格、版面定案後再捲動，捲到的位置才會精準對到改變處。
    requestAnimationFrame(() => {
        field.scrollIntoView({ block: 'center' });
    });
}

function updateHistoryButtons() {
    if (els.undoButton) els.undoButton.disabled = history.undo.length === 0;
    if (els.redoButton) els.redoButton.disabled = history.redo.length === 0;
}

function refreshMetaSummary() {
    const segments = state.document?.segments || [];
    const total = segments.length;
    let both = 0;
    let playedOnly = 0;
    let editedOnly = 0;
    let none = 0;
    for (const segment of segments) {
        const p = Boolean(segment?.meta?.lastPlayed);
        const e = Boolean(segment?.meta?.lastEdited);
        if (p && e) both += 1;
        else if (p) playedOnly += 1;
        else if (e) editedOnly += 1;
        else none += 1;
    }
    if (els.metaTotalCount) els.metaTotalCount.textContent = String(total);
    if (els.metaBothCount) els.metaBothCount.textContent = String(both);
    if (els.metaPlayedOnlyCount) els.metaPlayedOnlyCount.textContent = String(playedOnly);
    if (els.metaEditedOnlyCount) els.metaEditedOnlyCount.textContent = String(editedOnly);
    if (els.metaNoneCount) els.metaNoneCount.textContent = String(none);
}

function segmentBodyText(segment) {
    return segment?.parts?.map((part) => part.text).join('') || '';
}

// 「答疑內容」＝段落內文（Taiguanglin：…），不含「### 提問」「時間」等標記列，
// 也不含「最後播放／最後編輯」。複製鈕用它把師父的回答原文放進剪貼簿。
function segmentAnswerText(segment) {
    return (segment?.parts || [])
        .filter((part) => part.type === 'chunk')
        .map((part) => part.text)
        .join('')
        .trim();
}

async function copySegmentAnswer(segmentIndex, button) {
    const segment = state.document?.segments?.[segmentIndex];
    if (!segment) return;
    const text = segmentAnswerText(segment);
    if (!text) {
        setStatus('這一段沒有可複製的答疑內容', 'error');
        return;
    }
    const ok = await copyTextToClipboard(text);
    if (ok) {
        setStatus(`已複製第 ${segment.number || segmentIndex + 1} 段答疑內容`, 'ok');
        flashCopyButton(button);
    } else {
        setStatus('複製失敗，請改用手動選取複製', 'error');
    }
}

async function copyTextToClipboard(text) {
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch (_) { /* 權限或非安全環境失敗時，改走下方備援 */ }
    try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.top = '-1000px';
        textarea.style.opacity = '0';
        document.body.append(textarea);
        textarea.select();
        const ok = document.execCommand('copy');
        textarea.remove();
        return ok;
    } catch (_) {
        return false;
    }
}

function flashCopyButton(button) {
    if (!button) return;
    const original = button.dataset.label || button.textContent;
    button.dataset.label = original;
    button.classList.add('copied');
    button.textContent = '✓';
    clearTimeout(button._copyTimer);
    button._copyTimer = setTimeout(() => {
        button.textContent = button.dataset.label || original;
        button.classList.remove('copied');
    }, 1200);
}

function formatTimestamp(date = new Date()) {
    const pad = (value) => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

async function saveCurrentFile({ force = false, reason = 'edit' } = {}) {
    if (!state.currentFile || !state.document) return;

    // 把尚未收尾的打字先收成一步歷史，存檔後仍可往回復原。
    commitHistory();
    const playedOnly = reason === 'played';
    const finalText = serializeDocument(state.document);

    if (!force && finalText === state.originalText) {
        setStatus(playedOnly ? '沒有可儲存的收聽進度' : '沒有需要儲存的修改', 'ok');
        state.dirty = false;
        refreshDirtyUI();
        return;
    }

    if (!getPat()) {
        openSettings('請先設定 GitHub PAT 才能儲存。');
        return;
    }

    els.saveButton.disabled = true;
    if (els.savePlayedButton) els.savePlayedButton.disabled = true;
    setStatus(playedOnly ? '正在儲存收聽進度...' : '正在儲存到 GitHub...', 'loading');
    try {
        const action = playedOnly ? 'update listen progress' : 'edit';
        const message = `qa: ${action} ${state.currentFile.name} via web editor (${new Date().toLocaleString('zh-TW')})`;
        const result = await putFile(state.currentFile.path, finalText, state.currentSha, message, { force });
        state.currentSha = result.content.sha;
        state.originalText = finalText;
        state.originalDocument = parseDocument(finalText, state.currentFile.path);
        state.document = parseDocument(finalText, state.currentFile.path);
        state.dirty = false;
        clearDraft(state.currentFile.path);
        state.draftPaths = listDraftPaths();
        renderFileList();
        // 重繪會把內文框重建並從最小高度開始（之後才以 microtask 自動長回），
        // 過程中捲動高度短暫塌縮，捲動位置會被夾到頂端，畫面因此往上跳。
        // 存檔不需要移動視角，所以記住目前捲動位置，等版面長回後再還原。
        preserveWorkspaceScroll(() => {
            renderDocument();
            refreshCurrentFileStats();
        });
        setStatus(playedOnly ? '已將收聽進度儲存到 GitHub' : '已儲存並建立 GitHub commit', 'ok');
    } catch (error) {
        if (isConflict(error)) {
            await handleConflict(finalText);
        } else {
            setStatus(`儲存失敗：${error.message}`, 'error');
            els.saveButton.disabled = !state.dirty;
            updateSavePlayedButton();
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

// 是否有「只聽過、沒有任何內文編輯」的收聽進度尚未存回 GitHub。
// 條件：完整內容與遠端不同，但忽略「最後播放」後的內文相同（差異只在收聽進度）。
function hasUnsavedPlayProgress() {
    if (!state.document || !state.currentFile) return false;
    const full = serializeDocument(state.document);
    return full !== state.originalText && contentText(full) === contentText(state.originalText);
}

// 只有在「單純聽過、沒有校稿編輯」時才顯示「存收聽進度」按鈕；有內文修改時
// 交給主要的「儲存到 GitHub」按鈕處理（它本來就會一併存入收聽進度）。
function updateSavePlayedButton() {
    if (!els.savePlayedButton) return;
    const show = hasUnsavedPlayProgress();
    els.savePlayedButton.classList.toggle('hidden', !show);
    els.savePlayedButton.disabled = !show;
}

function refreshDirtyUI() {
    els.saveButton.disabled = !state.dirty;
    updateSavePlayedButton();
    els.draftBadge.classList.toggle('hidden', !(state.currentFile && state.draftPaths.has(state.currentFile.path)));
    setStatus(state.dirty ? '有未儲存修改' : '已同步', state.dirty ? 'dirty' : 'ok');

    const originalSegments = state.originalDocument?.segments || [];
    for (const card of els.editorRoot.querySelectorAll('.segment-card[data-segment-index]')) {
        const index = Number(card.dataset.segmentIndex);
        const current = segmentSnapshot(state.document.segments[index]);
        const original = segmentSnapshot(originalSegments[index]);
        card.querySelector('.segment-dirty')?.classList.toggle('hidden', current === original);
    }
}

function segmentSnapshot(segment) {
    // 「最後播放」不列入比較：單純聽過不算修改，段落不會被標成「未存」。
    return JSON.stringify({
        body: segmentBodyText(segment),
        lastEdited: segment?.meta?.lastEdited || '',
    });
}

function setStatus(message, type = 'ok') {
    els.saveStatus.textContent = message;
    els.saveStatus.dataset.type = type;
}

function openSettings(message = '') {
    els.patInput.value = getPat();
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

const composingTextareas = new WeakSet();
const MIN_TEXTAREA_HEIGHT = 80;
// Headings hold a single-line question, so they start at one line and only grow
// when the text actually wraps (the body answer boxes keep the taller floor).
const MIN_HEADING_HEIGHT = 34;

function autoGrow(textarea, { allowShrink = false } = {}) {
    if (composingTextareas.has(textarea)) return;
    const scroller = textarea.closest('.workspace');
    const savedScrollTop = scroller?.scrollTop ?? null;
    const headingLike = textarea.classList.contains('marker-heading') || textarea.classList.contains('segment-title');
    const floor = headingLike ? MIN_HEADING_HEIGHT : MIN_TEXTAREA_HEIGHT;
    if (allowShrink) {
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.max(floor, textarea.scrollHeight + 2)}px`;
    } else {
        const needed = Math.max(floor, textarea.scrollHeight + 2);
        if (needed > textarea.clientHeight) {
            textarea.style.height = `${needed}px`;
        }
    }
    if (scroller && savedScrollTop !== null && scroller.scrollTop !== savedScrollTop) {
        scroller.scrollTop = savedScrollTop;
    }
}

function attachTextareaIME(textarea) {
    textarea.addEventListener('compositionstart', () => {
        composingTextareas.add(textarea);
    });
    textarea.addEventListener('compositionend', () => {
        composingTextareas.delete(textarea);
        autoGrow(textarea);
    });
    textarea.addEventListener('blur', () => {
        composingTextareas.delete(textarea);
        autoGrow(textarea, { allowShrink: true });
    });
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

// ---- 通用右鍵選單 -------------------------------------------------------
let activeContextMenu = null;

function closeContextMenu() {
    if (!activeContextMenu) return;
    activeContextMenu.remove();
    activeContextMenu = null;
    document.removeEventListener('pointerdown', onContextMenuPointerDown, true);
    document.removeEventListener('keydown', onContextMenuKeyDown, true);
    document.removeEventListener('scroll', closeContextMenu, true);
    window.removeEventListener('blur', closeContextMenu);
    window.removeEventListener('resize', closeContextMenu);
}

function onContextMenuPointerDown(event) {
    if (activeContextMenu && !activeContextMenu.contains(event.target)) {
        closeContextMenu();
    }
}

function onContextMenuKeyDown(event) {
    if (event.key === 'Escape') {
        event.preventDefault();
        closeContextMenu();
    }
}

function showContextMenu(x, y, items) {
    closeContextMenu();
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.setAttribute('role', 'menu');
    for (const item of items) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'context-menu-item';
        button.setAttribute('role', 'menuitem');
        button.textContent = item.label;
        button.addEventListener('click', () => {
            closeContextMenu();
            item.onSelect?.();
        });
        menu.append(button);
    }
    // 先隱藏量測尺寸，再夾到視窗範圍內定位。
    menu.style.visibility = 'hidden';
    document.body.append(menu);
    const rect = menu.getBoundingClientRect();
    const left = clamp(x, 8, Math.max(8, window.innerWidth - rect.width - 8));
    const top = clamp(y, 8, Math.max(8, window.innerHeight - rect.height - 8));
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.style.visibility = 'visible';
    activeContextMenu = menu;
    // 延後掛上關閉監聽，避免開啟當下的事件立刻把它關掉。
    setTimeout(() => {
        document.addEventListener('pointerdown', onContextMenuPointerDown, true);
        document.addEventListener('keydown', onContextMenuKeyDown, true);
        document.addEventListener('scroll', closeContextMenu, true);
        window.addEventListener('blur', closeContextMenu);
        window.addEventListener('resize', closeContextMenu);
    }, 0);
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
        if (idx == null || !state.document?.segments?.[idx]) {
            setStatus('請先播放某一段的音檔，才知道要設定哪一段的時間', 'error');
            return;
        }
        if (single) applyPlayerTimeSingle(idx, edge, now);
        else applyPlayerTime(idx, edge, now);
    };
    els.setStartButton?.addEventListener('click', () => applySetTime('start'));
    els.setEndButton?.addEventListener('click', () => applySetTime('end'));

    // 右鍵選單：只改這一段的起始／結束，不連動相鄰段落的共用邊界。
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
                seekBy(-5);
                break;
            case 'ArrowRight':
                if (!alt) return;
                event.preventDefault();
                seekBy(5);
                break;
        }
    }, true);

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

    mini.addEventListener('pointerdown', (event) => {
        if (event.button !== undefined && event.button !== 0) return;
        if (event.target.closest('button, input, select, textarea, label, a')) return;
        dragging = true;
        dragOffset = {
            x: event.clientX - mini.offsetLeft,
            y: event.clientY - mini.offsetTop,
        };
        mini.classList.add('dragging');
        handle.classList.add('dragging');
        try {
            mini.setPointerCapture(event.pointerId);
        } catch {
            // pointer capture may fail on some elements; drag still works via listeners
        }
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
        try {
            mini.releasePointerCapture(event.pointerId);
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
    mini.addEventListener('pointerup', stopDrag);
    mini.addEventListener('pointercancel', stopDrag);

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
