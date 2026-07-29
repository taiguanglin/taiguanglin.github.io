/* 實修故事閱讀頁互動：閱讀進度、字級、深色模式、圖片燈箱 */
(function () {
    'use strict';

    var STORE = 'tai-story-reading';
    var article = document.querySelector('.story-article');
    if (!article) return;

    /* 導覽列高度會隨字級與視窗寬度變化，量到多少就給 CSS 多少 */
    var navbar = document.getElementById('navbar');
    function measureNav() {
        if (!navbar) return;
        var h = navbar.offsetHeight;
        document.documentElement.style.setProperty('--story-navh', h + 'px');
    }
    measureNav();
    window.addEventListener('resize', measureNav);
    window.addEventListener('load', measureNav);

    var prefs = {};
    try {
        prefs = JSON.parse(localStorage.getItem(STORE)) || {};
    } catch (e) {
        prefs = {};
    }

    function save() {
        try {
            localStorage.setItem(STORE, JSON.stringify(prefs));
        } catch (e) { /* 私密瀏覽等情況忽略 */ }
    }

    /* ---- 字級 ----
       沒調過就交給樣式表決定（手機比桌機小一級），調過才寫成行內樣式。 */
    var SIZES = [16, 18, 20, 23, 26];
    var sizeIndex = SIZES.indexOf(prefs.fontSize);

    function nearestIndex() {
        var now = parseFloat(getComputedStyle(article).fontSize) || 18;
        var best = 0;
        for (var i = 1; i < SIZES.length; i++) {
            if (Math.abs(SIZES[i] - now) < Math.abs(SIZES[best] - now)) best = i;
        }
        return best;
    }

    function step(delta) {
        if (sizeIndex < 0) sizeIndex = nearestIndex();
        sizeIndex = Math.min(SIZES.length - 1, Math.max(0, sizeIndex + delta));
        article.style.fontSize = SIZES[sizeIndex] + 'px';
        prefs.fontSize = SIZES[sizeIndex];
        save();
    }

    if (sizeIndex >= 0) article.style.fontSize = SIZES[sizeIndex] + 'px';

    /* ---- 深色模式 ---- */
    function applyDark() {
        document.body.classList.toggle('story-dark', !!prefs.dark);
        var btn = document.getElementById('story-dark-btn');
        if (btn) {
            btn.setAttribute('aria-pressed', prefs.dark ? 'true' : 'false');
            btn.innerHTML = prefs.dark
                ? '<i class="fas fa-sun"></i> 淺色'
                : '<i class="fas fa-moon"></i> 深色';
        }
    }

    applyDark();

    var smaller = document.getElementById('story-font-smaller');
    var bigger = document.getElementById('story-font-bigger');
    if (smaller) smaller.addEventListener('click', function () { step(-1); });
    if (bigger) bigger.addEventListener('click', function () { step(1); });
    var darkBtn = document.getElementById('story-dark-btn');
    if (darkBtn) darkBtn.addEventListener('click', function () {
        prefs.dark = !prefs.dark;
        save();
        applyDark();
    });

    /* ---- 目錄跳轉 ----
       站台的 script.js 會攔下所有 #錨點 連結，用固定 80px 的位移捲動；
       閱讀頁上方多了一條工具列，所以在捕獲階段先接手，改用自己的位移。 */
    var toc = document.getElementById('story-toc');
    var toolbar = document.querySelector('.story-toolbar');
    if (toc) {
        toc.addEventListener('click', function (ev) {
            var link = ev.target.closest('a[href^="#"]');
            if (!link) return;
            var target = document.getElementById(link.getAttribute('href').slice(1));
            if (!target) return;
            ev.preventDefault();
            ev.stopPropagation();
            var offset = (navbar ? navbar.offsetHeight : 80) +
                (toolbar ? toolbar.offsetHeight : 0) + 16;
            window.scrollTo({
                top: target.getBoundingClientRect().top + window.scrollY - offset,
                behavior: 'smooth'
            });
            if (history.replaceState) history.replaceState(null, '', link.getAttribute('href'));
        }, true);
    }

    /* ---- 閱讀進度 ---- */
    var bar = document.querySelector('.reading-progress');
    var ticking = false;

    function onScroll() {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(function () {
            var top = article.offsetTop;
            var span = article.offsetHeight - window.innerHeight * 0.6;
            var done = Math.min(1, Math.max(0, (window.scrollY - top + 120) / Math.max(span, 1)));
            if (bar) bar.style.width = (done * 100).toFixed(2) + '%';
            ticking = false;
        });
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    /* ---- 圖片燈箱 ---- */
    var box = document.querySelector('.story-lightbox');
    if (box) {
        var boxImg = box.querySelector('img');
        article.addEventListener('click', function (ev) {
            var img = ev.target.closest('figure img');
            if (!img) return;
            boxImg.src = img.currentSrc || img.src;
            boxImg.alt = img.alt;
            box.classList.add('open');
            document.body.style.overflow = 'hidden';
        });
        function closeBox() {
            box.classList.remove('open');
            document.body.style.overflow = '';
            boxImg.removeAttribute('src');
        }
        box.addEventListener('click', closeBox);
        document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape' && box.classList.contains('open')) closeBox();
        });
    }
})();
