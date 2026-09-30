(() => {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const money = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 });
  const tl = (kurus) => `${money.format(kurus / 100)}₺`;

  const el = (tag, attrs = {}, children = []) => {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (v === undefined || v === null || v === false) return;
      if (k === 'text') node.textContent = v;
      else node.setAttribute(k, v);
    });
    children.forEach((c) => c && node.append(c));
    return node;
  };

  function priceRow(item) {
    return el('li', { class: item.addon ? 'is-addon' : null }, [
      el('span', { class: 'm-name', text: item.name }),
      el('span', { class: 'm-dots', 'aria-hidden': 'true' }),
      el('span', { class: 'm-price', text: `${item.addon ? '+' : ''}${tl(item.price)}` }),
    ]);
  }

  function serpmeCard(serpme) {
    return el('article', { class: 'm-card m-serpme' }, [
      el('h3', { text: 'Serpme Kahvaltı' }),
      el('p', { class: 'm-big' }, [el('b', { text: tl(serpme.price) }), el('span', { text: serpme.note || 'Kişi başı' })]),
      serpme.detail ? el('p', { class: 'm-detail', text: serpme.detail }) : null,
      el('a', { class: 'btn btn-light', href: '#rezervasyon', text: 'Masa ayırt' }),
    ]);
  }

  function sectionCard(section) {
    return el('article', { class: `m-card m-${section.id}` }, [
      el('h3', { text: section.title }),
      el('ul', { class: 'm-list' }, section.items.map(priceRow)),
    ]);
  }

  function applySerpme(serpme) {
    $('#serpmePrice').textContent = tl(serpme.price);
    $('#heroPrice').textContent = tl(serpme.price);
    const minNote = (serpme.note || '').split('·').pop().trim();
    if (minNote) $('#serpmeNote').textContent = minNote;
    if (serpme.detail) $('#serpmeDetail').textContent = serpme.detail;
  }

  function applyGozlemeChips(sections) {
    const gozleme = sections.find((s) => s.id === 'gozleme');
    if (!gozleme) return;
    $('#gozlemeList').replaceChildren(...gozleme.items.filter((i) => !i.addon).map((i) =>
      el('li', {}, [el('b', { text: i.name }), el('small', { text: tl(i.price) })])));
  }

  /** Önce canlı API; sunucu yoksa (ör. GitHub Pages) statik anlık görüntü. */
  async function loadMenu() {
    try {
      const res = await fetch('/api/menu', { headers: { Accept: 'application/json' } });
      const body = await res.json();
      if (res.ok && body.success) return body.data;
    } catch { /* sunucu yok */ }
    const res = await fetch('assets/data/menu.json');
    if (!res.ok) throw new Error('Menü yüklenemedi');
    return res.json();
  }

  async function init() {
    const state = $('#menuState');
    try {
      const { serpme, sections } = await loadMenu();
      $('#menuBoard').replaceChildren(serpmeCard(serpme), ...sections.filter((s) => s.items.length).map(sectionCard));
      applySerpme(serpme);
      applyGozlemeChips(sections);
      state.hidden = true;
    } catch {
      state.replaceChildren('Menü şu an yüklenemedi. ',
        el('a', { href: 'assets/img/menu.jpg', target: '_blank', rel: 'noopener', text: 'Basılı menüyü açın →' }));
    }
  }

  init();
})();
