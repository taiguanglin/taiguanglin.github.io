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
  return {
    path: file.path,
    name: file.name,
    sha: file.sha,
    text: decodeBase64(file.content || ''),
  };
}

export async function putFile(path, text, sha, message) {
  return request(`/repos/${GITHUB_CONFIG.owner}/${GITHUB_CONFIG.repo}/contents/${encodePath(path)}`, {
    method: 'PUT',
    body: JSON.stringify({
      message,
      content: encodeBase64(text),
      sha,
      branch: GITHUB_CONFIG.branch,
    }),
    requireAuth: true,
  });
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
    throw new GitHubApiError(payload?.message || `GitHub API failed (${response.status})`, response, payload);
  }
  return payload;
}

function encodePath(path) {
  return path.split('/').map(encodeURIComponent).join('/');
}

function decodeBase64(value) {
  const binary = atob(value.replace(/\s/g, ''));
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder('utf-8').decode(bytes);
}

function encodeBase64(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = '';
  bytes.forEach((b) => { binary += String.fromCharCode(b); });
  return btoa(binary);
}
