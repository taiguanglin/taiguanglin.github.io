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
