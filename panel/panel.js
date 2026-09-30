(() => {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const REFRESH_MS = 60_000;
  const STATUS_LABELS = {
    yeni: 'Yeni', onaylandi: 'Onaylandı', hazirlaniyor: 'Hazırlanıyor',
    kargoda: 'Kargoda', teslim: 'Teslim edildi', iptal: 'İptal',
  };
  const LOW_STOCK = 3;
  const money = new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', minimumFractionDigits: 0, maximumFractionDigits: 2 });
  const fmt = (kurus) => money.format(kurus / 100);
  const dateFmt = new Intl.DateTimeFormat('tr-TR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

  const state = { meta: null, orders: [], products: [], orderFilter: 'aktif', editing: null, timer: null };

  const el = (tag, attrs = {}, children = []) => {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => {
      if (v === undefined || v === null || v === false) return;
      if (k === 'text') node.textContent = v;
      else if (k === 'on') Object.entries(v).forEach(([ev, fn]) => node.addEventListener(ev, fn));
      else node.setAttribute(k, v === true ? '' : v);
    });
    children.forEach((c) => c && node.append(c));
    return node;
  };

  /* ---------- yardımcılar ---------- */
  function toKurus(text) {
    const clean = String(text).trim().replace(/\s|₺/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.');
    if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
    return Math.round(Number(clean) * 100);
  }
  const toTL = (kurus) => (kurus / 100).toLocaleString('tr-TR', { maximumFractionDigits: 2 });

  let toastTimer;
  function toast(msg, isError = false) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.toggle('is-error', isError);
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
  }

  async function api(path, { method = 'GET', body, raw, contentType } = {}) {
    const headers = { Accept: 'application/json' };
    if (method !== 'GET') headers['X-Sah-Panel'] = '1';
    let payload;
    if (raw) { payload = raw; headers['Content-Type'] = contentType; }
    else if (body !== undefined) { payload = JSON.stringify(body); headers['Content-Type'] = 'application/json'; }
    const res = await fetch(path, { method, headers, body: payload, credentials: 'same-origin' });
    const data = await res.json().catch(() => ({ success: false, error: 'Sunucuya ulaşılamadı. Panel yalnızca bilgisayardaki Şah sunucusu (python server.py) açıkken çalışır.' }));
    if (res.status === 401 && path !== '/api/admin/login') {
      showLogin();
      throw new Error('Oturum süresi doldu, tekrar giriş yapın.');
    }
    if (!res.ok || !data.success) throw new Error(data.error || 'İşlem başarısız.');
    return data.data;
  }

  /* ---------- oturum ---------- */
  function showLogin() {
    clearInterval(state.timer);
    $('#app').hidden = true;
    $('#login').hidden = false;
    $('#pw').focus();
  }

  async function showApp() {
    $('#login').hidden = true;
    $('#app').hidden = false;
    await Promise.all([loadOrders(), loadProducts(), loadSettings(), loadMenu()]);
    clearInterval(state.timer);
    state.timer = setInterval(() => loadOrders().catch(() => {}), REFRESH_MS);
  }

  async function onLogin(e) {
    e.preventDefault();
    const err = $('#loginError');
    err.hidden = true;
    try {
      await api('/api/admin/login', { method: 'POST', body: { password: $('#pw').value } });
      $('#pw').value = '';
      state.meta = await api('/api/admin/me');
      await showApp();
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  }

  /* ---------- siparişler ---------- */
  async function loadOrders() {
    state.orders = await api('/api/admin/orders');
    renderStats();
    renderOrderFilters();
    renderOrders();
  }

  function renderStats() {
    const today = new Date().toDateString();
    const live = state.orders.filter((o) => o.status !== 'iptal');
    const todays = live.filter((o) => new Date(o.createdAt).toDateString() === today);
    const fresh = state.orders.filter((o) => o.status === 'yeni').length;
    const low = state.products.filter((p) => p.active && p.stock <= LOW_STOCK).length;
    const badge = $('#newCount');
    badge.textContent = String(fresh);
    badge.hidden = fresh === 0;
    document.title = fresh ? `(${fresh}) Kiler Paneli — Şah` : 'Kiler Paneli — Şah';
    const stats = [
      ['Yeni sipariş', String(fresh), fresh ? 'hot' : ''],
      ['Bugünkü ciro', fmt(todays.reduce((s, o) => s + o.total, 0)), ''],
      ['Toplam sipariş', String(live.length), ''],
      ['Azalan stok', String(low), low ? 'warn' : ''],
    ];
    $('#stats').replaceChildren(...stats.map(([k, v, cls]) => el('div', { class: `stat ${cls}` }, [el('dt', { text: k }), el('dd', { text: v })])));
  }

  function renderOrderFilters() {
    const count = (fn) => state.orders.filter(fn).length;
    const filters = [
      ['aktif', 'Açık', (o) => !['teslim', 'iptal'].includes(o.status)],
      ...Object.entries(STATUS_LABELS).map(([k, label]) => [k, label, (o) => o.status === k]),
      ['hepsi', 'Hepsi', () => true],
    ];
    $('#orderFilters').replaceChildren(...filters.map(([key, label, fn]) => el('button', {
      type: 'button', class: 'chip', 'aria-pressed': String(state.orderFilter === key),
      text: `${label} (${count(fn)})`,
      on: { click: () => { state.orderFilter = key; renderOrderFilters(); renderOrders(); } },
    })));
  }

  function filteredOrders() {
    const f = state.orderFilter;
    if (f === 'hepsi') return state.orders;
    if (f === 'aktif') return state.orders.filter((o) => !['teslim', 'iptal'].includes(o.status));
    return state.orders.filter((o) => o.status === f);
  }

  function waLink(order) {
    const phone = `90${order.customer.phone.slice(1)}`;
    const msg = `Merhaba ${order.customer.name}, Şah Kiler'den ${order.id} numaralı siparişiniz hakkında yazıyoruz.`;
    return `https://wa.me/${phone}?text=${encodeURIComponent(msg)}`;
  }

  function orderCard(o) {
    const c = o.customer;
    const select = el('select', { 'aria-label': `${o.id} durumu`, class: `status s-${o.status}` },
      Object.entries(STATUS_LABELS).map(([k, label]) => el('option', { value: k, text: label, selected: k === o.status })));
    select.addEventListener('change', async () => {
      const prev = o.status;
      if (select.value === 'iptal' && !confirm(`${o.id} iptal edilsin mi? Ürünler stoğa geri eklenir.`)) {
        select.value = prev;
        return;
      }
      try {
        await api(`/api/admin/orders/${encodeURIComponent(o.id)}`, { method: 'PATCH', body: { status: select.value } });
        toast(`${o.id}: ${STATUS_LABELS[select.value]}`);
        await Promise.all([loadOrders(), loadProducts()]);
      } catch (ex) {
        select.value = prev;
        toast(ex.message, true);
      }
    });

    return el('article', { class: `order ${o.status === 'yeni' ? 'is-new' : ''}` }, [
      el('header', {}, [
        el('div', {}, [el('b', { class: 'oid', text: o.id }), el('time', { datetime: o.createdAt, text: dateFmt.format(new Date(o.createdAt)) })]),
        select,
      ]),
      el('div', { class: 'order-grid' }, [
        el('div', {}, [
          el('p', { class: 'cust', text: c.name }),
          el('p', {}, [el('a', { href: `tel:${c.phone}`, text: c.phone })]),
          el('p', { class: 'addr', text: `${c.address} — ${c.city}` }),
          c.note ? el('p', { class: 'note', text: `Not: ${c.note}` }) : null,
        ]),
        el('ul', { class: 'items' }, o.items.map((i) => el('li', {}, [
          el('span', { text: `${i.qty} × ${i.name}${i.size ? ` (${i.size})` : ''}` }), el('span', { text: fmt(i.total) }),
        ]))),
      ]),
      el('footer', {}, [
        el('span', { class: 'pay', text: state.meta?.payments?.[o.payment] || o.payment }),
        el('span', { class: 'sum', text: `Kargo ${fmt(o.shipping)} · Toplam ${fmt(o.total)}` }),
        el('a', { class: 'wa', href: waLink(o), target: '_blank', rel: 'noopener', text: 'WhatsApp' }),
      ]),
    ]);
  }

  function renderOrders() {
    const list = filteredOrders();
    $('#orderList').replaceChildren(...list.map(orderCard));
    $('#ordersEmpty').hidden = list.length > 0;
  }

  /* ---------- ürünler ---------- */
  async function loadProducts() {
    state.products = await api('/api/admin/products');
    renderProducts();
    renderStats();
  }

  function renderProducts() {
    const cats = state.meta?.categories || {};
    $('#productList').replaceChildren(...state.products.map((p) => el('button', {
      type: 'button', class: `p-card ${p.active ? '' : 'is-off'}`,
      on: { click: () => openProduct(p) },
    }, [
      p.image ? el('img', { src: `../${p.image}`, alt: '', width: '200', height: '240', loading: 'lazy' }) : el('span', { class: 'no-img', text: 'Görsel yok' }),
      el('span', { class: 'p-meta' }, [
        el('small', { text: `${cats[p.category] || p.category}${p.size ? ` · ${p.size}` : ''}` }),
        el('b', { text: p.name }),
        el('span', { class: 'p-row' }, [
          el('span', { class: 'p-price', text: fmt(p.price) }),
          el('span', { class: `p-stock ${p.stock <= LOW_STOCK ? 'low' : ''}`, text: `Stok: ${p.stock}` }),
        ]),
        p.active ? null : el('span', { class: 'off', text: 'Sitede gizli' }),
      ]),
    ])));
  }

  function openProduct(p) {
    state.editing = p?.id || null;
    const form = $('#productForm');
    form.reset();
    const cat = $('#pdCat');
    cat.replaceChildren(...Object.entries(state.meta.categories).map(([k, v]) => el('option', { value: k, text: v })));
    const v = p || { category: 'recel', stock: 10, sort: 100, active: true, image: '' };
    form.name.value = v.name || '';
    cat.value = v.category;
    form.size.value = v.size || '';
    form.price.value = v.price ? toTL(v.price) : '';
    form.stock.value = v.stock;
    form.badge.value = v.badge || '';
    form.sort.value = v.sort;
    form.description.value = v.description || '';
    form.active.checked = !!v.active;
    form.image.value = v.image || '';
    setPreview(v.image);
    $('#pdUploadState').textContent = '';
    $('#pd-title').textContent = p ? 'Ürünü düzenle' : 'Yeni ürün';
    $('#pdDelete').hidden = !p;
    $('#productError').hidden = true;
    $('#productDialog').showModal();
  }

  function setPreview(path) {
    const img = $('#pdPreview');
    if (path) img.src = `../${path}`;
    else img.removeAttribute('src');
  }

  async function onUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const stateEl = $('#pdUploadState');
    if (file.size > 5 * 1024 * 1024) { stateEl.textContent = 'Dosya 5 MB’den küçük olmalı.'; return; }
    stateEl.textContent = 'Yükleniyor…';
    try {
      const { path } = await api('/api/admin/upload', { method: 'POST', raw: file, contentType: file.type || 'application/octet-stream' });
      $('#productForm').image.value = path;
      setPreview(path);
      stateEl.textContent = 'Yüklendi — kaydetmeyi unutmayın.';
    } catch (ex) {
      stateEl.textContent = ex.message;
    } finally {
      e.target.value = '';
    }
  }

  async function onSaveProduct(e) {
    e.preventDefault();
    const f = e.target;
    const err = $('#productError');
    const price = toKurus(f.price.value);
    if (price === null || price < 100) {
      err.textContent = 'Fiyatı TL olarak girin (örn. 220 veya 219,90).';
      err.hidden = false;
      return;
    }
    const body = {
      name: f.name.value, category: f.category.value, size: f.size.value, price,
      stock: Number(f.stock.value), badge: f.badge.value, sort: Number(f.sort.value || 100),
      description: f.description.value, active: f.active.checked, image: f.image.value,
    };
    try {
      if (state.editing) await api(`/api/admin/products/${encodeURIComponent(state.editing)}`, { method: 'PUT', body });
      else await api('/api/admin/products', { method: 'POST', body });
      $('#productDialog').close();
      toast('Ürün kaydedildi');
      await loadProducts();
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  }

  async function onDeleteProduct() {
    const p = state.products.find((x) => x.id === state.editing);
    if (!p || !confirm(`“${p.name}” silinsin mi? Bu işlem geri alınamaz. (Geçici olarak gizlemek için “Sitede göster”i kapatabilirsiniz.)`)) return;
    try {
      await api(`/api/admin/products/${encodeURIComponent(p.id)}`, { method: 'DELETE' });
      $('#productDialog').close();
      toast('Ürün silindi');
      await loadProducts();
    } catch (ex) {
      toast(ex.message, true);
    }
  }

  /* ---------- menü ---------- */
  async function loadMenu() {
    const menu = await api('/api/admin/menu');
    const f = $('#menuForm');
    f.serpPrice.value = toTL(menu.serpme.price);
    f.serpNote.value = menu.serpme.note || '';
    f.serpDetail.value = menu.serpme.detail || '';
    $('#menuSections').replaceChildren(...menu.sections.map(menuSection));
  }

  function menuRow(item = { name: '', price: 0 }) {
    const row = el('div', { class: 'm-row' }, [
      el('input', { class: 'name', value: item.name, maxlength: '60', 'aria-label': 'Ürün adı', placeholder: 'Ürün adı' }),
      el('input', { class: 'price', value: item.price ? toTL(item.price) : '', inputmode: 'decimal', 'aria-label': 'Fiyat (₺)', placeholder: '₺' }),
      el('label', { class: 'addon', title: 'Fiyat “+25₺” gibi ek ücret olarak gösterilir' }, [
        el('input', { type: 'checkbox', class: 'is-addon', checked: item.addon === true }), 'ekstra',
      ]),
      el('button', { type: 'button', class: 'icon', 'aria-label': 'Satırı sil', text: '✕', on: { click: () => row.remove() } }),
    ]);
    return row;
  }

  function menuSection(section = { title: '', items: [] }) {
    const rows = el('div', { class: 'm-rows' }, section.items.map(menuRow));
    const card = el('section', { class: 'card m-sec' }, [
      el('div', { class: 'm-sec-head' }, [
        el('input', { class: 'sec-title', value: section.title, maxlength: '40', 'aria-label': 'Bölüm adı', placeholder: 'Bölüm adı' }),
        el('button', {
          type: 'button', class: 'icon', 'aria-label': 'Bölümü sil', text: '✕',
          on: { click: () => { if (confirm(`“${card.querySelector('.sec-title').value || 'Bu bölüm'}” silinsin mi?`)) card.remove(); } },
        }),
      ]),
      rows,
      el('button', { type: 'button', class: 'ghost add-row', text: '+ Satır ekle', on: { click: () => { rows.append(menuRow()); rows.lastChild.querySelector('input').focus(); } } }),
    ]);
    return card;
  }

  function collectMenu() {
    const f = $('#menuForm');
    const serpPrice = toKurus(f.serpPrice.value);
    if (serpPrice === null) throw new Error('Serpme kahvaltı fiyatını TL olarak girin.');
    const sections = [...document.querySelectorAll('#menuSections .m-sec')].map((card) => {
      const title = card.querySelector('.sec-title').value.trim();
      if (!title) throw new Error('Her bölümün bir adı olmalı.');
      const items = [...card.querySelectorAll('.m-row')]
        .filter((r) => r.querySelector('.name').value.trim())
        .map((r) => {
          const name = r.querySelector('.name').value.trim();
          const price = toKurus(r.querySelector('.price').value || '0');
          if (price === null) throw new Error(`“${name}” fiyatı geçersiz.`);
          return { name, price, addon: r.querySelector('.is-addon').checked };
        });
      return { title, items };
    });
    return { serpme: { price: serpPrice, note: f.serpNote.value, detail: f.serpDetail.value }, sections };
  }

  async function onSaveMenu(e) {
    e.preventDefault();
    const err = $('#menuError');
    err.hidden = true;
    try {
      await api('/api/admin/menu', { method: 'PUT', body: collectMenu() });
      toast('Menü kaydedildi');
      await loadMenu();
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  }

  /* ---------- ayarlar ---------- */
  async function loadSettings() {
    const s = await api('/api/admin/settings');
    const f = $('#settingsForm');
    f.shopOpen.checked = s.shopOpen;
    f.shippingFee.value = toTL(s.shippingFee);
    f.freeShippingMin.value = toTL(s.freeShippingMin);
    f.notice.value = s.notice;
    f.bankInfo.value = s.bankInfo;
  }

  async function onSaveSettings(e) {
    e.preventDefault();
    const f = e.target;
    const err = $('#settingsError');
    const fee = toKurus(f.shippingFee.value);
    const free = toKurus(f.freeShippingMin.value);
    if (fee === null || free === null) {
      err.textContent = 'Tutarları TL olarak girin (örn. 120 veya 0).';
      err.hidden = false;
      return;
    }
    err.hidden = true;
    try {
      await api('/api/admin/settings', {
        method: 'PUT',
        body: { shopOpen: f.shopOpen.checked, shippingFee: fee, freeShippingMin: free, notice: f.notice.value, bankInfo: f.bankInfo.value },
      });
      toast('Ayarlar kaydedildi');
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  }

  /* ---------- gezinme ---------- */
  function showView(name) {
    document.querySelectorAll('.view').forEach((v) => { v.hidden = v.id !== `view-${name}`; });
    document.querySelectorAll('.tab').forEach((t) => {
      if (t.dataset.view === name) t.setAttribute('aria-current', 'page');
      else t.removeAttribute('aria-current');
    });
  }

  async function init() {
    $('#loginForm').addEventListener('submit', onLogin);
    $('#logout').addEventListener('click', async () => {
      await api('/api/admin/logout', { method: 'POST' }).catch(() => {});
      showLogin();
    });
    document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => showView(t.dataset.view)));
    $('#refreshOrders').addEventListener('click', () => loadOrders().then(() => toast('Güncellendi')).catch((ex) => toast(ex.message, true)));
    $('#newProduct').addEventListener('click', () => openProduct(null));
    $('#productForm').addEventListener('submit', onSaveProduct);
    $('#pdFile').addEventListener('change', onUpload);
    $('#pdDelete').addEventListener('click', onDeleteProduct);
    $('#productDialog').addEventListener('click', (e) => {
      if (e.target.closest('[data-close]') || e.target === e.currentTarget) $('#productDialog').close();
    });
    $('#settingsForm').addEventListener('submit', onSaveSettings);
    $('#menuForm').addEventListener('submit', onSaveMenu);
    $('#addSection').addEventListener('click', () => {
      $('#menuSections').append(menuSection());
      $('#menuSections').lastChild.querySelector('input').focus();
    });

    try {
      state.meta = await api('/api/admin/me');
      await showApp();
    } catch {
      showLogin();
    }
  }

  init();
})();
