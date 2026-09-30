# Şah Gözleme & Kahvaltı Salonu — Site + Kiler

Tanıtım sitesi, **Kiler** online satış bölümü ve **yönetim paneli**.

## Çalıştırma

```bash
python server.py
```

- Site: http://127.0.0.1:8966
- Panel: http://127.0.0.1:8966/panel/
- Panel şifresi `.env` dosyasındaki `SAH_ADMIN_PASSWORD` satırıdır. İstediğiniz zaman değiştirebilirsiniz (en az 10 karakter), sonra sunucuyu yeniden başlatın.

Python 3.10+ yeterli, ek paket gerekmez.

## Panelde neler var

| Bölüm | Ne yapar |
|---|---|
| **Siparişler** | Yeni siparişler, günlük ciro, durum değiştirme (Yeni → Onaylandı → Hazırlanıyor → Kargoda → Teslim), müşteriye tek tıkla WhatsApp. İptal edilen siparişin ürünleri stoğa geri eklenir. |
| **Ürünler** | Ürün ekle / düzenle / sil / gizle, fiyat, stok, etiket (Organik vb.), **kavanoz fotoğrafı yükleme**. |
| **Menü** | Serpme kahvaltı fiyatı ve tüm menü bölümleri (gözleme, sıcak kahvaltılar, içecekler…); satır/bölüm ekle-sil, fiyat güncelle. Basılı menü görseli `assets/img/menu.jpg`. |
| **Ayarlar** | Kargo ücreti, ücretsiz kargo limiti, havale (IBAN) bilgisi, mağaza duyurusu, siparişleri açma/kapama. |

## Kendi kavanoz fotoğraflarınız

`assets/products/` içindeki SVG kavanozlar geçicidir. Fotoğraflarınız hazır olunca panelde ürüne tıklayın,
**Görsel yükle** deyin ve kaydedin. Kare ya da 4:5 dikey, açık zeminli fotoğraflar en iyi sonucu verir.

## Dosyalar

- `server.py`: web sunucusu ve API
- `store.py`: ürün, sipariş ve ayar verisi (`data/*.json`)
- `index.html`, `css/`, `js/`: site ve Kiler
- `panel/`: yönetim paneli
- `assets/img/`: @sahkahvaltisalonu Instagram hesabından seçilmiş fotoğraflar
- `tests/`: testler (`python -m unittest discover -s tests`)

## GitHub Pages yayını

Site https://emirhanerdgn.github.io/sah-kahvalti/ adresinde sunucusuz (statik) çalışır:
menü ve ürünler `assets/data/` içindeki anlık görüntüden okunur, siparişler hazır mesajla WhatsApp'a gider.
Panel yalnızca bilgisayarda `python server.py` çalışırken kullanılabilir.

Panelde ürün veya menü değiştirdikten sonra yayını güncellemek için:

```bash
python tools/export_static.py
git add -A && git commit -m "chore: menü ve ürünleri güncelle" && git push
```

## Yayına alırken

- Sunucuyu bir HTTPS ters vekil (Caddy / Nginx) arkasında çalıştırın ve `.env` içinde `SAH_SECURE_COOKIE=1` yapın.
- `data/` klasörünü düzenli yedekleyin; siparişler oradadır.
- Sipariş sayfası kişisel veri topladığı için bir KVKK aydınlatma metni eklenmelidir.
