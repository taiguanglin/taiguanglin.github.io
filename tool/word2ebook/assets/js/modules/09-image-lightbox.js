// ============================================================
// 09-image-lightbox.js — 章節內嵌圖 lightbox（原圖／縮放／同頁切換）
//
// 點擊 img[src*="assets/images/"] 開啟；同頁前後張；適窗／縮放／拖曳。
// 獨立 IIFE，避免與共享 DOMContentLoaded 作用域碰撞。
// ============================================================

(function () {
  const IMG_SEL = 'img[src*="assets/images/"]';
  const MIN_SCALE = 0.25;
  const MAX_SCALE = 8;
  const ZOOM_STEP = 1.25;

  let root = null;
  let stage = null;
  let imgEl = null;
  let counterEl = null;
  let btnPrev = null;
  let btnNext = null;
  let btnJump = null;
  let btnClose = null;
  let btnZoomIn = null;
  let btnZoomOut = null;
  let btnReset = null;

  let gallery = [];
  let index = 0;
  let open = false;
  let scale = 1;
  let fitScale = 1;
  let tx = 0;
  let ty = 0;
  let naturalW = 0;
  let naturalH = 0;

  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragOriginTx = 0;
  let dragOriginTy = 0;
  let moved = false;

  let pinchActive = false;
  let pinchStartDist = 0;
  let pinchStartScale = 1;
  let lastTapTime = 0;

  function t(sim, trad) {
    if (typeof getText === 'function') return getText(sim, trad);
    return trad;
  }

  function collectGallery() {
    return Array.from(document.querySelectorAll(IMG_SEL));
  }

  function ensureDom() {
    if (root) return;

    root = document.createElement('div');
    root.className = 'img-lightbox';
    root.setAttribute('role', 'dialog');
    root.setAttribute('aria-modal', 'true');
    root.setAttribute('aria-label', t('图片查看', '圖片檢視'));

    const toolbar = document.createElement('div');
    toolbar.className = 'img-lightbox__toolbar';

    btnPrev = makeBtn('prev', '‹', t('上一张', '上一張'));
    btnNext = makeBtn('next', '›', t('下一张', '下一張'));
    btnJump = makeBtn('jump', t('跳到问答', '跳到問答'), t('关闭并滚动到该图片所在问答', '關閉並捲動到該圖片所在問答'));
    btnZoomOut = makeBtn('zoom-out', '−', t('缩小', '縮小'));
    btnZoomIn = makeBtn('zoom-in', '+', t('放大', '放大'));
    btnReset = makeBtn('reset', '1:1', t('实际大小', '實際大小'));
    btnClose = makeBtn('close', '×', t('关闭', '關閉'));

    counterEl = document.createElement('span');
    counterEl.className = 'img-lightbox__counter';
    counterEl.setAttribute('aria-live', 'polite');

    toolbar.append(
      btnPrev, counterEl, btnNext, btnJump,
      btnZoomOut, btnZoomIn, btnReset, btnClose,
    );

    stage = document.createElement('div');
    stage.className = 'img-lightbox__stage';

    imgEl = document.createElement('img');
    imgEl.className = 'img-lightbox__img';
    imgEl.alt = '';
    stage.appendChild(imgEl);

    root.append(toolbar, stage);
    document.body.appendChild(root);

    btnPrev.addEventListener('click', (e) => { e.stopPropagation(); go(-1); });
    btnNext.addEventListener('click', (e) => { e.stopPropagation(); go(1); });
    btnJump.addEventListener('click', (e) => { e.stopPropagation(); jumpToSource(); });
    btnZoomIn.addEventListener('click', (e) => { e.stopPropagation(); zoomBy(ZOOM_STEP); });
    btnZoomOut.addEventListener('click', (e) => { e.stopPropagation(); zoomBy(1 / ZOOM_STEP); });
    btnReset.addEventListener('click', (e) => { e.stopPropagation(); toggleFitOrOne(); });
    btnClose.addEventListener('click', (e) => { e.stopPropagation(); closeLightbox(); });

    root.addEventListener('click', (e) => {
      if (moved) {
        moved = false;
        return;
      }
      if (e.target === root || e.target === stage) closeLightbox();
    });

    stage.addEventListener('pointerdown', onPointerDown);
    stage.addEventListener('pointermove', onPointerMove);
    stage.addEventListener('pointerup', onPointerUp);
    stage.addEventListener('pointercancel', onPointerUp);
    stage.addEventListener('wheel', onWheel, { passive: false });
    stage.addEventListener('dblclick', onDblClick);
    stage.addEventListener('touchstart', onTouchStart, { passive: false });
    stage.addEventListener('touchmove', onTouchMove, { passive: false });
    stage.addEventListener('touchend', onTouchEnd);
    stage.addEventListener('touchcancel', onTouchEnd);
  }

  function makeBtn(action, label, title) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'img-lightbox__btn';
    b.dataset.action = action;
    b.textContent = label;
    b.title = title;
    b.setAttribute('aria-label', title);
    return b;
  }

  function applyTransform() {
    imgEl.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
  }

  function clampPan() {
    const sw = stage.clientWidth;
    const sh = stage.clientHeight;
    const dw = naturalW * scale;
    const dh = naturalH * scale;
    const maxX = Math.max(0, (dw - sw) / 2);
    const maxY = Math.max(0, (dh - sh) / 2);
    tx = Math.min(maxX, Math.max(-maxX, tx));
    ty = Math.min(maxY, Math.max(-maxY, ty));
  }

  function computeFitScale() {
    const sw = Math.max(1, stage.clientWidth - 16);
    const sh = Math.max(1, stage.clientHeight - 16);
    if (!naturalW || !naturalH) return 1;
    return Math.min(1, sw / naturalW, sh / naturalH);
  }

  function setScale(next, pivotX, pivotY) {
    const prev = scale;
    scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, next));
    if (pivotX != null && pivotY != null && prev > 0) {
      const rect = stage.getBoundingClientRect();
      const cx = pivotX - rect.left - rect.width / 2;
      const cy = pivotY - rect.top - rect.height / 2;
      const ratio = scale / prev;
      tx = cx - (cx - tx) * ratio;
      ty = cy - (cy - ty) * ratio;
    }
    clampPan();
    applyTransform();
    updateResetLabel();
  }

  function zoomBy(factor, pivotX, pivotY) {
    setScale(scale * factor, pivotX, pivotY);
  }

  function updateResetLabel() {
    const nearFit = Math.abs(scale - fitScale) < 0.02;
    if (nearFit) {
      btnReset.textContent = '1:1';
      btnReset.title = t('实际大小', '實際大小');
      btnReset.setAttribute('aria-label', btnReset.title);
    } else {
      btnReset.textContent = t('适窗', '適窗');
      btnReset.title = t('适合窗口', '適合視窗');
      btnReset.setAttribute('aria-label', btnReset.title);
    }
  }

  function toggleFitOrOne() {
    const nearFit = Math.abs(scale - fitScale) < 0.02;
    if (nearFit) {
      setScale(1);
      tx = 0;
      ty = 0;
      clampPan();
      applyTransform();
    } else {
      fitToViewport();
    }
    updateResetLabel();
  }

  function fitToViewport() {
    fitScale = computeFitScale();
    scale = fitScale;
    tx = 0;
    ty = 0;
    applyTransform();
    updateResetLabel();
  }

  function updateNav() {
    const n = gallery.length;
    counterEl.textContent = n ? `${index + 1} / ${n}` : '0 / 0';
    btnPrev.disabled = index <= 0;
    btnNext.disabled = index >= n - 1;
  }

  function showAt(i) {
    if (i < 0 || i >= gallery.length) return;
    index = i;
    const src = gallery[i].currentSrc || gallery[i].src;
    imgEl.onload = () => {
      naturalW = imgEl.naturalWidth;
      naturalH = imgEl.naturalHeight;
      fitToViewport();
    };
    if (imgEl.src !== src) {
      imgEl.src = src;
    } else if (imgEl.complete && imgEl.naturalWidth) {
      naturalW = imgEl.naturalWidth;
      naturalH = imgEl.naturalHeight;
      fitToViewport();
    }
    updateNav();
  }

  function go(delta) {
    const next = index + delta;
    if (next < 0 || next >= gallery.length) return;
    showAt(next);
  }

  /** Closest Q/A card for the current gallery image; fall back to the img itself. */
  function sourceAnchor() {
    const img = gallery[index];
    if (!img || !document.body.contains(img)) return null;
    return img.closest('.question, .answer') || img;
  }

  function jumpToSource() {
    const target = sourceAnchor();
    closeLightbox();
    if (!target) return;
    // Wait a frame so body overflow is restored before scrolling.
    requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (target.id) {
        try {
          history.replaceState(null, '', `#${target.id}`);
        } catch (_) { /* ignore */ }
      }
    });
  }

  function openLightbox(fromImg) {
    ensureDom();
    gallery = collectGallery();
    const i = gallery.indexOf(fromImg);
    if (i < 0) return;
    open = true;
    root.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    showAt(i);
  }

  function closeLightbox() {
    if (!open) return;
    open = false;
    root.classList.remove('is-open');
    document.body.style.overflow = '';
    dragging = false;
    pinchActive = false;
    stage.classList.remove('is-dragging');
  }

  function onPointerDown(e) {
    if (e.pointerType === 'touch') return;
    if (e.button != null && e.button !== 0) return;
    dragging = true;
    moved = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragOriginTx = tx;
    dragOriginTy = ty;
    stage.classList.add('is-dragging');
    try { stage.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
  }

  function onPointerMove(e) {
    if (!dragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
    tx = dragOriginTx + dx;
    ty = dragOriginTy + dy;
    clampPan();
    applyTransform();
  }

  function onPointerUp(e) {
    if (!dragging) return;
    dragging = false;
    stage.classList.remove('is-dragging');
    try { stage.releasePointerCapture(e.pointerId); } catch (_) { /* ignore */ }
  }

  function onWheel(e) {
    if (!open) return;
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) {
      const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      zoomBy(factor, e.clientX, e.clientY);
    } else {
      // plain wheel also zooms (common for image viewers)
      const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      zoomBy(factor, e.clientX, e.clientY);
    }
  }

  function onDblClick(e) {
    e.preventDefault();
    toggleFitOrOne();
  }

  function touchDistance(touches) {
    const a = touches[0];
    const b = touches[1];
    const dx = a.clientX - b.clientX;
    const dy = a.clientY - b.clientY;
    return Math.hypot(dx, dy);
  }

  function onTouchStart(e) {
    if (e.touches.length === 2) {
      e.preventDefault();
      pinchActive = true;
      dragging = false;
      pinchStartDist = touchDistance(e.touches);
      pinchStartScale = scale;
      return;
    }
    if (e.touches.length === 1) {
      const now = Date.now();
      if (now - lastTapTime < 300) {
        e.preventDefault();
        toggleFitOrOne();
        lastTapTime = 0;
        return;
      }
      lastTapTime = now;
      dragging = true;
      moved = false;
      dragStartX = e.touches[0].clientX;
      dragStartY = e.touches[0].clientY;
      dragOriginTx = tx;
      dragOriginTy = ty;
      stage.classList.add('is-dragging');
    }
  }

  function onTouchMove(e) {
    if (pinchActive && e.touches.length === 2) {
      e.preventDefault();
      const dist = touchDistance(e.touches);
      if (pinchStartDist > 0) {
        const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
        setScale(pinchStartScale * (dist / pinchStartDist), midX, midY);
      }
      return;
    }
    if (dragging && e.touches.length === 1) {
      e.preventDefault();
      const dx = e.touches[0].clientX - dragStartX;
      const dy = e.touches[0].clientY - dragStartY;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
      tx = dragOriginTx + dx;
      ty = dragOriginTy + dy;
      clampPan();
      applyTransform();
    }
  }

  function onTouchEnd(e) {
    if (e.touches.length < 2) pinchActive = false;
    if (e.touches.length === 0) {
      dragging = false;
      stage.classList.remove('is-dragging');
    } else if (e.touches.length === 1) {
      dragging = true;
      dragStartX = e.touches[0].clientX;
      dragStartY = e.touches[0].clientY;
      dragOriginTx = tx;
      dragOriginTy = ty;
    }
  }

  function onKeyDown(e) {
    if (!open) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      closeLightbox();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      go(-1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      go(1);
    } else if (e.key === '+' || e.key === '=') {
      e.preventDefault();
      zoomBy(ZOOM_STEP);
    } else if (e.key === '-' || e.key === '_') {
      e.preventDefault();
      zoomBy(1 / ZOOM_STEP);
    } else if (e.key === '0') {
      e.preventDefault();
      fitToViewport();
    }
  }

  function onDocClick(e) {
    const img = e.target.closest(IMG_SEL);
    if (!img || !document.body.contains(img)) return;
    if (root && root.contains(img)) return;
    e.preventDefault();
    openLightbox(img);
  }

  function onResize() {
    if (!open) return;
    fitScale = computeFitScale();
    if (scale <= fitScale * 1.02) {
      fitToViewport();
    } else {
      clampPan();
      applyTransform();
      updateResetLabel();
    }
  }

  document.addEventListener('click', onDocClick);
  document.addEventListener('keydown', onKeyDown);
  window.addEventListener('resize', onResize);

  W2E.openImageLightbox = openLightbox;
  W2E.closeImageLightbox = closeLightbox;
})();
