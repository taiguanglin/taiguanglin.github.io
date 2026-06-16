// 音檔放在本網站根目錄的 audio/ 資料夾，這個頁面位於 qa/，所以用相對路徑往上一層。
// 同網域播放，不需跨 domain。
const AUDIO_BASE = '../audio/';

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
            const src = new URL(`${AUDIO_BASE}${encodeURIComponent(baseName)}`, document.baseURI).href;
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
            titleEl.title = label || baseName;
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
