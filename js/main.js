(() => {
  'use strict';

  const C = window.SAH_CONFIG;
  const $ = (sel) => document.querySelector(sel);
  const SLOT_MINUTES = 30;
  const MAX_PEOPLE = 200;

  const el = (tag, attrs = {}, children = []) => {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === 'text') node.textContent = v;
      else node.setAttribute(k, v);
    });
    children.forEach((c) => node.append(c));
    return node;
  };

  const toMinutes = (hhmm) => {
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + m;
  };
  const fromMinutes = (min) =>
    `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`;

  /* ---------- Görseller ---------- */
  function renderImages() {
    document.querySelectorAll('img[data-img]').forEach((img) => {
      const src = C.images[img.dataset.img];
      if (src) img.src = src;
    });
  }

  /* ---------- İçerik listeleri ---------- */
  function renderContent() {
    const words = ['Sınırsız kahvaltı', 'Sacda gözleme', 'Bal & kaymak', 'Bakır sahanda menemen',
      'Sıcak bazlama', 'Demlik çay', 'Ağaç gölgesi', 'Kaynaklar'];
    const track = $('#marquee');
    [...words, ...words].forEach((w) => track.append(el('span', { text: w })));

    const spread = $('#spreadList');
    C.spread.forEach((item) =>
      spread.append(el('li', {}, [el('div', {}, [el('b', { text: item.name }), el('small', { text: item.note })])])));


    const events = $('#eventGrid');
    C.events.forEach((e, i) => events.append(el('article', { class: 'event' }, [
      el('span', { class: 'event-num', text: `0${i + 1}` }),
      el('h3', { text: e.title }),
      el('p', { text: e.text }),
    ])));

    const scores = $('#scores');
    C.ratings.forEach((r) => scores.append(el('div', { class: 'score' }, [
      el('b', { text: r.score }),
      el('span', { class: 'stars', text: '★★★★★' }),
      el('span', { text: ` ${r.source} · ${r.count}` }),
    ])));

    const reviews = $('#reviewList');
    C.reviews.forEach((r) => reviews.append(el('figure', { class: 'review reveal' }, [
      el('div', {}, [el('span', { class: 'stars', text: '★★★★★' }), el('blockquote', { text: `“${r.text}”` })]),
      el('figcaption', { text: `— ${r.author}, ${r.source} yorumu` }),
    ])));

    $('#addr').textContent = C.address;
    $('#hours').textContent = `${C.hours.label}, ${C.hours.open} – ${C.hours.close}`;
    const q = encodeURIComponent(C.mapsQuery);
    $('#map').src = `https://www.google.com/maps?q=${q}&output=embed`;
    $('#directions').href = `https://www.google.com/maps/dir/?api=1&destination=${q}`;
    $('#year').textContent = new Date().getFullYear();
  }

  /* ---------- Açık / kapalı durumu (İstanbul saati) ---------- */
  function renderOpenStatus() {
    const parts = new Intl.DateTimeFormat('tr-TR', {
      timeZone: 'Europe/Istanbul', hour: '2-digit', minute: '2-digit', hour12: false,
    }).formatToParts(new Date());
    const get = (t) => Number(parts.find((p) => p.type === t)?.value ?? 0);
    const now = get('hour') * 60 + get('minute');
    const isOpen = now >= toMinutes(C.hours.open) && now < toMinutes(C.hours.close);
    $('#openDot').classList.toggle('open', isOpen);
    const nextDay = now < toMinutes(C.hours.open) ? 'Bugün' : 'Yarın';
    $('#openStatus').textContent = isOpen
      ? `Şu an açık · ${C.hours.close}'e kadar`
      : `Şu an kapalı · ${nextDay} ${C.hours.open}'da açılır`;
  }

  /* ---------- Navigasyon ---------- */
  function initNav() {
    const nav = $('#nav');
    const burger = $('#burger');
    const links = $('#navLinks');
    const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 40);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    const setOpen = (open) => {
      links.classList.toggle('open', open);
      nav.classList.toggle('menu-open', open);
      burger.setAttribute('aria-expanded', String(open));
      burger.setAttribute('aria-label', open ? 'Menüyü kapat' : 'Menüyü aç');
      document.body.style.overflow = open ? 'hidden' : '';
    };
    burger.addEventListener('click', () => setOpen(!links.classList.contains('open')));
    links.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
  }

  /* ---------- Görünüme girince belirme ---------- */
  function initReveal() {
    const items = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window)) {
      items.forEach((i) => i.classList.add('in'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
      });
    }, { threshold: 0.12 });
    items.forEach((i) => io.observe(i));
  }

  /* ---------- Rezervasyon formu ---------- */
  function initForm() {
    const form = $('#reserveForm');
    const date = $('#fDate');
    const time = $('#fTime');
    const type = $('#fType');
    const errorBox = $('#formError');

    const today = new Date();
    const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    date.min = iso(today);
    date.value = iso(today);

    const lastSlot = toMinutes(C.hours.close) - 60;
    for (let m = toMinutes(C.hours.open); m <= lastSlot; m += SLOT_MINUTES) {
      time.append(el('option', { value: fromMinutes(m), text: fromMinutes(m) }));
    }
    time.value = '10:00';

    document.querySelectorAll('a[data-type]').forEach((a) =>
      a.addEventListener('click', () => { type.value = a.dataset.type; }));

    const showError = (msg, field) => {
      errorBox.textContent = msg;
      errorBox.hidden = false;
      if (field) { field.setAttribute('aria-invalid', 'true'); field.focus(); }
    };

    form.addEventListener('input', (e) => {
      e.target.removeAttribute('aria-invalid');
      errorBox.hidden = true;
    });

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      const name = String(data.name || '').trim();
      const people = Number(data.people);

      if (name.length < 2) return showError('Lütfen adınızı ve soyadınızı yazın.', $('#fName'));
      if (!data.date || data.date < date.min) return showError('Lütfen bugün veya ileri bir tarih seçin.', date);
      if (!Number.isInteger(people) || people < 1 || people > MAX_PEOPLE) {
        return showError(`Kişi sayısı 1 ile ${MAX_PEOPLE} arasında olmalı.`, $('#fPeople'));
      }

      const [y, mo, d] = data.date.split('-');
      const lines = [
        'Merhaba, rezervasyon yapmak istiyorum.',
        `Ad Soyad: ${name}`,
        `Tarih: ${d}.${mo}.${y} — Saat: ${data.time}`,
        `Kişi: ${people}`,
        `Tür: ${data.type}`,
      ];
      const note = String(data.note || '').trim();
      if (note) lines.push(`Not: ${note}`);

      const url = `https://wa.me/${C.phoneRaw}?text=${encodeURIComponent(lines.join('\n'))}`;
      window.open(url, '_blank', 'noopener');
    });
  }

  renderImages();
  renderContent();
  renderOpenStatus();
  initNav();
  initReveal();
  initForm();
  setInterval(renderOpenStatus, 60_000);
})();
