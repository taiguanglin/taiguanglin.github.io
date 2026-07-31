const PAT_KEY = 'audio_map_github_pat';

export function getPat() {
  return localStorage.getItem(PAT_KEY) || '';
}

export function setPat(value) {
  if (value) localStorage.setItem(PAT_KEY, value);
  else localStorage.removeItem(PAT_KEY);
}
