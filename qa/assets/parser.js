const SEGMENT_HEADING_RE = /^###\s+(\d+)\.\s*(.*)$/;
const MARKER_LINE_RE = /^(###\s+\d+\..*|時間：\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-\s*\d{2}:\d{2}:\d{2}[.,]\d{3})\r?\n?$/;
const TIME_RANGE_RE = /(?:開場時間|時間)：\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})/g;

export function parseDocument(text, path = '') {
    const headingMatches = [...text.matchAll(/^###\s+(\d+)\.\s*(.*)$/gm)];

    if (headingMatches.length === 0) {
        return {
            path,
            title: firstNonEmptyLine(text) || fileTitleFromPath(path),
            mode: 'fallback',
            header: '',
            segments: [
                createFallbackSegment(text),
            ],
        };
    }

    const header = text.slice(0, headingMatches[0].index);
    const segments = headingMatches.map((match, index) => {
        const start = match.index;
        const end = index + 1 < headingMatches.length ? headingMatches[index + 1].index : text.length;
        return parseSegment(text.slice(start, end), index);
    });

    return {
        path,
        title: firstNonEmptyLine(header) || fileTitleFromPath(path),
        mode: 'segments',
        header,
        headerRanges: parseRanges(header),
        segments,
    };
}

export function serializeDocument(document) {
    if (document.mode === 'fallback') {
        return document.segments[0]?.parts[0]?.text || '';
    }

    return [
        document.header || '',
        ...document.segments.map(serializeSegment),
    ].join('');
}

export function cloneDocument(document) {
    return JSON.parse(JSON.stringify(document));
}

export function parseRanges(text) {
    const ranges = [];
    for (const match of text.matchAll(TIME_RANGE_RE)) {
        ranges.push({
            label: `${match[1]} - ${match[2]}`,
            startLabel: match[1],
            endLabel: match[2],
            start: timecodeToSeconds(match[1]),
            end: timecodeToSeconds(match[2]),
        });
    }
    return ranges;
}

export function timecodeToSeconds(value) {
    const normalized = value.replace(',', '.');
    const [hours, minutes, seconds] = normalized.split(':');
    return Number(hours) * 3600 + Number(minutes) * 60 + Number(seconds);
}

export function secondsToTimecode(value) {
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    const seconds = value % 60;
    const wholeSeconds = Math.floor(seconds);
    const millis = Math.round((seconds - wholeSeconds) * 1000);
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(wholeSeconds).padStart(2, '0')}.${String(millis).padStart(3, '0')}`;
}

export function fileTitleFromPath(path) {
    return path.split('/').pop()?.replace(/\.txt$/i, '') || '未命名檔案';
}

function parseSegment(raw, index) {
    const lines = raw.match(/[^\n]*\n|[^\n]+$/g) || [''];
    const firstLine = lines[0]?.replace(/\r?\n$/, '') || '';
    const heading = firstLine.match(SEGMENT_HEADING_RE);
    const parts = [];
    let chunk = '';

    for (const line of lines) {
        if (MARKER_LINE_RE.test(line)) {
            if (chunk) {
                parts.push({ type: 'chunk', text: chunk });
                chunk = '';
            }
            parts.push({ type: 'marker', text: line });
        } else {
            chunk += line;
        }
    }

    if (chunk || parts.length === 0) {
        parts.push({ type: 'chunk', text: chunk });
    }

    return {
        id: `segment-${index + 1}`,
        index,
        number: heading?.[1] || String(index + 1),
        title: heading?.[2] || `段落 ${index + 1}`,
        raw,
        ranges: parseRanges(raw),
        parts,
    };
}

function serializeSegment(segment) {
    return segment.parts.map((part) => part.text).join('');
}

function createFallbackSegment(text) {
    return {
        id: 'fallback',
        index: 0,
        number: '',
        title: '全文編輯模式',
        raw: text,
        ranges: parseRanges(text),
        parts: [
            { type: 'chunk', text },
        ],
    };
}

function firstNonEmptyLine(text) {
    return text.split(/\r?\n/).find((line) => line.trim())?.trim() || '';
}
