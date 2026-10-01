import { getPat } from './storage.js';

const API_ROOT = 'https://api.github.com';
const RAW_ROOT = 'https://raw.githubusercontent.com';
/** Raw goes through a CDN that can stall outright on blocked networks. */
const RAW_TIMEOUT_MS = 8000;
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

export async function getFile(path) {
    const file = await request(
        `/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${encodePath(path)}?ref=${GITHUB_CONFIG.branch}`,
    );
    // Files >1 MB come back with empty `content` — refetch raw text instead.
    let text;
    if (file.content) {
        text = decodeBase64(file.content);
    } else {
        text = await getRawFile(path);
    }
    return {
        path: file.path,
        name: file.name,
        sha: file.sha,
        text,
        htmlUrl: file.html_url,
    };
}

async function getRawFile(path) {
    const token = getPat();
    const headers = { Accept: 'application/vnd.github.raw' };
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(
        `${API_ROOT}/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${encodePath(path)}?ref=${GITHUB_CONFIG.branch}`,
        { headers },
    );
    if (!response.ok) throw new Error(`HTTP ${response.status} ${path}`);
    return response.text();
}

/**
 * Whether the page runs on a real web host (GitHub Pages) instead of a local
 * preview server. A local preview must read the working tree, so it never
 * substitutes raw GitHub content.
 */
export function isRemoteHost() {
    const { protocol, hostname } = window.location;
    if (protocol !== 'http:' && protocol !== 'https:') return false;
    return !/^(localhost|127(\.\d+){3}|0\.0\.0\.0|\[::1\])$/i.test(hostname);
}

/** Canonical raw URL for a repo path on the configured branch. */
export function rawFileUrl(path) {
    return `${RAW_ROOT}/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/${GITHUB_CONFIG.branch}/${encodePath(path)}`;
}

let rawUnreachable = false;

/**
 * Read a map JSON, preferring the just-committed file over the deployed copy.
 *
 * A GitHub Pages deploy only publishes `main` once its build finishes, so a
 * freshly pushed JSON stays invisible for minutes — or forever when the build
 * fails. Reading `raw.githubusercontent.com` shows the committed file within
 * seconds. Falls back to the deployed copy when raw is unreachable, and stays
 * on it for the rest of the session so a blocked network costs one timeout
 * rather than one per month switch.
 *
 * @param {string} repoPath repo-relative path, e.g. `audio_map2/2024-02.json`
 * @param {string} deployedUrl the same file as served by the current origin
 * @returns {Promise<{text: string, source: 'raw'|'deployed', url: string}>}
 */
export async function loadMapJson(repoPath, deployedUrl) {
    if (isRemoteHost() && !rawUnreachable) {
        const url = rawFileUrl(repoPath);
        try {
            return { text: await fetchText(url, repoPath, RAW_TIMEOUT_MS), source: 'raw', url };
        } catch (error) {
            rawUnreachable = true;
            console.warn('[github] raw 讀取失敗，改用已部署檔案：', error);
        }
    }
    const url = new URL(deployedUrl, window.location.href).href;
    return { text: await fetchText(url, url), source: 'deployed', url };
}

async function fetchText(url, label, timeoutMs = 0) {
    const controller = timeoutMs ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
    try {
        // `no-store` so a commit shows up on the next reload instead of waiting
        // out the raw CDN's max-age.
        const response = await fetch(url, { cache: 'no-store', signal: controller?.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}（${label}）`);
        return await response.text();
    } catch (error) {
        if (error?.name === 'AbortError') throw new Error(`讀取逾時（${timeoutMs / 1000}s，${label}）`);
        throw error;
    } finally {
        if (timer) clearTimeout(timer);
    }
}

/**
 * When the file was last changed on the configured branch — the one signal that
 * tells you whether the data on screen is the file you just pushed. Neither raw
 * (it sends no `Last-Modified`) nor the contents API carries a timestamp, so
 * this is the only source. Returns null when unavailable (offline, rate
 * limited); callers must treat that as "unknown", not as "stale".
 */
export async function getLastCommit(path) {
    const commits = await request(
        `/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/commits`
        + `?path=${encodePath(path)}&sha=${GITHUB_CONFIG.branch}&per_page=1`,
    );
    const commit = Array.isArray(commits) ? commits[0] : null;
    const date = commit?.commit?.committer?.date;
    if (!date) return null;
    return { date, sha: commit.sha || '', message: commit.commit?.message || '' };
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
