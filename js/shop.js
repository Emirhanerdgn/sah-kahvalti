(() => {
  'use strict';

  const C = window.SAH_CONFIG;
  const $ = (sel) => document.querySelector(sel);
  const CART_KEY = 'sah-cart-v1';
  const MIN_ADDRESS = 10;
  const PHONE_RE = /^(?:\+?90|0)?5\d{9}$/;
  const money = new Intl.NumberFormat('tr-TR', {
    style: 'currency', currency: 'TRY', minimumFractionDigits: 0, maximumFractionDigits: 2,
  });
  const fmt = (kurus) => money.format(kurus / 100);

  const state = { products: [], categories: {}, settings: null, filter: 'all', cart: loadCart(), staticMode: false };

  /** Önce canlı API; sunucu yoksa (ör. GitHub Pages) statik anlık görüntü. */
  async function fetchData(apiUrl, staticUrl) {
    try {
      const res = await fetch(apiUrl, { headers: { Accept: 'application/json' } });
      const body = await res.json();
      if (res.ok && body.success) return { data: body.data, isStatic: false };
    } catch { /* sunucu yok, statik dosyaya geç */ }
    const res = await fetch(staticUrl, { headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error('Veri yüklenemedi');
    return { data: await res.json(), isStatic: true };
  }

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

  /* ---------- sepet deposu (tarayıcıda) ---------- */
  function loadCart() {
    try {
      const raw = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
      return Array.isArray(raw) ? raw.filter((l) => typeof l.id === 'string' && Number.isInteger(l.qty) && l.qty > 0) : [];
    } catch {
      return [];
    }
  }
  function saveCart(cart) {
    state.cart = cart;
    try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch { /* gizli sekme: sepet sadece bu oturumda kalır */ }
    renderCart();
    renderProducts();
  }
  const productById = (id) => state.products.find((p) => p.id === id);
  const qtyInCart = (id) => state.cart.find((l) => l.id === id)?.qty ?? 0;

  function setQty(id, qty) {
    const p = productById(id);
    if (!p) return;
    const clamped = Math.max(0, Math.min(qty, p.maxQty));
    const rest = state.cart.filter((l) => l.id !== id);
    const exists = state.cart.some((l) => l.id === id);
    const next = clamped === 0 ? rest
      : exists ? state.cart.map((l) => (l.id === id ? { ...l, qty: clamped } : l))
        : [...state.cart, { id, qty: clamped }];
    saveCart(next);
  }

  function totals() {
    const lines = state.cart
      .map((l) => ({ ...l, product: productById(l.id) }))
      .filter((l) => l.product);
    const subtotal = lines.reduce((s, l) => s + l.product.price * l.qty, 0);
    const s = state.settings;
    const free = s.freeShippingMin > 0 && subtotal >= s.freeShippingMin;
    const shipping = subtotal === 0 || free ? 0 : s.shippingFee;
    return { lines, subtotal, shipping, total: subtotal + shipping, free };
  }

  /* ---------- ürünler ---------- */
  async function loadShop() {
    try {
      const { data, isStatic } = await fetchData('/api/shop', 'assets/data/shop.json');
      state.staticMode = isStatic;
      state.products = data.products;
      state.categories = data.categories;
      state.settings = data.settings;
      if (isStatic) $('#placeOrder').textContent = 'WhatsApp ile sipariş ver';
      const known = new Set(state.products.map((p) => p.id));
      saveCart(state.cart.filter((l) => known.has(l.id)));
      renderFilters();
      $('#shopNotice').textContent = state.settings.notice || '';
      if (!state.settings.shopOpen) showState('Kiler şu an sipariş almıyor. Çok yakında yeniden açılacak.');
    } catch (err) {
      showState('Kiler şu an yüklenemedi. Siparişiniz için bize WhatsApp\'tan yazabilirsiniz.', true);
    }
  }

  function showState(text, withWa = false) {
    const box = $('#shopState');
    box.replaceChildren(text);
    if (withWa) {
      box.append(' ', el('a', { href: `https://wa.me/${C.phoneRaw}`, target: '_blank', rel: 'noopener', text: 'WhatsApp →' }));
    }
    box.hidden = false;
  }

  function renderFilters() {
    const used = [...new Set(state.products.map((p) => p.category))];
    const chips = [['all', 'Tümü'], ...used.map((c) => [c, state.categories[c] || c])];
    const wrap = $('#shopFilters');
    wrap.replaceChildren(...chips.map(([key, label]) => el('button', {
      type: 'button', class: 'chip', 'aria-pressed': String(state.filter === key), text: label,
      on: { click: () => { state.filter = key; renderFilters(); renderProducts(); } },
    })));
  }

  function stepper(p, qty) {
    return el('div', { class: 'stepper', role: 'group', 'aria-label': `${p.name} adedi` }, [
      el('button', { type: 'button', 'aria-label': 'Azalt', text: '−', on: { click: () => setQty(p.id, qty - 1) } }),
      el('output', { text: String(qty), 'aria-live': 'polite' }),
      el('button', { type: 'button', 'aria-label': 'Artır', text: '+', disabled: qty >= p.maxQty, on: { click: () => setQty(p.id, qty + 1) } }),
    ]);
  }

  function productCard(p) {
    const qty = qtyInCart(p.id);
    const open = state.settings?.shopOpen;
    let action;
    if (!p.inStock) action = el('span', { class: 'sold-out', text: 'Tükendi' });
    else if (!open) action = el('span', { class: 'sold-out', text: 'Sipariş kapalı' });
    else if (qty > 0) action = stepper(p, qty);
    else action = el('button', { type: 'button', class: 'add-btn', text: 'Sepete ekle', on: { click: () => { setQty(p.id, 1); bumpFab(); } } });

    return el('article', { class: `product${p.inStock ? '' : ' is-out'}` }, [
      el('div', { class: 'product-media' }, [
        p.image ? el('img', { src: p.image, alt: `${p.name} kavanozu`, width: '400', height: '480', loading: 'lazy' }) : null,
        p.badge ? el('span', { class: 'badge', text: p.badge }) : null,
      ]),
      el('div', { class: 'product-body' }, [
        el('p', { class: 'product-cat', text: `${state.categories[p.category] || ''}${p.size ? ` · ${p.size}` : ''}` }),
        el('h3', { text: p.name }),
        p.description ? el('p', { class: 'product-desc', text: p.description }) : null,
        el('div', { class: 'product-foot' }, [el('b', { class: 'price', text: fmt(p.price) }), action]),
      ]),
    ]);
  }

  function renderProducts() {
    if (!state.settings) return;
    const list = state.products.filter((p) => state.filter === 'all' || p.category === state.filter);
    $('#productGrid').replaceChildren(...list.map(productCard));
    const box = $('#shopState');
    if (state.settings.shopOpen) box.hidden = list.length > 0;
    if (!list.length && state.settings.shopOpen) box.textContent = 'Bu kategoride şu an ürün yok.';
  }

  /* ---------- sepet çekmecesi ---------- */
  function totalsList(t) {
    const rows = [
      ['Ara toplam', fmt(t.subtotal)],
      ['Kargo', t.shipping === 0 && t.subtotal > 0 ? 'Ücretsiz' : fmt(t.shipping)],
      ['Toplam', fmt(t.total)],
    ];
    return rows.flatMap(([k, v], i) => [el('dt', { text: k, class: i === 2 ? 'grand' : null }), el('dd', { text: v, class: i === 2 ? 'grand' : null })]);
  }

  function renderCart() {
    if (!state.settings) return;
    const t = totals();
    const count = t.lines.reduce((s, l) => s + l.qty, 0);
    $('#cartCount').textContent = String(count);
    $('#cartFab').hidden = count === 0;
    $('#cartEmpty').hidden = count > 0;
    $('#checkoutBtn').disabled = count === 0 || !state.settings.shopOpen;

    $('#cartLines').replaceChildren(...t.lines.map((l) => el('li', { class: 'cart-line' }, [
      l.product.image ? el('img', { src: l.product.image, alt: '', width: '64', height: '77' }) : el('span'),
      el('div', {}, [
        el('b', { text: l.product.name }),
        el('small', { text: `${l.product.size || ''} · ${fmt(l.product.price)}` }),
        stepper(l.product, l.qty),
      ]),
      el('button', { type: 'button', class: 'icon-btn remove', 'aria-label': `${l.product.name} ürününü çıkar`, text: '✕', on: { click: () => setQty(l.id, 0) } }),
    ])));

    const s = state.settings;
    const hint = $('#freeShip');
    if (s.freeShippingMin > 0 && t.subtotal > 0 && !t.free) {
      hint.textContent = `${fmt(s.freeShippingMin - t.subtotal)} daha ekleyin, kargo ücretsiz olsun.`;
    } else {
      hint.textContent = t.free ? 'Kargo ücretsiz 🎉' : '';
    }
    $('#cartTotals').replaceChildren(...totalsList(t));
    $('#checkoutTotals').replaceChildren(...totalsList(t));
  }

  function setCartOpen(open) {
    const cart = $('#cart');
    cart.classList.toggle('open', open);
    cart.setAttribute('aria-hidden', String(!open));
    cart.inert = !open;
    $('#cartScrim').hidden = !open;
    $('#cartFab').setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('no-scroll', open);
    if (open) $('#cartClose').focus();
  }

  function bumpFab() {
    const fab = $('#cartFab');
    fab.classList.remove('bump');
    void fab.offsetWidth; // animasyonu yeniden başlat
    fab.classList.add('bump');
  }

  /* ---------- ödeme ---------- */
  function validate(data) {
    if (data.name.length < 3) return ['Ad ve soyadınızı yazın.', 'cName'];
    if (!PHONE_RE.test(data.phone.replace(/[\s()-]/g, ''))) return ['Geçerli bir cep telefonu girin (05xx xxx xx xx).', 'cPhone'];
    if (data.city.length < 2) return ['İl / ilçe bilgisini yazın.', 'cCity'];
    if (data.address.length < MIN_ADDRESS) return ['Açık adresinizi biraz daha ayrıntılı yazın.', 'cAddress'];
    if (!data.consent) return ['Devam etmek için onay kutusunu işaretleyin.', null];
    return null;
  }

  function showError(msg, fieldId) {
    const box = $('#checkoutError');
    box.textContent = msg;
    box.hidden = false;
    if (fieldId) {
      const f = document.getElementById(fieldId);
      f.setAttribute('aria-invalid', 'true');
      f.focus();
    }
  }

  async function submitOrder(e) {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    const data = {
      name: String(fd.get('name') || '').trim(),
      phone: String(fd.get('phone') || '').trim(),
      city: String(fd.get('city') || '').trim(),
      address: String(fd.get('address') || '').trim(),
      note: String(fd.get('note') || '').trim(),
      payment: String(fd.get('payment') || 'kapida'),
      consent: fd.get('consent') === 'on',
    };
    const problem = validate(data);
    if (problem) return showError(...problem);
    $('#checkoutError').hidden = true;

    if (state.staticMode) return orderViaWhatsApp(data);

    const btn = $('#placeOrder');
    btn.disabled = true;
    btn.textContent = 'Gönderiliyor…';
    try {
      const res = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer: { name: data.name, phone: data.phone, city: data.city, address: data.address, note: data.note },
          items: state.cart.map(({ id, qty }) => ({ id, qty })),
          payment: data.payment,
          consent: data.consent,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || !body.success) throw new Error(body.error || 'Sipariş gönderilemedi, lütfen tekrar deneyin.');
      showDone(body.data, data);
      saveCart([]);
      form.reset();
      loadShop(); // stokları tazele
    } catch (err) {
      showError(err.message || 'Bağlantı hatası, lütfen tekrar deneyin.', null);
    } finally {
      btn.disabled = false;
      btn.textContent = state.staticMode ? 'WhatsApp ile sipariş ver' : 'Siparişi gönder';
    }
  }

  /** Sunucusuz yayında sipariş: hazır mesajla WhatsApp'ı açar. */
  function orderViaWhatsApp(data) {
    const t = totals();
    const pay = data.payment === 'havale' ? 'Havale / EFT' : 'Kapıda ödeme';
    const lines = t.lines.map((l) => `• ${l.qty} x ${l.product.name}${l.product.size ? ` (${l.product.size})` : ''} — ${fmt(l.product.price * l.qty)}`);
    const msg = ["Merhaba, Kiler'den sipariş vermek istiyorum.", ...lines,
      `Kargo: ${t.shipping ? fmt(t.shipping) : 'Ücretsiz'}`, `Toplam: ${fmt(t.total)} (${pay})`, '',
      `Ad Soyad: ${data.name}`, `Telefon: ${data.phone}`, `Adres: ${data.address} — ${data.city}`,
      ...(data.note ? [`Not: ${data.note}`] : [])].join('\n');
    const url = `https://wa.me/${C.phoneRaw}?text=${encodeURIComponent(msg)}`;
    window.open(url, '_blank', 'noopener');
    $('#checkoutForm').hidden = true;
    $('#checkoutDone').hidden = false;
    $('#doneId').textContent = 'WhatsApp açıldı';
    $('#doneText').textContent = `Toplam ${fmt(t.total)} · ${pay}. Hazırlanan mesajı WhatsApp'ta göndermeniz yeterli; siparişinizi teyit edip hazırlayacağız.`;
    $('#doneBank').hidden = true;
    $('#doneWa').href = url;
    $('#doneWa').textContent = 'WhatsApp açılmadıysa tıklayın';
    saveCart([]);
    $('#checkoutForm').reset();
  }

  function showDone(order, data) {
    $('#checkoutForm').hidden = true;
    $('#checkoutDone').hidden = false;
    $('#doneId').textContent = `Sipariş no: ${order.id}`;
    const pay = order.payment === 'havale' ? 'Havale / EFT' : 'Kapıda ödeme';
    $('#doneText').textContent = `Toplam ${fmt(order.total)} · ${pay}. Siparişinizi WhatsApp'tan teyit ettiğinizde hemen hazırlamaya başlıyoruz.`;
    const bank = $('#doneBank');
    bank.hidden = !order.bankInfo;
    bank.textContent = order.bankInfo || '';
    const lines = order.items.map((i) => `• ${i.qty} x ${i.name}${i.size ? ` (${i.size})` : ''}`);
    const msg = [`Merhaba, Kiler'den sipariş verdim.`, `Sipariş no: ${order.id}`, ...lines,
      `Toplam: ${fmt(order.total)} (${pay})`, `Ad: ${data.name}`].join('\n');
    $('#doneWa').href = `https://wa.me/${C.phoneRaw}?text=${encodeURIComponent(msg)}`;
  }

  function openCheckout() {
    const dlg = $('#checkout');
    $('#checkoutForm').hidden = false;
    $('#checkoutDone').hidden = true;
    $('#checkoutError').hidden = true;
    setCartOpen(false);
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');
  }

  function closeCheckout() {
    const dlg = $('#checkout');
    if (typeof dlg.close === 'function') dlg.close();
    else dlg.removeAttribute('open');
  }

  function init() {
    $('#cartFab').addEventListener('click', () => setCartOpen(true));
    $('#cartClose').addEventListener('click', () => setCartOpen(false));
    $('#cartScrim').addEventListener('click', () => setCartOpen(false));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setCartOpen(false); });
    $('#checkoutBtn').addEventListener('click', openCheckout);
    $('#checkoutForm').addEventListener('submit', submitOrder);
    $('#checkoutForm').addEventListener('input', (e) => {
      e.target.removeAttribute('aria-invalid');
      $('#checkoutError').hidden = true;
    });
    $('#checkout').addEventListener('click', (e) => {
      if (e.target.closest('[data-close]') || e.target === e.currentTarget) closeCheckout();
    });
    loadShop();
  }

  init();
})();
