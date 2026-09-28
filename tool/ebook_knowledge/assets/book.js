/* 複習電子書前端行為：自測展開/收合 + 全文檢索 + 錨點高亮。
   無外部相依（不用 jieba wasm），檢索索引由建置器一併產生。 */
(function () {
  'use strict';

  // ---- 自測題：點一下才顯示參考答案 ------------------------------------
  document.querySelectorAll('.check').forEach(function (box) {
    var answer = box.querySelector('.check__a');
    var btn = box.querySelector('.check__btn');
    if (!answer || !btn) return;
    answer.hidden = true;
    btn.addEventListener('click', function () {
      var showing = !answer.hidden;
      answer.hidden = showing;
      btn.textContent = showing ? '看參考答案' : '收起答案';
    });
  });

  // ---- 全文檢索 ---------------------------------------------------------
  var form = document.getElementById('search-form');
  var input = document.getElementById('search-input');
  var status = document.getElementById('search-status');
  var list = document.getElementById('search-results');
  if (!form || !input || !status || !list) return;

  var index = null;
  var loading = false;

  function load(cb) {
    if (index) return cb(index);
    if (loading) return;
    loading = true;
    status.textContent = '正在載入檢索索引…';
    fetch(form.dataset.index, { cache: 'force-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
        return r.json();
      })
      .then(function (data) { index = data; loading = false; cb(index); })
      .catch(function (err) {
        loading = false;
        status.textContent = '檢索索引載入失敗（' + err.message + '）。頁面本身仍可正常閱讀。';
      });
  }

  function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  function excerpt(text, terms) {
    var lo = text.toLowerCase();
    var at = -1;
    for (var i = 0; i < terms.length; i++) {
      var p = lo.indexOf(terms[i]);
      if (p >= 0 && (at < 0 || p < at)) at = p;
    }
    if (at < 0) return text.slice(0, 120) + (text.length > 120 ? '…' : '');
    var start = Math.max(0, at - 40);
    var end = Math.min(text.length, at + 90);
    var frag = (start > 0 ? '…' : '') + text.slice(start, end) + (end < text.length ? '…' : '');
    terms.forEach(function (t) {
      if (!t) return;
      frag = frag.replace(new RegExp('(' + escapeRe(t) + ')', 'gi'), '<mark>$1</mark>');
    });
    return frag;
  }

  function run() {
    var raw = input.value.trim().toLowerCase();
    list.innerHTML = '';
    if (!raw) { status.textContent = ''; return; }
    var terms = raw.split(/\s+/).filter(Boolean);
    load(function (data) {
      var hits = [];
      for (var i = 0; i < data.docs.length; i++) {
        var d = data.docs[i];
        var hay = d.t || '';
        var all = true;
        for (var j = 0; j < terms.length; j++) {
          if (hay.indexOf(terms[j]) < 0) { all = false; break; }
        }
        if (all) hits.push(d);
      }
      status.textContent = hits.length
        ? '找到 ' + hits.length + ' 筆符合「' + raw + '」的段落。'
        : '沒有找到符合「' + raw + '」的段落。';
      hits.slice(0, 60).forEach(function (d) {
        var li = document.createElement('li');
        li.className = 'search__hit';
        var a = document.createElement('a');
        a.href = d.u;
        a.textContent = d.h;
        var p = document.createElement('p');
        p.innerHTML = excerpt(d.t, terms);
        li.appendChild(a);
        li.appendChild(p);
        list.appendChild(li);
      });
      if (hits.length > 60) {
        var li = document.createElement('li');
        li.className = 'search__status';
        li.textContent = '…只顯示前 60 筆，請縮小關鍵字範圍。';
        list.appendChild(li);
      }
    });
  }

  form.addEventListener('submit', function (e) { e.preventDefault(); run(); });
  var t = null;
  input.addEventListener('input', function () {
    clearTimeout(t);
    t = setTimeout(run, 220);
  });

  // 從別頁連過來時帶 ?q=
  var q = new URLSearchParams(location.search).get('q');
  if (q) { input.value = q; run(); }

  // ---- 錨點到達時短暫高亮 ---------------------------------------------
  if (location.hash) {
    var target = document.querySelector(location.hash);
    if (target) {
      target.style.transition = 'background-color .4s';
      target.style.backgroundColor = 'var(--k-primary-soft)';
      setTimeout(function () { target.style.backgroundColor = ''; }, 1400);
    }
  }
})();
