const PREFIX = 'qaEditor:';
const PAT_KEY = `${PREFIX}pat`;
const PREFS_KEY = `${PREFIX}prefs`;
const DRAFT_PREFIX = `${PREFIX}draft:`;

const DEFAULT_PREFS = {
    playbackRate: 1,
    stopAtRangeEnd: true,
    sidebarWidth: 320,
    sidebarCollapsed: false,
};

export function getPat() {
    return localStorage.getItem(PAT_KEY) || '';
}

export function setPat(token) {
    const cleanToken = token.trim();
    if (cleanToken) {
        localStorage.setItem(PAT_KEY, cleanToken);
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
    localStorage.setItem(PREFS_KEY, JSON.stringify({ ...getPrefs(), ...nextPrefs }));
}

export function getDraft(path) {
    try {
        return JSON.parse(localStorage.getItem(draftKey(path)) || 'null');
    } catch {
        return null;
    }
}

export function setDraft(path, text, sha) {
    localStorage.setItem(draftKey(path), JSON.stringify({
        path,
        text,
        sha,
        savedAt: new Date().toISOString(),
    }));
}

export function clearDraft(path) {
    localStorage.removeItem(draftKey(path));
}

export function listDraftPaths() {
    const paths = new Set();
    for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (key?.startsWith(DRAFT_PREFIX)) {
            paths.add(key.slice(DRAFT_PREFIX.length));
        }
    }
    return paths;
}

function draftKey(path) {
    return `${DRAFT_PREFIX}${path}`;
}
