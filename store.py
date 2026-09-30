"""Şah Kiler — veri katmanı: ürünler, siparişler, ayarlar (JSON dosyaları)."""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TR_TZ = timezone(timedelta(hours=3))

CATEGORIES = {
    "zeytinyagi": "Zeytinyağı",
    "recel": "Reçel",
    "zeytin": "Zeytin",
    "tereyagi": "Tereyağı",
    "peynir": "Peynir",
    "bal": "Bal",
    "diger": "Diğer",
}
ORDER_STATUSES = ("yeni", "onaylandi", "hazirlaniyor", "kargoda", "teslim", "iptal")
PAYMENT_METHODS = {"kapida": "Kapıda ödeme", "havale": "Havale / EFT"}
MAX_QTY_PER_ITEM = 10
MAX_ITEMS = 20
MAX_OPEN_ORDERS_PER_PHONE = 3

_lock = threading.RLock()


class ValidationError(ValueError):
    """Kullanıcıya gösterilebilir doğrulama hatası."""


class NotFound(LookupError):
    """İstenen kayıt yok."""


# ---------- dosya yardımcıları ----------

def _path(name: str) -> Path:
    return DATA_DIR / f"{name}.json"


def _read(name: str, default):
    p = _path(name)
    if not p.exists():
        return default
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _write(name: str, value) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _path(name).with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path(name))


def now_iso() -> str:
    return datetime.now(TR_TZ).isoformat(timespec="seconds")


# ---------- doğrulama yardımcıları ----------

def _text(value, field: str, *, min_len=0, max_len=200, required=True) -> str:
    s = str(value if value is not None else "").strip()
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    if required and len(s) < max(min_len, 1):
        raise ValidationError(f"{field} gerekli.")
    if len(s) > max_len:
        raise ValidationError(f"{field} en fazla {max_len} karakter olabilir.")
    return s


def _int(value, field: str, *, lo: int, hi: int) -> int:
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise ValidationError(f"{field} tam sayı olmalı.")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} sayı olmalı.") from None
    if not lo <= n <= hi:
        raise ValidationError(f"{field} {lo} ile {hi} arasında olmalı.")
    return n


def normalize_phone(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("90"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"5\d{9}", digits):
        raise ValidationError("Geçerli bir cep telefonu girin (05xx xxx xx xx).")
    return "0" + digits


def slugify(text: str) -> str:
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = text.translate(table).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48] or "urun"


# ---------- ürünler ----------

def list_products(*, include_inactive=False) -> list[dict]:
    with _lock:
        items = _read("products", [])
    items = sorted(items, key=lambda p: (p.get("sort", 999), p["name"]))
    return items if include_inactive else [p for p in items if p.get("active")]


def _validate_product(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Geçersiz ürün verisi.")
    category = str(data.get("category", ""))
    if category not in CATEGORIES:
        raise ValidationError("Kategori seçin.")
    image = _text(data.get("image"), "Görsel", max_len=200, required=False)
    if image and not re.fullmatch(r"assets/(products|uploads)/[a-z0-9._-]+\.(svg|jpg|jpeg|png|webp)", image):
        raise ValidationError("Görsel yolu geçersiz.")
    return {
        "name": _text(data.get("name"), "Ürün adı", min_len=2, max_len=80),
        "category": category,
        "description": _text(data.get("description"), "Açıklama", max_len=600, required=False),
        "size": _text(data.get("size"), "Gramaj", max_len=30, required=False),
        "price": _int(data.get("price"), "Fiyat (kuruş)", lo=100, hi=10_000_000),
        "stock": _int(data.get("stock", 0), "Stok", lo=0, hi=100_000),
        "badge": _text(data.get("badge"), "Etiket", max_len=24, required=False),
        "image": image,
        "active": bool(data.get("active", True)),
        "sort": _int(data.get("sort", 100), "Sıra", lo=0, hi=9999),
    }


def create_product(data: dict) -> dict:
    clean = _validate_product(data)
    with _lock:
        items = _read("products", [])
        base = slugify(clean["name"])
        pid, n = base, 2
        ids = {p["id"] for p in items}
        while pid in ids:
            pid, n = f"{base}-{n}", n + 1
        product = {"id": pid, **clean, "createdAt": now_iso()}
        _write("products", [*items, product])
    return product


def update_product(pid: str, data: dict) -> dict:
    clean = _validate_product(data)
    with _lock:
        items = _read("products", [])
        current = next((p for p in items if p["id"] == pid), None)
        if not current:
            raise NotFound(pid)
        updated = {**current, **clean, "updatedAt": now_iso()}
        _write("products", [updated if p["id"] == pid else p for p in items])
    return updated


def delete_product(pid: str) -> None:
    with _lock:
        items = _read("products", [])
        if not any(p["id"] == pid for p in items):
            raise NotFound(pid)
        _write("products", [p for p in items if p["id"] != pid])


# ---------- ayarlar ----------

DEFAULT_SETTINGS = {
    "shippingFee": 12000,          # kuruş
    "freeShippingMin": 150000,     # kuruş, 0 = kapalı
    "shopOpen": True,
    "bankInfo": "",
    "notice": "Siparişiniz WhatsApp üzerinden teyit edildikten sonra hazırlanır.",
}


def get_settings() -> dict:
    with _lock:
        return {**DEFAULT_SETTINGS, **_read("settings", {})}


def update_settings(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Geçersiz ayar verisi.")
    clean = {
        "shippingFee": _int(data.get("shippingFee", 0), "Kargo ücreti", lo=0, hi=1_000_000),
        "freeShippingMin": _int(data.get("freeShippingMin", 0), "Ücretsiz kargo limiti", lo=0, hi=100_000_000),
        "shopOpen": bool(data.get("shopOpen", True)),
        "bankInfo": _text(data.get("bankInfo"), "Havale bilgisi", max_len=400, required=False),
        "notice": _text(data.get("notice"), "Duyuru", max_len=300, required=False),
    }
    with _lock:
        _write("settings", clean)
    return clean


def public_settings() -> dict:
    s = get_settings()
    return {k: s[k] for k in ("shippingFee", "freeShippingMin", "shopOpen", "notice")} | {
        "hasBankInfo": bool(s["bankInfo"]),
    }


# ---------- siparişler ----------

def shipping_for(subtotal: int, settings: dict) -> int:
    free_min = settings["freeShippingMin"]
    if free_min and subtotal >= free_min:
        return 0
    return settings["shippingFee"]


def _validate_customer(c) -> dict:
    if not isinstance(c, dict):
        raise ValidationError("Müşteri bilgileri eksik.")
    return {
        "name": _text(c.get("name"), "Ad soyad", min_len=3, max_len=60),
        "phone": normalize_phone(c.get("phone")),
        "city": _text(c.get("city"), "İl / ilçe", min_len=2, max_len=60),
        "address": _text(c.get("address"), "Adres", min_len=10, max_len=300),
        "note": _text(c.get("note"), "Not", max_len=300, required=False),
    }


def _new_order_id(existing: set[str]) -> str:
    day = datetime.now(TR_TZ).strftime("%y%m%d")
    while True:
        oid = f"SAH-{day}-{secrets.randbelow(9000) + 1000}"
        if oid not in existing:
            return oid


def create_order(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Geçersiz sipariş.")
    if payload.get("consent") is not True:
        raise ValidationError("Kişisel verilerin işlenmesine onay vermelisiniz.")
    customer = _validate_customer(payload.get("customer"))
    payment = str(payload.get("payment", ""))
    if payment not in PAYMENT_METHODS:
        raise ValidationError("Ödeme yöntemi seçin.")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValidationError("Sepetiniz boş.")
    if len(raw_items) > MAX_ITEMS:
        raise ValidationError("Sepette çok fazla ürün var.")

    wanted: dict[str, int] = {}
    for it in raw_items:
        if not isinstance(it, dict):
            raise ValidationError("Sepet verisi geçersiz.")
        pid = str(it.get("id", ""))
        qty = _int(it.get("qty"), "Adet", lo=1, hi=MAX_QTY_PER_ITEM)
        wanted[pid] = wanted.get(pid, 0) + qty

    with _lock:
        settings = get_settings()
        if not settings["shopOpen"]:
            raise ValidationError("Kiler şu an sipariş almıyor.")
        products = {p["id"]: p for p in _read("products", [])}
        lines = []
        for pid, qty in wanted.items():
            p = products.get(pid)
            if not p or not p.get("active"):
                raise ValidationError("Sepetteki bir ürün artık satışta değil.")
            if qty > MAX_QTY_PER_ITEM:
                raise ValidationError(f"{p['name']} için en fazla {MAX_QTY_PER_ITEM} adet.")
            if p["stock"] < qty:
                raise ValidationError(f"{p['name']} için stokta {p['stock']} adet var.")
            lines.append({"id": pid, "name": p["name"], "size": p.get("size", ""),
                          "price": p["price"], "qty": qty, "total": p["price"] * qty})

        subtotal = sum(l["total"] for l in lines)
        shipping = shipping_for(subtotal, settings)
        orders = _read("orders", [])
        open_same_phone = sum(
            1 for o in orders if o["customer"]["phone"] == customer["phone"] and o["status"] == "yeni"
        )
        if open_same_phone >= MAX_OPEN_ORDERS_PER_PHONE:
            raise ValidationError("Bu numarayla bekleyen siparişleriniz var. Lütfen WhatsApp'tan bize ulaşın.")
        order = {
            "id": _new_order_id({o["id"] for o in orders}),
            "createdAt": now_iso(),
            "status": "yeni",
            "customer": customer,
            "payment": payment,
            "items": lines,
            "subtotal": subtotal,
            "shipping": shipping,
            "total": subtotal + shipping,
            "stockReturned": False,
            "history": [{"at": now_iso(), "status": "yeni"}],
        }
        new_products = [
            {**p, "stock": p["stock"] - wanted[p["id"]]} if p["id"] in wanted else p
            for p in _read("products", [])
        ]
        # Önce sipariş yazılır: stok yazımı başarısız olursa sipariş kaybolmaz, stok elle düzeltilebilir.
        _write("orders", [order, *orders])
        try:
            _write("products", new_products)
        except OSError:
            _write("orders", orders)
            raise
    return order


def list_orders() -> list[dict]:
    with _lock:
        return _read("orders", [])


def set_order_status(oid: str, status: str) -> dict:
    if status not in ORDER_STATUSES:
        raise ValidationError("Geçersiz durum.")
    with _lock:
        orders = _read("orders", [])
        order = next((o for o in orders if o["id"] == oid), None)
        if not order:
            raise NotFound(oid)
        if order["status"] == status:
            return order
        return_stock = status == "iptal" and not order["stockReturned"]
        take_stock = order["status"] == "iptal" and order["stockReturned"]
        updated = {
            **order,
            "status": status,
            "stockReturned": return_stock or (order["stockReturned"] and not take_stock),
            "history": [*order["history"], {"at": now_iso(), "status": status}],
        }
        if return_stock or take_stock:
            sign = 1 if return_stock else -1
            delta = {l["id"]: l["qty"] * sign for l in order["items"]}
            _write("products", [
                {**p, "stock": max(0, p["stock"] + delta[p["id"]])} if p["id"] in delta else p
                for p in _read("products", [])
            ])
        _write("orders", [updated if o["id"] == oid else o for o in orders])
    return updated


# ---------- menü ----------

MAX_MENU_SECTIONS = 12
MAX_MENU_ITEMS = 40

DEFAULT_MENU = {
    "serpme": {
        "price": 40000,
        "note": "Kişi başı · minimum 2 kişilik",
        "detail": "Menemen ve peynir tabağı sınırlıdır, diğer tüm ürünler sınırsızdır.",
    },
    "sections": [
        {"id": "gozleme", "title": "Gözleme", "items": [
            {"name": "Otlu peynirli", "price": 17500}, {"name": "Patatesli", "price": 17500},
            {"name": "Kaşarlı", "price": 17500}, {"name": "Lorlu", "price": 17500},
            {"name": "Patlıcanlı", "price": 20000}, {"name": "Kıymalı", "price": 22500},
            {"name": "Sucuklu", "price": 22500}, {"name": "Kavurmalı", "price": 22500},
            {"name": "Karışık", "price": 25000}, {"name": "Ekstra kaşar", "price": 2500, "addon": True},
        ]},
        {"id": "sicak", "title": "Sıcak Kahvaltılar", "items": [
            {"name": "Sucuklu yumurta", "price": 30000}, {"name": "Mıhlama", "price": 30000},
            {"name": "Kavurmalı yumurta", "price": 30000},
        ]},
        {"id": "ana", "title": "Ana Yemekler", "items": [
            {"name": "Saç kavurma", "price": 50000}, {"name": "Mantı", "price": 30000},
            {"name": "Sarma", "price": 30000},
        ]},
        {"id": "aperatif", "title": "Aperatifler", "items": [
            {"name": "Patates kızartması", "price": 20000}, {"name": "Karışık kızartma", "price": 25000},
            {"name": "Pişi porsiyon", "price": 20000},
        ]},
        {"id": "icecek", "title": "İçecekler", "items": [
            {"name": "Su", "price": 2500}, {"name": "Çay", "price": 2500},
            {"name": "Türk kahvesi", "price": 8000}, {"name": "Ayran", "price": 3500},
            {"name": "Maden suyu (sade)", "price": 3000}, {"name": "Maden suyu (meyveli)", "price": 4000},
            {"name": "Kola", "price": 8000}, {"name": "Fanta", "price": 8000},
            {"name": "Ice tea", "price": 8000}, {"name": "Gazoz", "price": 8000},
        ]},
    ],
}


def get_menu() -> dict:
    with _lock:
        return _read("menu", DEFAULT_MENU)


def update_menu(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Geçersiz menü verisi.")
    serpme = data.get("serpme")
    if not isinstance(serpme, dict):
        raise ValidationError("Serpme kahvaltı bilgisi eksik.")
    sections = data.get("sections")
    if not isinstance(sections, list) or len(sections) > MAX_MENU_SECTIONS:
        raise ValidationError(f"Menüde en fazla {MAX_MENU_SECTIONS} bölüm olabilir.")

    clean_sections = []
    for sec in sections:
        if not isinstance(sec, dict):
            raise ValidationError("Menü bölümü geçersiz.")
        title = _text(sec.get("title"), "Bölüm adı", max_len=40)
        items = sec.get("items")
        if not isinstance(items, list) or len(items) > MAX_MENU_ITEMS:
            raise ValidationError(f"“{title}” bölümünde en fazla {MAX_MENU_ITEMS} satır olabilir.")
        clean_items = [
            {"name": _text(it.get("name"), f"{title} satır adı", max_len=60),
             "price": _int(it.get("price"), f"{title} fiyatı", lo=0, hi=10_000_000),
             **({"addon": True} if it.get("addon") is True else {})}
            for it in items if isinstance(it, dict)
        ]
        clean_sections.append({"id": slugify(title), "title": title, "items": clean_items})

    clean = {
        "serpme": {
            "price": _int(serpme.get("price"), "Serpme kahvaltı fiyatı", lo=0, hi=10_000_000),
            "note": _text(serpme.get("note"), "Serpme notu", max_len=80, required=False),
            "detail": _text(serpme.get("detail"), "Serpme açıklaması", max_len=200, required=False),
        },
        "sections": clean_sections,
    }
    with _lock:
        _write("menu", clean)
    return clean
