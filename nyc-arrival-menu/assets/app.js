/* New York's Arrival Menu — theme, reading progress, era tracking, image slots. */
(function () {
  'use strict';

  var root = document.documentElement;
  var KEY = 'nyc-arrival-menu:theme';

  /* ---------------------------------------------------------- theme */

  var toggle = document.querySelector('[data-theme-toggle]');
  var toggleLabel = document.querySelector('[data-theme-label]');

  function readStored() {
    try { return localStorage.getItem(KEY); } catch (err) { return null; }
  }
  function writeStored(value) {
    try { localStorage.setItem(KEY, value); } catch (err) { /* private mode, blocked storage */ }
  }
  function currentTheme() {
    var stamped = root.getAttribute('data-theme');
    if (stamped === 'dark' || stamped === 'light') return stamped;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function syncToggle() {
    if (!toggle) return;
    var dark = currentTheme() === 'dark';
    toggle.setAttribute('aria-pressed', dark ? 'true' : 'false');
    if (toggleLabel) toggleLabel.textContent = dark ? 'Light' : 'Dark';
  }

  var stored = readStored();
  if (stored === 'dark' || stored === 'light') root.setAttribute('data-theme', stored);
  syncToggle();

  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = currentTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      writeStored(next);
      syncToggle();
    });
  }

  /* ------------------------------------------------- image slots
     Frames ship empty so a missing photo shows the slot spec rather
     than a broken-image icon. Drop the file into images/ and it
     appears on the next load — no markup change needed. */

  Array.prototype.forEach.call(document.querySelectorAll('.plate__frame[data-src]'), function (frame) {
    var src = frame.getAttribute('data-src');
    if (!src) return;
    var probe = new Image();
    probe.addEventListener('load', function () {
      var img = document.createElement('img');
      img.src = src;
      img.alt = frame.getAttribute('data-alt') || '';
      img.decoding = 'async';
      img.loading = 'lazy';
      frame.appendChild(img);
      frame.classList.add('is-filled');
    });
    probe.src = src;
  });

  /* ---------------------------------------------- reading progress */

  var bar = document.querySelector('[data-progress]');
  var pending = false;

  function paintProgress() {
    if (pending) return;
    pending = true;
    window.requestAnimationFrame(function () {
      pending = false;
      if (!bar) return;
      var scrollable = document.documentElement.scrollHeight - window.innerHeight;
      var ratio = scrollable > 0 ? window.scrollY / scrollable : 0;
      bar.style.transform = 'scaleX(' + Math.min(1, Math.max(0, ratio)) + ')';
    });
  }

  window.addEventListener('scroll', paintProgress, { passive: true });
  window.addEventListener('resize', paintProgress);
  paintProgress();

  /* -------------------------------------------------- era tracking */

  var eras = Array.prototype.slice.call(document.querySelectorAll('.era[id]'));
  var links = Array.prototype.slice.call(document.querySelectorAll('.rail a[href^="#"]'));
  var eraLabel = document.querySelector('[data-era-label]');

  function markEra(id, name) {
    links.forEach(function (link) {
      var on = link.getAttribute('href') === '#' + id;
      link.classList.toggle('is-current', on);
      if (on) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
    if (eraLabel) eraLabel.textContent = name;
  }

  if (eras.length && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        markEra(entry.target.id, entry.target.getAttribute('data-era-name') || '');
      });
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });
    eras.forEach(function (era) { observer.observe(era); });
    markEra(eras[0].id, eras[0].getAttribute('data-era-name') || '');
  }
}());
