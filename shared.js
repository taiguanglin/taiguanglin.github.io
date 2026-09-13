/* TaiGuangLin — shared site chrome behaviours (nav, reveal, download modal) */
(function () {
    'use strict';

    /* ---------- Sticky nav ---------- */
    var navbar = document.getElementById('navbar');
    function onScroll() {
        if (!navbar) return;
        if (window.scrollY > 40) navbar.classList.add('scrolled');
        else navbar.classList.remove('scrolled');
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    /* ---------- Mobile menu ---------- */
    var hamburger = document.getElementById('hamburger');
    var navMenu = document.getElementById('nav-menu');
    if (hamburger && navMenu) {
        /* 頁面沒放遮罩時就補一個，抽屜開啟時才有背景壓暗 */
        var veil = document.getElementById('site-menu-veil');
        if (!veil) {
            veil = document.createElement('div');
            veil.id = 'site-menu-veil';
            veil.className = 'site-menu-veil';
            document.body.appendChild(veil);
        }
        function closeMenu() {
            navMenu.classList.remove('active');
            hamburger.classList.remove('active');
            hamburger.setAttribute('aria-expanded', 'false');
            if (veil) veil.classList.remove('active');
            document.body.style.overflow = '';
        }
        hamburger.addEventListener('click', function () {
            var open = navMenu.classList.toggle('active');
            hamburger.classList.toggle('active', open);
            hamburger.setAttribute('aria-expanded', open ? 'true' : 'false');
            if (veil) veil.classList.toggle('active', open);
            document.body.style.overflow = open ? 'hidden' : '';
        });
        if (veil) veil.addEventListener('click', closeMenu);
        window.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
        navMenu.querySelectorAll('.nav-link').forEach(function (link) {
            link.addEventListener('click', closeMenu);
        });
        document.addEventListener('click', function (e) {
            if (navMenu.contains(e.target) || hamburger.contains(e.target)) return;
            closeMenu();
        });
    }

    /* ---------- Dropdown (mobile tap) ---------- */
    document.querySelectorAll('.nav-dropdown-toggle').forEach(function (toggle) {
        toggle.addEventListener('click', function (e) {
            if (window.innerWidth > 768) return;
            e.preventDefault();
            var dd = toggle.closest('.nav-dropdown');
            if (dd) dd.classList.toggle('active');
        });
    });

    /* ---------- Nav active：跨頁高亮 + 首頁 scrollspy ---------- */
    /* 桌機：active 顯示粉色 pill + 圓點（見 style.css .nav-link.active）。
       首頁依捲動位置切換；其餘頁依 URL 判定（無 JS 時靠各頁硬編碼 active）。 */
    (function navActive() {
        var menu = document.getElementById('nav-menu');
        if (!menu) return;
        var menuLinks = menu.querySelectorAll('a.nav-link, a.nav-dropdown-item');
        if (!menuLinks.length) return;

        function hrefOf(a) { return (a.getAttribute('href') || '').trim(); }
        function isHashLink(a, id) {
            var h = hrefOf(a);
            return h === '#' + id || h.slice(-('#' + id).length) === '#' + id;
        }
        function isFileLink(a, file) {
            var h = hrefOf(a);
            if (h.indexOf('#') !== -1) return false;
            return h === file || h.slice(-('/' + file).length) === '/' + file;
        }
        function firstMatch(fn) {
            for (var i = 0; i < menuLinks.length; i++) {
                if (fn(menuLinks[i])) return menuLinks[i];
            }
            return null;
        }

        var homeLink = firstMatch(function (a) {
            return isFileLink(a, 'index.html') || isHashLink(a, 'home') ||
                hrefOf(a) === '/' || hrefOf(a) === './' || hrefOf(a) === '';
        }) || menu.querySelector('a.nav-link');
        var aboutLink = firstMatch(function (a) { return isHashLink(a, 'about'); });
        var startLink = firstMatch(function (a) { return isHashLink(a, 'start'); });
        var booksLink = firstMatch(function (a) { return isHashLink(a, 'books'); });
        var wendaLink = firstMatch(function (a) { return isFileLink(a, 'wenda2.html'); });
        var storiesLink = firstMatch(function (a) { return isFileLink(a, 'stories.html'); });
        var downloadsLink = firstMatch(function (a) { return isHashLink(a, 'downloads'); });
        var graphicToggle = menu.querySelector('.nav-dropdown-toggle');
        var graphicItems = menu.querySelectorAll('.nav-dropdown-item');

        var currentKey = null;
        function clearActive() {
            menu.querySelectorAll('.nav-link.active').forEach(function (l) {
                l.classList.remove('active');
                l.removeAttribute('aria-current');
            });
            menu.querySelectorAll('.nav-dropdown-item.active').forEach(function (l) {
                l.classList.remove('active');
                l.removeAttribute('aria-current');
            });
            menu.querySelectorAll('.nav-dropdown.is-current').forEach(function (d) {
                d.classList.remove('is-current');
            });
        }
        function applyLink(link, key, isPage) {
            if (currentKey === key) return;
            currentKey = key;
            clearActive();
            if (!link) return;
            link.classList.add('active');
            link.setAttribute('aria-current', isPage ? 'page' : 'true');
            var dd = link.closest ? link.closest('.nav-dropdown') : null;
            if (link.classList.contains('nav-dropdown-item')) {
                /* 子項高亮時，母選單「圖解」同步顯示 pill */
                if (dd) {
                    dd.classList.add('is-current');
                    var t = dd.querySelector('.nav-dropdown-toggle');
                    if (t) { t.classList.add('active'); t.setAttribute('aria-current', 'true'); }
                }
            }
            if (link.classList.contains('nav-dropdown-toggle') && dd) {
                dd.classList.add('is-current');
            }
        }

        /* ----- 跨頁：先依 URL 判定（wenda2 / stories / 圖解系） ----- */
        var path = window.location.pathname || '';
        var file = decodeURIComponent(path.split('/').pop() || '');
        var isIndex = file === '' || file === 'index.html' || file === 'index.htm' ||
            path === '/' || path.slice(-1) === '/';
        var inWenda = path.indexOf('/wenda2/') !== -1;
        var inStories = path.indexOf('/stories/') !== -1;

        if (file === 'wenda2.html' || inWenda) {
            applyLink(wendaLink, 'wenda-page', true);
            return;
        }
        if (file === 'stories.html' || inStories) {
            applyLink(storiesLink, 'stories-page', true);
            return;
        }
        if (file === 'infographic.html' || file === 'mindmap.html') {
            var wanted = file === 'infographic.html' ? 'infographic.html' : 'mindmap.html';
            var item = null;
            graphicItems.forEach(function (a) {
                if (hrefOf(a).slice(-wanted.length) === wanted) item = a;
            });
            applyLink(item || graphicToggle, 'graphic-page', true);
            return;
        }
        if (!isIndex) return; /* 其餘頁（ebook 等自帶導覽）不接管 */

        /* ----- 首頁 scrollspy：捲動到哪一段，哪個 nav 就亮起 ----- */
        var spyDefs = [
            { key: 'home', id: null, link: homeLink },
            { key: 'about', id: 'about', link: aboutLink },
            { key: 'start', id: 'start', link: startLink },
            { key: 'books', id: 'books', link: booksLink },
            { key: 'wenda', id: 'wenda', link: wendaLink },
            { key: 'stories', id: 'stories', link: storiesLink },
            { key: 'downloads', id: 'downloads', link: downloadsLink }
        ].filter(function (d) {
            if (!d.link) return false;
            if (d.key === 'home') return true;
            return !!document.getElementById(d.id);
        });
        if (spyDefs.length < 2) {
            /* 沒有足夠的錨點區塊時，至少依 hash 亮起 */
            var h0 = (window.location.hash || '').replace('#', '');
            var d0 = null;
            spyDefs.forEach(function (d) { if (d.id === h0) d0 = d; });
            applyLink(d0 ? d0.link : homeLink, d0 ? d0.key : 'home', false);
            return;
        }
        function findDef(key) {
            for (var i = 0; i < spyDefs.length; i++) {
                if (spyDefs[i].key === key) return spyDefs[i];
            }
            return null;
        }
        var NAV_OFFSET = 130; /* 固定膠囊 nav 高 + 緩衝 */
        function sectionTop(el) {
            return el.getBoundingClientRect().top + window.pageYOffset;
        }
        function pickCurrent() {
            if (window.scrollY < 80) return 'home';
            var pos = window.scrollY + NAV_OFFSET;
            var cur = 'home';
            spyDefs.forEach(function (d) {
                if (d.key === 'home') return;
                var el = document.getElementById(d.id);
                if (el && sectionTop(el) <= pos) cur = d.key;
            });
            var doc = document.documentElement;
            var nearBottom = window.innerHeight + window.scrollY >= doc.scrollHeight - 24;
            if (nearBottom) {
                var last = spyDefs[spyDefs.length - 1];
                var lastEl = last && last.id ? document.getElementById(last.id) : null;
                if (last && (last.key === 'home' || lastEl)) cur = last.key;
            }
            return cur;
        }
        function updateSpy() {
            var key = pickCurrent();
            var def = findDef(key);
            applyLink(def ? def.link : null, key, false);
        }
        var ticking = false;
        function onScrollSpy() {
            if (ticking) return;
            ticking = true;
            requestAnimationFrame(function () { ticking = false; updateSpy(); });
        }
        window.addEventListener('scroll', onScrollSpy, { passive: true });
        window.addEventListener('resize', onScrollSpy);
        window.addEventListener('hashchange', function () {
            var h = (window.location.hash || '').replace('#', '');
            var def = null;
            spyDefs.forEach(function (d) { if (d.id === h) def = d; });
            if (def) applyLink(def.link, def.key, false);
            else updateSpy();
        });
        /* 同頁錨點點擊時先即時亮起，捲動結束後 scroll 事件會再校準 */
        menu.querySelectorAll('a[href^="#"]').forEach(function (a) {
            a.addEventListener('click', function () {
                var id = (a.getAttribute('href') || '').slice(1);
                var def = null;
                spyDefs.forEach(function (d) { if (d.id === id) def = d; });
                if (def) applyLink(def.link, def.key, false);
            });
        });
        window.addEventListener('load', updateSpy);
        updateSpy();
        setTimeout(updateSpy, 350); /* 等圖片載入、版面穩定後再校準一次 */
    })();

    /* ---------- Smooth anchor scroll (same page) ---------- */
    document.querySelectorAll('a[href^="#"]:not([data-download-trigger])').forEach(function (a) {
        a.addEventListener('click', function (e) {
            var id = a.getAttribute('href');
            if (!id || id === '#') return;
            var target = document.querySelector(id);
            if (!target) return;
            e.preventDefault();
            var offset = 90;
            var top = target.getBoundingClientRect().top + window.pageYOffset - offset;
            window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
        });
    });

    /* ---------- Scroll reveal ---------- */
    var revealEls = document.querySelectorAll('.reveal');
    if (revealEls.length && 'IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (en) {
                if (en.isIntersecting) {
                    en.target.classList.add('in');
                    io.unobserve(en.target);
                }
            });
        }, { threshold: 0.12 });
        revealEls.forEach(function (el) { io.observe(el); });
    } else {
        document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('in'); });
    }

    /* ---------- Dharma quotes：隨機只顯示其中一則 ---------- */
    /* footer 法語區預設放兩則（.dharma-content / .qa-quote），太長故每次只留一則 */
    (function randomDharmaQuote() {
        function pickOne(container, quoteSel, citeSel) {
            var quotes = container.querySelectorAll(quoteSel);
            if (quotes.length < 2) return;
            var cites = container.querySelectorAll(citeSel);
            var keep = Math.floor(Math.random() * quotes.length);
            for (var i = 0; i < quotes.length; i++) {
                if (i === keep) continue;
                quotes[i].style.display = 'none';
                if (cites[i]) cites[i].style.display = 'none';
            }
        }
        document.querySelectorAll('.dharma-content').forEach(function (el) {
            pickOne(el, 'blockquote.dharma-quote', 'cite.dharma-author');
        });
        document.querySelectorAll('.qa-quote').forEach(function (el) {
            pickOne(el, 'blockquote.q', 'cite.cite');
        });
    })();

    /* ---------- Download modal (index) ---------- */
    var overlay = document.getElementById('downloadModal');
    if (overlay) {
        var closeBtn = document.getElementById('downloadModalClose');
        function openModal() {
            overlay.classList.add('active');
            overlay.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';
        }
        function closeModal() {
            overlay.classList.remove('active');
            overlay.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        }
        document.querySelectorAll('[data-download-trigger]').forEach(function (b) {
            b.addEventListener('click', function (e) { e.preventDefault(); openModal(); });
        });
        if (closeBtn) closeBtn.addEventListener('click', closeModal);
        overlay.addEventListener('click', function (e) { if (e.target === overlay) closeModal(); });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && overlay.classList.contains('active')) closeModal();
        });
    }
})();
