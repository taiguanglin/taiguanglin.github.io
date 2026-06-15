import { parseRanges, secondsToTimecode } from './parser.js';

const HEADING_TEST = /^###\s+\d+\./;
const HEADING_TITLE_RE = /^###\s+\d+\.\s*(.*?)\s*\r?\n?$/;
const TIME_TEST = /^(時間|開場時間)：/;

function clonePart(part) {
    return { type: part.type, text: part.text };
}

function isHeadingMarker(part) {
    return part.type === 'marker' && HEADING_TEST.test(part.text);
}

function isTimeMarker(part) {
    return part.type === 'marker' && TIME_TEST.test(part.text);
}

function isStructuralMarker(part) {
    return isHeadingMarker(part) || isTimeMarker(part);
}

function blankMeta() {
    return { lastPlayed: '', lastEdited: '', hasLastPlayedLine: true, hasLastEditedLine: true };
}

function timeMarker(segment) {
    return segment.parts.find(isTimeMarker) || null;
}

export function getSegmentRange(segment) {
    const marker = timeMarker(segment);
    if (marker) {
        const range = parseRanges(marker.text)[0];
        if (range) return range;
    }
    for (const part of segment.parts) {
        if (part.type !== 'marker') continue;
        const range = parseRanges(part.text)[0];
        if (range) return range;
    }
    return null;
}

function setTimeRange(part, start, end) {
    part.text = `時間：${secondsToTimecode(start)} - ${secondsToTimecode(end)}\n`;
}

// Trim trailing whitespace and guarantee one blank line so the next segment's
// heading always starts on its own line after serialization.
function ensureBlockEnd(text) {
    const trimmed = text.replace(/\s+$/, '');
    return trimmed ? `${trimmed}\n\n` : '';
}

function stripLeadingBlank(text) {
    return text.replace(/^[ \t\r\n]+/, '');
}

function makeSegment(parts) {
    return {
        id: `segment-${Math.random().toString(36).slice(2, 9)}`,
        index: 0,
        number: '',
        title: '',
        raw: parts.map((part) => part.text).join(''),
        ranges: parts.filter((part) => part.type === 'marker').flatMap((part) => parseRanges(part.text)),
        parts,
        meta: blankMeta(),
    };
}

// Rewrite every heading to a sequential 1-based number and refresh derived
// fields. Mutates and returns the same document object.
export function renumber(document) {
    document.segments.forEach((segment, index) => {
        segment.index = index;
        const heading = segment.parts.find(isHeadingMarker);
        if (heading) {
            const match = heading.text.match(HEADING_TITLE_RE);
            const title = match ? match[1] : (segment.title || '');
            heading.text = `### ${index + 1}. ${title}\n`;
            segment.number = String(index + 1);
            segment.title = title;
        } else {
            segment.number = String(index + 1);
        }
        segment.raw = segment.parts.map((part) => part.text).join('');
        segment.ranges = segment.parts
            .filter((part) => part.type === 'marker')
            .flatMap((part) => parseRanges(part.text));
    });
    return document;
}

// Split segment[segmentIndex] at `offset` inside its chunk part[partIndex].
// Text before the caret stays in the first segment; text after becomes a new
// segment. The split boundary in time uses the segment's *current* end time
// (the value shown in the 時間 input box): the usual workflow is to press the
// floating player's「設結束」at the split moment first, so the first segment
// keeps [start, end] from the input box and the new second segment starts at
// that end (its own end is left equal, to be refined while listening on).
// Returns the same document object.
export function splitSegment(document, segmentIndex, partIndex, offset) {
    const segment = document.segments[segmentIndex];
    if (!segment) return document;
    const part = segment.parts[partIndex];
    if (!part || part.type !== 'chunk') return document;

    const range = getSegmentRange(segment);
    const boundary = range ? range.end : null;
    const before = part.text.slice(0, offset);
    const after = part.text.slice(offset);

    const firstParts = segment.parts.slice(0, partIndex).map(clonePart);
    firstParts.push({ type: 'chunk', text: ensureBlockEnd(before) });
    if (range) {
        const firstTime = firstParts.find(isTimeMarker);
        if (firstTime) setTimeRange(firstTime, range.start, boundary);
    }

    const tailParts = segment.parts
        .slice(partIndex + 1)
        .filter((p) => !isStructuralMarker(p))
        .map(clonePart);
    const secondHeading = { type: 'marker', text: '### 0. （待填提問）\n' };
    const secondTime = {
        type: 'marker',
        text: range
            ? `時間：${secondsToTimecode(boundary)} - ${secondsToTimecode(boundary)}\n`
            : '時間：00:00:00.000 - 00:00:00.000\n',
    };
    // Keep the split-off segment valid for format A: its body must start with a
    // single「Taiguanglin：」answer marker.
    let afterText = stripLeadingBlank(after);
    if (!/^\s*Taiguanglin[:：]/.test(afterText)) {
        afterText = `Taiguanglin：\n${afterText}`;
    }
    const secondBody = { type: 'chunk', text: ensureBlockEnd(afterText) };
    const secondParts = [secondHeading, secondTime, secondBody, ...tailParts];

    document.segments.splice(segmentIndex, 1, makeSegment(firstParts), makeSegment(secondParts));
    return renumber(document);
}

// Merge segment[segmentIndex] with the following segment. The first segment's
// heading is kept; the time range spans both; the second segment's heading and
// time markers are dropped and its body is appended. Returns the document.
export function mergeWithNext(document, segmentIndex) {
    const first = document.segments[segmentIndex];
    const second = document.segments[segmentIndex + 1];
    if (!first || !second) return document;

    const firstParts = first.parts.map(clonePart);
    const firstRange = getSegmentRange(first);
    const secondRange = getSegmentRange(second);
    if (firstRange && secondRange) {
        const firstTime = firstParts.find(isTimeMarker);
        if (firstTime) setTimeRange(firstTime, firstRange.start, secondRange.end);
    }

    // Format A: the question lives in the heading. Fold the second segment's
    // question into the kept heading so it is not lost on merge.
    const firstHeading = firstParts.find(isHeadingMarker);
    const secondHeadingPart = second.parts.find(isHeadingMarker);
    if (firstHeading && secondHeadingPart) {
        const q1 = (firstHeading.text.match(HEADING_TITLE_RE)?.[1] || '').trim();
        const q2 = (secondHeadingPart.text.match(HEADING_TITLE_RE)?.[1] || '').trim();
        const isPlaceholder = (q) => !q || /^（(新段落|待填提問)）$/.test(q);
        let combined = q1;
        if (!isPlaceholder(q2) && q2 !== q1) combined = q1 ? `${q1}${q2}` : q2;
        firstHeading.text = `### 0. ${combined}\n`;
    }

    // The two answers must share ONE text box, so merge all body text into a
    // single chunk and keep only the top「Taiguanglin：」(drop the second one).
    const structural = firstParts.filter(isStructuralMarker);
    const firstBody = firstParts.filter((part) => part.type === 'chunk').map((part) => part.text).join('');
    const secondBody = second.parts.filter((part) => !isStructuralMarker(part)).map((part) => part.text).join('');
    const secondNoMarker = secondBody.replace(/^\s*Taiguanglin[:：][ \t]*\r?\n?/, '');
    const mergedBody = ensureBlockEnd(firstBody) + stripLeadingBlank(secondNoMarker);
    document.segments.splice(segmentIndex, 2, makeSegment([...structural, { type: 'chunk', text: mergedBody }]));
    return renumber(document);
}

// Delete a whole segment and renumber the rest so the headings stay sequential.
// Returns the same document object.
export function removeSegment(document, segmentIndex) {
    if (segmentIndex < 0 || segmentIndex >= document.segments.length) return document;
    document.segments.splice(segmentIndex, 1);
    return renumber(document);
}

// Locate the start of the 2nd 提問 line in a segment body, used as a fallback
// split point when no caret position is available.
export function findSecondQuestion(segment) {
    for (let i = 0; i < segment.parts.length; i += 1) {
        const part = segment.parts[i];
        if (part.type !== 'chunk') continue;
        const re = /(^|\n)([ \t]*)(提問|追加問題)[:：]/g;
        let match;
        let count = 0;
        while ((match = re.exec(part.text))) {
            count += 1;
            if (count === 2) {
                const lead = match[1] ? match[1].length : 0;
                return { partIndex: i, offset: match.index + lead };
            }
        }
    }
    return null;
}
