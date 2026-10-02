import {
    clearDraft,
    getDraft,
    hasDraft,
    initDraftStore,
    listDraftPaths,
    setDraft,
} from './draft_store.js';

/**
 * 草稿（`get/set/clearDraft`）本體在 IndexedDB，不在 localStorage：一個月份 JSON 就是
 * 1–3 MB，localStorage 的額度是三個審核 UI 共用的，寫滿會讓存檔在 `flushDraft()` 直接
 * 掛掉。`hasDraft()`／`listDraftPaths()` 仍是同步的（讀 localStorage 索引）。
 * 這裡原樣轉出，editor.js 只需要 import storage.js。
 */
export { clearDraft, getDraft, hasDraft, initDraftStore, listDraftPaths, setDraft };

const PREFIX = 'audioMapEditor:';
const PAT_KEY = `${PREFIX}pat`;
const PREFS_KEY = `${PREFIX}prefs`;
const PENDING_SAVE_KEY = `${PREFIX}pendingSave`;

const DEFAULT_PREFS = {
    playbackRate: 1,
    stopAtRangeEnd: true,
    sidebarWidth: 320,
    sidebarCollapsed: false,
    miniPlayerHidden: false,
    miniPlayerExpanded: false,
    /** Document panel max width in px; 0 = fill available width. */
    contentMaxWidth: 1100,
    /** 'center' | 'left' — widescreen only. */
    contentAlign: 'center',
    /** Extra workspace padding-right (px) so content clears the floating player. */
    contentRightGutter: 0,
    /** When false, play keeps the player hidden if the user already hid it. */
    autoShowMiniPlayer: true,
    lastMonth: null,
    lastSessionId: null,
};

export function getPat() {
    return localStorage.getItem(PAT_KEY) || '';
}

export function setPat(token) {
    const cleanToken = token.trim();
    if (cleanToken) {
        safeSetItem(PAT_KEY, cleanToken);
    } else {
        localStorage.removeItem(PAT_KEY);
    }
}

export function clearPat() {
    localStorage.removeItem(PAT_KEY);
}

export function getPrefs() {
    try {
        return {
            ...DEFAULT_PREFS,
            ...JSON.parse(localStorage.getItem(PREFS_KEY) || '{}'),
        };
    } catch {
        return { ...DEFAULT_PREFS };
    }
}

export function setPrefs(nextPrefs) {
    safeSetItem(PREFS_KEY, JSON.stringify({ ...getPrefs(), ...nextPrefs }));
}

/**
 * Marker for "a GitHub save was started and never confirmed". Cleared on
 * success. A leftover marker is how the next page load knows the previous
 * session ended mid-save, so the draft it finds can be explained instead of
 * looking like an unexplained local copy.
 */
export function getPendingSave() {
    try {
        return JSON.parse(localStorage.getItem(PENDING_SAVE_KEY) || 'null');
    } catch {
        return null;
    }
}

export function setPendingSave(path) {
    safeSetItem(PENDING_SAVE_KEY, JSON.stringify({
        path,
        startedAt: new Date().toISOString(),
    }));
}

export function clearPendingSave() {
    localStorage.removeItem(PENDING_SAVE_KEY);
}

let quotaWarned = false;

/**
 * localStorage 寫入不讓例外外洩。
 *
 * 這些 key 都只有幾百 bytes，寫不進去代表**整個 origin 的額度**被別的東西塞滿（過去就是
 * localStorage 裡的舊草稿）。讓 `QuotaExceededError` 從 `setPendingSave()` 丟出去，會在
 * 第一個 `await` 之前就中止整個上傳——就是「按儲存卻沒反應」的原因。額度在啟動時由
 * `initDraftStore()` 搬走舊草稿回收，這裡只是最後一道不炸掉整條流程的保險。
 */
function safeSetItem(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (error) {
        if (error?.name !== 'QuotaExceededError' && error?.name !== 'NS_ERROR_DOM_QUOTA_REACHED') {
            throw error;
        }
        if (!quotaWarned) {
            quotaWarned = true;
            console.warn('[storage] localStorage 額度已滿，這次偏好設定／存檔標記沒有寫入：', error);
        }
    }
}
