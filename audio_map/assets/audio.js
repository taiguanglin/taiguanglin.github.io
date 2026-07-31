const AUDIO_BASE = '../audio/';

export function createPlayer({ audio, titleEl, rangeEl, stopCheckbox, playerRoot, toggleBtn }) {
  let activeRange = null;
  let activeFile = '';

  audio.addEventListener('timeupdate', () => {
    if (!activeRange?.stopAtEnd) return;
    if (Number.isFinite(activeRange.end) && audio.currentTime >= activeRange.end) {
      audio.pause();
      audio.currentTime = activeRange.end;
    }
  });

  toggleBtn?.addEventListener('click', () => {
    if (audio.paused) audio.play();
    else audio.pause();
  });

  playerRoot?.querySelectorAll('[data-seek]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const delta = Number(btn.dataset.seek) || 0;
      let t = audio.currentTime + delta;
      if (activeRange) {
        t = Math.min(Math.max(t, activeRange.start), activeRange.end);
      }
      audio.currentTime = t;
    });
  });

  return {
    async playRange(fileName, start, end, label = '') {
      const src = new URL(`${AUDIO_BASE}${encodeURIComponent(fileName)}`, document.baseURI).href;
      if (activeFile !== src) {
        activeFile = src;
        audio.src = src;
      }
      activeRange = {
        start,
        end,
        stopAtEnd: stopCheckbox?.checked ?? true,
      };
      titleEl.textContent = fileName;
      rangeEl.textContent = label || `${start.toFixed(1)} – ${end.toFixed(1)}`;
      playerRoot?.classList.remove('hidden');
      audio.currentTime = start;
      await audio.play();
    },
    stop() {
      audio.pause();
      playerRoot?.classList.add('hidden');
    },
  };
}
