/**
 * 本機草稿儲存（audio_map / audio_map2 / audio_map3 共用同一份模組）。
 *
 * 為什麼不用 localStorage 存草稿本體：一個月份的 JSON 就是 0.5–3.4 MB，草稿等於整份檔案；
 * 而 localStorage 的額度約 5 MB／origin，**由三個審核 UI 共用**，加上其他 key，寫滿之後
 * `setItem` 會丟 `QuotaExceededError`。存檔流程在送出前會先 `flushDraft()`，於是那個例外
 * 直接把「儲存到 GitHub」整段中止——畫面上只看得到 console 紅字，資料本身沒問題。
 *
 * 現在草稿文字放 IndexedDB（額度是可用磁碟的一小部分），localStorage 只留每個草稿一筆
 * 小紀錄（沿用 `audioMapEditor:draft:<path>` 這個 key，但不含文字）。好處：
 * - `listDraftPaths()`／徽章／「有草稿」對話框維持同步，冷啟動就能用。
 * - key 帶各自的 repo 路徑（`audio_map2/…`、`audio_map3/…`），三個 UI 共用一個 store 也不會互相覆蓋。
 * - 舊版寫在 localStorage 的草稿（含文字）會在 `initDraftStore()` 匯入 IndexedDB 並縮小成
 *   metadata 紀錄——這同時就是把塞爆的額度還回去的動作。
 *
 * ⚠ 文字寫入是**非同步**的（IDB 沒有同步 API），離頁時的 `flushDraft()` 只能盡力啟動寫入；
 * 防遺失靠的是「離頁前 800ms debounce／2500ms 硬上限就已經寫過」＋
 * `visibilitychange:hidden`（手機切 app、下拉重整）這個提前量很大的同步點。
 */

/** 三個審核 UI 共用同一個 database：key 帶路徑，所以不會互相覆蓋。 */
const DB_NAME = 'audioMapEditor';
const DB_VERSION = 1;
const STORE = 'drafts';
/** localStorage 索引用的前綴（與舊版 key 相同，方便沿用既有的掃描邏輯）。 */
const LOCAL_PREFIX = 'audioMapEditor:draft:';

let dbPromise = null;

function localKey(path) {
    return `${LOCAL_PREFIX}${path}`;
}

function isQuotaError(error) {
    return error?.name === 'QuotaExceededError'
        || error?.name === 'NS_ERROR_DOM_QUOTA_REACHED'
        || error?.code === 22
        || error?.code === 1014;
}

function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
        if (!('indexedDB' in window)) {
            reject(new Error('這個瀏覽器沒有 IndexedDB'));
            return;
        }
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(STORE)) {
                db.createObjectStore(STORE, { keyPath: 'key' });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error || new Error('開啟 IndexedDB 失敗'));
        request.onblocked = () => reject(new Error('IndexedDB 被其他分頁佔住'));
    }).catch((error) => {
        // 失敗不要把 promise 釘死，之後還能再試（例如使用者關掉其他分頁）。
        dbPromise = null;
        throw error;
    });
    return dbPromise;
}

/** 跑一次 store 操作；transaction 結束（`oncomplete`）才算寫入落地。 */
function withStore(mode, run) {
    return openDb().then((db) => new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, mode);
        let result;
        tx.oncomplete = () => resolve(result);
        tx.onerror = () => reject(tx.error || new Error('IndexedDB 交易失敗'));
        tx.onabort = () => reject(tx.error || new Error('IndexedDB 交易中止'));
        const request = run(tx.objectStore(STORE));
        if (request) request.onsuccess = () => { result = request.result; };
    }));
}

/**
 * 開好資料庫並把舊版 localStorage 草稿搬進去。頁面啟動時 `await` 一次；
 * IndexedDB 不可用時不中斷頁面，草稿退回 localStorage（見 `setDraft` 的退路）。
 */
export function initDraftStore() {
    return openDb()
        .then(migrateLocalDrafts)
        .then(() => undefined)
        .catch((error) => {
            console.warn('[draft] IndexedDB 不可用，草稿改用 localStorage（額度有限）：', error);
        });
}

/** 本地有草稿的 repo 路徑（同步：只讀 localStorage 索引，不碰草稿本體）。 */
export function listDraftPaths() {
    const paths = new Set();
    for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (key?.startsWith(LOCAL_PREFIX)) {
            paths.add(key.slice(LOCAL_PREFIX.length));
        }
    }
    return paths;
}

/** 同步判斷某個路徑有沒有草稿（給重算 dirty 這種不能 await 的地方用）。 */
export function hasDraft(path) {
    return readLocalRecord(path) != null;
}

export async function getDraft(path) {
    const record = readLocalRecord(path);
    if (!record) return null;
    if (record.store !== 'idb') {
        // 尚未遷移的舊格式：文字就在 localStorage 紀錄裡。
        return typeof record.text === 'string' ? record : null;
    }
    let stored = null;
    try {
        stored = await withStore('readonly', (store) => store.get(localKey(path)));
    } catch (error) {
        console.warn('[draft] 讀取 IndexedDB 失敗：', error);
        return null;
    }
    if (!stored || typeof stored.text !== 'string') {
        // 索引有、文本沒有（寫入途中被中斷）：沒有東西可以救回，清掉這筆索引。
        removeLocalRecord(path);
        return null;
    }
    return { path, text: stored.text, sha: record.sha || '', savedAt: record.savedAt };
}

/**
 * 存草稿。**回傳的 promise 永不 reject**：草稿只是保險，寫不進去不該擋住上傳，
 * 呼叫端（`flushDraft`）會把失敗訊息顯示出來。
 */
export async function setDraft(path, text, sha) {
    const savedAt = new Date().toISOString();
    try {
        await withStore('readwrite', (store) => store.put({
            key: localKey(path), path, text, sha, savedAt,
        }));
        writeLocalRecord(path, { sha, savedAt, bytes: text.length, store: 'idb' });
        return;
    } catch (error) {
        console.warn('[draft] IndexedDB 寫入失敗，改用 localStorage：', error);
    }
    try {
        writeLocalDraftInline(path, text, sha, savedAt);
    } catch (error) {
        // 最後手段：把最舊的 inline 草稿先搬進 IndexedDB 再重試。搬不掉的（IDB 也壞了）
        // 只能丟棄——它們是本 session 沒在編輯的月份，但寧可丟舊的也不要丟現在這份。
        for (const victim of inlineDraftsOldestFirst(path)) {
            if (!await moveDraftToDb(victim.path, victim.record)) continue;
            removeLocalRecord(victim.path);
            try {
                writeLocalDraftInline(path, text, sha, savedAt);
                console.warn(`[draft] localStorage 額度不足，已把 ${victim.path} 的草稿搬進 IndexedDB。`);
                return;
            } catch (retryError) {
                if (!isQuotaError(retryError)) throw retryError;
            }
        }
        console.error('[draft] 草稿寫入失敗（未儲存變更仍可直接上傳，但離開頁面會遺失）：', error);
    }
}

export async function clearDraft(path) {
    removeLocalRecord(path);
    try {
        await withStore('readwrite', (store) => store.delete(localKey(path)));
    } catch (error) {
        console.warn('[draft] 從 IndexedDB 刪除草稿失敗：', error);
    }
}

/** 清掉所有草稿（IndexedDB ＋ localStorage 索引），設定頁／debug 用。 */
export async function clearAllDrafts() {
    for (const path of listDraftPaths()) {
        await clearDraft(path);
    }
}

function writeLocalRecord(path, fields) {
    try {
        localStorage.setItem(localKey(path), JSON.stringify({ path, ...fields }));
    } catch (error) {
        if (!isQuotaError(error)) throw error;
        // 索引紀錄只有幾百 bytes，寫不進去代表 localStorage 已經被別的東西塞滿。
        console.warn('[draft] localStorage 索引寫入失敗：', error);
    }
}

function writeLocalDraftInline(path, text, sha, savedAt) {
    localStorage.setItem(localKey(path), JSON.stringify({
        path, text, sha, savedAt, bytes: text.length, store: 'local',
    }));
}

function readLocalRecord(path) {
    try {
        const raw = localStorage.getItem(localKey(path));
        if (!raw) return null;
        return JSON.parse(raw);
    } catch {
        return null;
    }
}

function removeLocalRecord(path) {
    try {
        localStorage.removeItem(localKey(path));
    } catch {
        // 移除不會因為額度失敗。
    }
}

function readAllLocalRecords() {
    const records = [];
    for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (!key?.startsWith(LOCAL_PREFIX)) continue;
        const record = readLocalRecord(key.slice(LOCAL_PREFIX.length));
        if (record) records.push(record);
    }
    return records;
}

/** 還帶著文字的 localStorage 草稿，由舊到新（`savedAt`）。 */
function inlineDraftsOldestFirst(currentPath) {
    return readAllLocalRecords()
        .filter((record) => record.store !== 'idb' && typeof record.text === 'string')
        .filter((record) => record.path !== currentPath)
        .sort((a, b) => String(a.savedAt || '').localeCompare(String(b.savedAt || '')))
        .map((record) => ({ path: record.path, record }));
}

/** 把一份 localStorage 草稿搬進 IndexedDB；成功回 true，IDB 不可用回 false。 */
async function moveDraftToDb(path, record) {
    try {
        await withStore('readwrite', (store) => store.put({
            key: localKey(path),
            path,
            text: record.text,
            sha: record.sha || '',
            savedAt: record.savedAt || new Date().toISOString(),
        }));
        return true;
    } catch (error) {
        console.warn(`[draft] ${path} 的草稿無法搬進 IndexedDB：`, error);
        return false;
    }
}

/**
 * 舊格式（文字在 localStorage）→ IndexedDB，並把 localStorage 紀錄縮小成 metadata。
 * 這一步同時把 localStorage 額度還回去，解除 QuotaExceededError 的死結。
 */
async function migrateLocalDrafts() {
    for (const record of readAllLocalRecords()) {
        if (record.store === 'idb') continue;
        if (typeof record.text !== 'string') {
            removeLocalRecord(record.path);
            continue;
        }
        if (!await moveDraftToDb(record.path, record)) continue;
        writeLocalRecord(record.path, {
            sha: record.sha || '',
            savedAt: record.savedAt || new Date().toISOString(),
            bytes: record.text.length,
            store: 'idb',
        });
    }
}
