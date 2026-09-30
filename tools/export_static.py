"""Statik yayın (GitHub Pages) için ürün ve menü anlık görüntüsünü üretir.

Panelde ürün/menü değiştirdikten sonra çalıştırın, sonra değişiklikleri GitHub'a gönderin:
    python tools/export_static.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import store  # noqa: E402

OUT = ROOT / "assets" / "data"
FIELDS = ("id", "name", "category", "description", "size", "price", "badge", "image")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    products = [
        {**{k: p.get(k) for k in FIELDS}, "inStock": p["stock"] > 0,
         "maxQty": min(p["stock"], store.MAX_QTY_PER_ITEM)}
        for p in store.list_products()
    ]
    settings = store.public_settings()
    shop = {"products": products, "categories": store.CATEGORIES, "payments": store.PAYMENT_METHODS,
            "settings": {**settings, "notice": "Siparişiniz WhatsApp üzerinden alınır; teyit sonrası hazırlanır."}}
    (OUT / "shop.json").write_text(json.dumps(shop, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "menu.json").write_text(json.dumps(store.get_menu(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(products)} ürün ve menü assets/data/ klasörüne yazıldı.")


if __name__ == "__main__":
    main()
