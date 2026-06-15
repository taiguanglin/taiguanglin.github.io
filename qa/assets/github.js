import { getPat } from './storage.js';

const API_ROOT = 'https://api.github.com';
export const GITHUB_CONFIG = {
    owner: 'taiguanglin',
    repo: 'taiguanglin.github.io',
    branch: 'main',
};

export class GitHubApiError extends Error {
    constructor(message, response, payload = null) {
        super(message);
        this.name = 'GitHubApiError';
        this.status = response?.status || 0;
        this.payload = payload;
    }
}

export async function listQaFiles({ showReports = false } = {}) {
    const items = await request(`/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/qa?ref=${GITHUB_CONFIG.branch}`);
    return items
        .filter((item) => item.type === 'file')
        .filter((item) => item.name.endsWith('.txt'))
        .filter((item) => showReports || !item.name.startsWith('_'))
        .map((item) => ({
            name: item.name,
            path: item.path,
            sha: item.sha,
            size: item.size,
            downloadUrl: item.download_url,
            isReport: item.name.startsWith('_'),
        }))
        .sort(compareByDateDesc);
}

// 從檔名（如「2026年1月10日…」）取出年月日，組成可比較的數值（年*10000+月*100+日）。
// 字串比較會把「10」排在「9」之前（逐字比 1 < 9），導致月份與日期沒有完全從新到舊，
// 改以數值比較才能正確由近到遠排序；非日期檔名（如統計報告）排到最後。
function dateKeyFromName(name) {
    const match = name.match(/^(\d{4})年(\d{1,2})月(\d{1,2})日/);
    if (!match) return null;
    return Number(match[1]) * 10000 + Number(match[2]) * 100 + Number(match[3]);
}

function compareByDateDesc(a, b) {
    const keyA = dateKeyFromName(a.name);
    const keyB = dateKeyFromName(b.name);
    if (keyA != null && keyB != null) {
        if (keyA !== keyB) return keyB - keyA;
    } else if (keyA == null && keyB != null) {
        return 1;
    } else if (keyA != null && keyB == null) {
        return -1;
    }
    // 同一天（或皆非日期檔名）時，沿用原本的檔名排序當作穩定的次序。
    return b.name.localeCompare(a.name, 'zh-Hant-u-nu-latn');
}

export async function getFile(path) {
    const file = await request(`/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${encodePath(path)}?ref=${GITHUB_CONFIG.branch}`);
    return {
        path: file.path,
        name: file.name,
        sha: file.sha,
        text: decodeBase64(file.content || ''),
        htmlUrl: file.html_url,
    };
}

export async function putFile(path, text, sha, message, { force = false } = {}) {
    let targetSha = sha;
    if (force) {
        targetSha = (await getFile(path)).sha;
    }

    return request(`/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${encodePath(path)}`, {
        method: 'PUT',
        body: JSON.stringify({
            message,
            content: encodeBase64(text),
            sha: targetSha,
            branch: GITHUB_CONFIG.branch,
        }),
        requireAuth: true,
    });
}

export async function testToken() {
    return request('/user', { requireAuth: true });
}

export function isConflict(error) {
    return error instanceof GitHubApiError && (error.status === 409 || error.status === 422);
}

async function request(endpoint, options = {}) {
    const token = getPat();
    if (options.requireAuth && !token) {
        throw new GitHubApiError('尚未設定 GitHub PAT', { status: 401 });
    }

    const response = await fetch(`${API_ROOT}${endpoint}`, {
        method: options.method || 'GET',
        headers: {
            Accept: 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        },
        body: options.body,
    });

    let payload = null;
    try {
        payload = await response.json();
    } catch {
        payload = null;
    }

    if (!response.ok) {
        const message = payload?.message || `GitHub API request failed (${response.status})`;
        throw new GitHubApiError(message, response, payload);
    }

    return payload;
}

function encodePath(path) {
    return path.split('/').map(encodeURIComponent).join('/');
}

function decodeBase64(value) {
    const binary = atob(value.replace(/\s/g, ''));
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    return new TextDecoder('utf-8').decode(bytes);
}

function encodeBase64(value) {
    const bytes = new TextEncoder().encode(value);
    let binary = '';
    bytes.forEach((byte) => {
        binary += String.fromCharCode(byte);
    });
    return btoa(binary);
}
