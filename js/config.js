/*
 * Şah Kahvaltı — içerik ayarları.
 * Tüm fotoğraflar @sahkahvaltisalonu Instagram hesabından seçildi (assets/img).
 * Kiler ürünleri ve fiyatları panelden (/panel/) yönetilir.
 */
const IMG = (name) => `assets/img/${name}.jpg`;

window.SAH_CONFIG = Object.freeze({
  name: 'Şah Gözleme & Kahvaltı Salonu',
  owner: 'Konyalı Seyhan Bacı',
  phone: '+90 535 590 48 91',
  phoneRaw: '905355904891',
  address: '29 Ekim Mah. Atatürk Cad. No:69, Kaynaklar / Buca, İzmir',
  mapsQuery: 'Şah Kahvaltı ve Gözleme Salonu Seyhan Bacının Yeri, Buca İzmir',
  hours: { open: '09:00', close: '20:00', label: 'Haftanın her günü' },
  instagram: 'https://www.instagram.com/sahkahvaltisalonu/',
  tiktok: 'https://www.tiktok.com/@sahkahvaltisalonu',
  ratings: [
    { source: 'Google', score: '4.4', count: '400+ yorum' },
    { source: 'Yandex', score: '4.6', count: 'Haritalar' },
  ],

  images: Object.freeze({
    hero: IMG('gozleme-ayran'),
    heroSmall: IMG('kasar'),
    tray: IMG('bahce-sofra'),
    gozleme: IMG('seyhan-baci-yufka'),
    menemen: IMG('menemen-sofra'),
    kasar: IMG('kasar-sofra'),
    gozleme2: IMG('gozleme-ayran-2'),
    ates: IMG('ates'),
    recelKazan: IMG('recel-kazan'),
    saksilar: IMG('saksilar'),
    cardak: IMG('cardak'),
    salon: IMG('salon'),
    event: IMG('organizasyon'),
    kavanozlar: IMG('kavanozlar-bahce'),
    dukkan: IMG('dukkan'),
  }),

  // Sınırsız kahvaltı sofrasında gelenler — mekanla teyit edilip güncellenebilir.
  spread: [
    { name: 'Köy peynirleri', note: 'Beyaz peynir, tulum, çökelek, örgü' },
    { name: 'Eriyen kaşar', note: 'Bakır tavada, uzadıkça uzar' },
    { name: 'Sıcak gözleme', note: 'Seyhan Bacı’nın sacından, dilim dilim' },
    { name: 'Menemen', note: 'Bakır sahanda, domatesi bol' },
    { name: 'Ev reçelleri', note: 'Odun ateşinde, kazanda kaynar' },
    { name: 'Bal & kaymak', note: 'Tereyağıyla, sıcak ekmeğe' },
    { name: 'Sigara böreği & patates', note: 'Çıtır çıtır, sıcak sıcak' },
    { name: 'Zeytin çeşitleri', note: 'Siyah, yeşil, kırma' },
    { name: 'Yaprak sarma', note: 'Zeytinyağlı, limonlu' },
    { name: 'Közlenmiş patlıcan & şakşuka', note: 'Her gün ocakta' },
    { name: 'Söğüş & yeşillik', note: 'Domates, salatalık, biber, roka' },
    { name: 'Demlik çay', note: 'Semaverden, bardak boş kalmaz' },
  ],

  events: [
    { title: 'Doğum günü', text: 'Bahçede masa düzeni, pasta servisi ve çocuklar için geniş alan.' },
    { title: 'Nişan & söz', text: 'Çardağın altında çiçek takı, uzun aile sofraları.' },
    { title: 'Aile kahvaltısı', text: 'Hafta sonu üç kuşak bir arada; önceden haber verin, masa hazır.' },
    { title: 'Kurumsal buluşma', text: 'Ekip kahvaltıları ve toplu rezervasyonlar için özel düzen.' },
  ],

  reviews: [
    { text: 'Bahçeye oturduk, ağaçların sesi, kuşların sesi… Kalabalık olmasına rağmen kahvaltımız 5 dakikada geldi.', author: 'Efe M.', source: 'Google' },
    { text: 'Kaynaklar’da hafta sonu kahvaltısı için tercih ettiğimiz yerlerden. Çok çeşit ve dolu dolu.', author: 'Vildan N.', source: 'Google' },
    { text: 'Her şey mükemmel, gelip görmeniz lazım.', author: 'Muammer T.', source: 'Google' },
  ],
});
