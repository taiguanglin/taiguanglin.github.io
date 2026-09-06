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
        var veil = document.getElementById('site-menu-veil');
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
