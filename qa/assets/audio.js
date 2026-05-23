const LECTURES_BASE = 'https://taiguanglin.github.io/lectures/QnA/';

export function createAudioController({ audio, titleEl, rangeEl, rateSelect, stopCheckbox }) {
    let activeRange = null;
    let activeFile = '';

    const supportsOpus = Boolean(audio.canPlayType('audio/ogg; codecs=opus') || audio.canPlayType('audio/opus'));

    rateSelect.addEventListener('change', () => {
        audio.playbackRate = Number(rateSelect.value);
    });

    stopCheckbox.addEventListener('change', () => {
        if (activeRange) {
            activeRange.stopAtEnd = stopCheckbox.checked;
        }
    });

    audio.addEventListener('timeupdate', () => {
        if (!activeRange?.stopAtEnd) return;
        if (Number.isFinite(activeRange.end) && audio.currentTime >= activeRange.end) {
            audio.pause();
            audio.currentTime = activeRange.end;
        }
    });

    return {
        supportsOpus,
        setPlaybackRate(value) {
            const rate = Number(value) || 1;
            rateSelect.value = String(rate);
            audio.playbackRate = rate;
        },
        setStopAtRangeEnd(value) {
            stopCheckbox.checked = Boolean(value);
            if (activeRange) {
                activeRange.stopAtEnd = stopCheckbox.checked;
            }
        },
        async playRange(filePath, range, label = '') {
            const baseName = filePath.split('/').pop().replace(/\.txt$/i, '.opus');
            const src = `${LECTURES_BASE}${encodeURIComponent(baseName)}`;
            if (activeFile !== src) {
                activeFile = src;
                audio.src = src;
            }

            activeRange = {
                start: range.start,
                end: range.end,
                stopAtEnd: stopCheckbox.checked,
            };
            titleEl.textContent = label || baseName;
            rangeEl.textContent = range.label ? ` ${range.label}` : '';
            audio.playbackRate = Number(rateSelect.value) || 1;
            audio.currentTime = range.start;
            await audio.play();
        },
        toggle() {
            if (audio.paused) {
                return audio.play();
            }
            audio.pause();
            return Promise.resolve();
        },
    };
}
