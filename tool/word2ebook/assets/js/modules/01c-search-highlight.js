// ============================================================
// 01c-search-highlight.js — 搜索结果高亮 & 上下文提取
// ============================================================

// 转义 HTML 特殊字符
function escapeHtml(str) {
  if (!str || typeof str !== 'string') return '';
  try {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  } catch (e) {
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#39;');
  }
}

// 转义正则表达式特殊字符
function escapeRegex(str) {
  if (!str || typeof str !== 'string') return '';
  const chars = {
    '\\': '\\\\', '.': '\\.', '*': '\\*', '+': '\\+', '?': '\\?',
    '^': '\\^', '$': '\\$', '{': '\\{', '}': '\\}', '(': '\\(',
    ')': '\\)', '|': '\\|', '[': '\\[', ']': '\\]', '/': '\\/'
  };
  let result = str;
  Object.keys(chars).forEach(c => { result = result.split(c).join(chars[c]); });
  return result;
}

// 智能获取最佳 context 用于高亮显示
function getBestContextForHighlight(result, query) {
  if (!query || !result.content) return result.context || result.content;

  const term = query.trim();
  const content = result.content;
  const lowerContent = content.toLowerCase();
  const lowerTerm = term.toLowerCase();

  if (!result.context) return content;
  if (result.context.toLowerCase().includes(lowerTerm)) return result.context;

  const exactIndex = lowerContent.indexOf(lowerTerm);
  if (exactIndex !== -1) return extractContextAroundPosition(content, exactIndex, 120);

  const keywords = extractKeywords(term);
  if (keywords.length > 1) return generateMultiKeywordContext(content, buildKeywordPositions(content, keywords), 150);

  return result.context || result.content;
}

function buildKeywordPositions(content, keywords) {
  const lowerContent = content.toLowerCase();
  const positions = [];
  keywords.forEach(kw => {
    const lw = kw.toLowerCase();
    let idx = lowerContent.indexOf(lw);
    while (idx !== -1) {
      positions.push({ keyword: kw, position: idx, length: kw.length });
      idx = lowerContent.indexOf(lw, idx + 1);
    }
  });
  return positions;
}

// 提取关键词（支持空格分割和中文简单分词）
function extractKeywords(searchTerm) {
  const cleaned = searchTerm.trim().replace(/\s+/g, ' ');
  const spaceWords = cleaned.split(' ').filter(w => w.length > 0);
  if (spaceWords.length > 1) return spaceWords;

  const keywords = [];
  const text = cleaned;
  if (text.length <= 4) {
    for (let i = 0; i < text.length; i += 2) {
      const w = text.substr(i, 2);
      if (w.length >= 2) keywords.push(w);
    }
  } else {
    for (let i = 0; i < text.length - 1; i++) {
      const w3 = text.substr(i, 3);
      const w2 = text.substr(i, 2);
      if (i < text.length - 2 && isLikelyWord(w3)) {
        keywords.push(w3); i += 2;
      } else if (isLikelyWord(w2)) {
        keywords.push(w2); i += 1;
      }
    }
  }
  return keywords.length > 0 ? keywords : [text];
}

function isLikelyWord(word) {
  return /^[\u4e00-\u9fff]+$/.test(word) && word.length >= 2;
}

// 生成包含多个关键词的 context 段落
function generateMultiKeywordContext(content, keywordPositions, maxLength) {
  if (!keywordPositions.length) return content.substring(0, maxLength);

  keywordPositions.sort((a, b) => a.position - b.position);
  const firstPos = keywordPositions[0].position;
  const last = keywordPositions[keywordPositions.length - 1];
  const totalSpan = last.position + last.length - firstPos;

  if (totalSpan <= maxLength * 0.8) {
    const start = Math.max(0, firstPos - Math.floor((maxLength - totalSpan) / 2));
    const end = Math.min(content.length, start + maxLength);
    let ctx = content.substring(start, end);
    if (start > 0) ctx = '...' + ctx;
    if (end < content.length) ctx += '...';
    return ctx;
  }

  const important = selectImportantPositions(keywordPositions, maxLength);
  return important.map(pos => {
    const partLen = Math.floor(maxLength / important.length);
    const s = Math.max(0, pos.position - Math.floor(partLen / 2));
    const e = Math.min(content.length, s + partLen);
    let part = content.substring(s, e);
    if (s > 0) part = '...' + part;
    if (e < content.length) part += '...';
    return part;
  }).join(' ');
}

function selectImportantPositions(positions, maxLength) {
  const selected = [];
  for (const pos of positions) {
    if (!selected.some(s => Math.abs(s.position - pos.position) < 20)) {
      selected.push(pos);
    }
    if (selected.length >= 3) break;
  }
  return selected.length > 0 ? selected : [positions[0]];
}

// 从指定位置提取上下文（智能裁剪到词边界）
function extractContextAroundPosition(text, position, maxLength) {
  const half = Math.floor(maxLength / 2);
  let start = Math.max(0, position - half);
  let end = Math.min(text.length, position + half);

  if (start > 0) {
    const before = text.substring(start - 10, start);
    const si = before.lastIndexOf(' ');
    const pi = Math.max(before.lastIndexOf('。'), before.lastIndexOf('，'), before.lastIndexOf('！'), before.lastIndexOf('？'));
    if (si !== -1 || pi !== -1) start = start - 10 + Math.max(si, pi) + 1;
  }
  if (end < text.length) {
    const after = text.substring(end, end + 10);
    const si = after.indexOf(' ');
    const pi = Math.min(
      after.indexOf('。') !== -1 ? after.indexOf('。') : Infinity,
      after.indexOf('，') !== -1 ? after.indexOf('，') : Infinity,
      after.indexOf('！') !== -1 ? after.indexOf('！') : Infinity,
      after.indexOf('？') !== -1 ? after.indexOf('？') : Infinity
    );
    if (si !== -1 || pi !== Infinity) end += Math.min(si !== -1 ? si : Infinity, pi);
  }

  let ctx = text.substring(start, end);
  if (start > 0) ctx = '...' + ctx;
  if (end < text.length) ctx += '...';
  return ctx;
}

// 智能高亮搜索词（支持精确 / 多关键词 / 模糊降级）
function highlightSearchTerm(text, searchTerm) {
  if (!text || !searchTerm || typeof text !== 'string' || typeof searchTerm !== 'string') return text;
  const term = searchTerm.trim();
  if (!term) return text;

  try {
    const exactRegex = new RegExp(`(${escapeRegex(term)})`, 'gi');
    const exact = text.replace(exactRegex, '<span class="search-result-highlight">$1</span>');
    if (exact !== text) return exact;

    const keywords = extractKeywords(term);
    if (keywords.length > 1) {
      const multi = highlightMultipleKeywords(text, keywords);
      if (multi !== text) return multi;
    }

    return highlightWithFuzzyMatching(text, term);
  } catch (e) {
    console.warn('智能高亮处理失败:', e);
    return highlightWithFuzzyMatching(text, term);
  }
}

function highlightMultipleKeywords(text, keywords) {
  let result = text;
  let hasMatch = false;
  const sorted = keywords.slice().sort((a, b) => b.length - a.length);
  sorted.forEach(kw => {
    const r = new RegExp(`(${escapeRegex(kw)})`, 'gi');
    const before = result;
    result = result.replace(r, '<span class="search-result-highlight">$1</span>');
    if (result !== before) hasMatch = true;
  });
  return hasMatch ? result : text;
}

function highlightWithFuzzyMatching(text, term) {
  try {
    const punct = '[\\s\\u3000-\\u303F\\uFF00-\\uFFEF\\u2000-\\u206F\\u0020-\\u002F\\u003A-\\u0040\\u005B-\\u0060\\u007B-\\u007E\\u2010-\\u2027\\u2030-\\u205F\\u3001-\\u3003\\u3008-\\u3011\\u3014-\\u301F\\uFE10-\\uFE19\\uFE30-\\uFE6F]';
    const flexPattern = term.split('').map(c => escapeRegex(c)).join(`${punct}*`);
    const flex = text.replace(new RegExp(`(${flexPattern})`, 'gi'), '<span class="search-result-highlight">$1</span>');
    if (flex !== text) return flex;

    const chars = term.split('');
    if (chars.length > 1) {
      const charPat = chars.map(c => escapeRegex(c)).join(`${punct}*`);
      const charResult = text.replace(new RegExp(`(${charPat})`, 'gi'), '<span class="search-result-highlight">$1</span>');
      if (charResult !== text) return charResult;
    }

    let result = text;
    chars.forEach(c => {
      if (c.trim()) result = result.replace(new RegExp(`(${escapeRegex(c)})`, 'gi'), '<span class="search-result-highlight">$1</span>');
    });
    return result;
  } catch (e) {
    console.warn('模糊高亮处理失败:', e);
    try {
      return text.replace(new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), '<span class="search-result-highlight">$&</span>');
    } catch (e2) {
      return text;
    }
  }
}
