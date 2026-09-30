import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import store  # noqa: E402

PRODUCT = {"name": "Çilek Reçeli", "category": "recel", "price": 22000, "stock": 5,
           "size": "380 g", "image": "assets/products/cilek-receli.svg"}
CUSTOMER = {"name": "Ayşe Yılmaz", "phone": "0532 123 45 67", "city": "Buca / İzmir",
            "address": "Atatürk Cad. No:1 Daire 2"}


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig = store.DATA_DIR
        store.DATA_DIR = Path(self.tmp.name)
        self.product = store.create_product(PRODUCT)

    def tearDown(self):
        store.DATA_DIR = self._orig
        self.tmp.cleanup()

    def order(self, qty=2, **overrides):
        payload = {"customer": CUSTOMER, "items": [{"id": self.product["id"], "qty": qty}],
                   "payment": "kapida", "consent": True, **overrides}
        return store.create_order(payload)

    def stock(self):
        return store.list_products(include_inactive=True)[0]["stock"]


class ProductTests(StoreTestCase):
    def test_creates_slug_id_and_unique_suffix(self):
        second = store.create_product(PRODUCT)
        self.assertEqual(self.product["id"], "cilek-receli")
        self.assertEqual(second["id"], "cilek-receli-2")

    def test_rejects_unknown_category(self):
        with self.assertRaises(store.ValidationError):
            store.create_product({**PRODUCT, "category": "elektronik"})

    def test_rejects_fractional_price(self):
        with self.assertRaises(store.ValidationError):
            store.create_product({**PRODUCT, "price": 199.5})

    def test_rejects_image_path_outside_assets(self):
        with self.assertRaises(store.ValidationError):
            store.create_product({**PRODUCT, "image": "../server.py"})

    def test_inactive_products_hidden_from_shop(self):
        store.update_product(self.product["id"], {**PRODUCT, "active": False})
        self.assertEqual(store.list_products(), [])
        self.assertEqual(len(store.list_products(include_inactive=True)), 1)

    def test_update_unknown_product_raises_key_error(self):
        with self.assertRaises(store.NotFound):
            store.update_product("yok", PRODUCT)


class OrderTests(StoreTestCase):
    def test_order_uses_server_price_and_decrements_stock(self):
        order = self.order(qty=2, items=[{"id": self.product["id"], "qty": 2, "price": 1}])
        self.assertEqual(order["subtotal"], 44000)
        self.assertEqual(order["total"], 44000 + store.DEFAULT_SETTINGS["shippingFee"])
        self.assertEqual(self.stock(), 3)
        self.assertEqual(order["customer"]["phone"], "05321234567")

    def test_free_shipping_above_limit(self):
        store.update_settings({**store.DEFAULT_SETTINGS, "freeShippingMin": 40000})
        self.assertEqual(self.order(qty=2)["shipping"], 0)

    def test_rejects_quantity_over_stock(self):
        with self.assertRaisesRegex(store.ValidationError, "stokta 5"):
            self.order(qty=6)
        self.assertEqual(self.stock(), 5)

    def test_merges_duplicate_lines_before_stock_check(self):
        items = [{"id": self.product["id"], "qty": 3}, {"id": self.product["id"], "qty": 3}]
        with self.assertRaises(store.ValidationError):
            self.order(items=items)

    def test_limits_open_orders_per_phone(self):
        store.update_product(self.product["id"], {**PRODUCT, "stock": 50})
        for _ in range(store.MAX_OPEN_ORDERS_PER_PHONE):
            self.order(qty=1)
        with self.assertRaisesRegex(store.ValidationError, "bekleyen"):
            self.order(qty=1)

    def test_rejects_quantity_above_per_item_cap(self):
        store.update_product(self.product["id"], {**PRODUCT, "stock": 100})
        with self.assertRaises(store.ValidationError):
            self.order(qty=store.MAX_QTY_PER_ITEM + 1)

    def test_requires_consent(self):
        with self.assertRaises(store.ValidationError):
            self.order(consent=False)

    def test_rejects_invalid_phone(self):
        with self.assertRaisesRegex(store.ValidationError, "telefon"):
            self.order(customer={**CUSTOMER, "phone": "12345"})

    def test_rejects_when_shop_closed(self):
        store.update_settings({**store.DEFAULT_SETTINGS, "shopOpen": False})
        with self.assertRaisesRegex(store.ValidationError, "sipariş almıyor"):
            self.order()

    def test_cancel_returns_stock_once_and_reopen_takes_it_back(self):
        order = self.order(qty=2)
        store.set_order_status(order["id"], "iptal")
        store.set_order_status(order["id"], "iptal")
        self.assertEqual(self.stock(), 5)
        store.set_order_status(order["id"], "onaylandi")
        self.assertEqual(self.stock(), 3)

    def test_status_history_is_recorded(self):
        order = self.order()
        updated = store.set_order_status(order["id"], "kargoda")
        self.assertEqual([h["status"] for h in updated["history"]], ["yeni", "kargoda"])

    def test_rejects_unknown_status(self):
        order = self.order()
        with self.assertRaises(store.ValidationError):
            store.set_order_status(order["id"], "kayip")

    def test_orders_persist_as_json(self):
        order = self.order()
        saved = json.loads((store.DATA_DIR / "orders.json").read_text(encoding="utf-8"))
        self.assertEqual(saved[0]["id"], order["id"])


class MenuTests(StoreTestCase):
    def test_default_menu_matches_printed_menu(self):
        menu = store.get_menu()
        self.assertEqual(menu["serpme"]["price"], 40000)
        gozleme = next(s for s in menu["sections"] if s["id"] == "gozleme")
        self.assertEqual(gozleme["items"][0], {"name": "Otlu peynirli", "price": 17500})

    def test_update_menu_roundtrip_and_slug_ids(self):
        saved = store.update_menu({"serpme": {"price": 45000, "note": "Kişi başı"},
                                   "sections": [{"title": "Sıcak İçecekler", "items": [
                                       {"name": "Çay", "price": 3000}, {"name": "Ekstra kaşar", "price": 2500, "addon": True}]}]})
        self.assertEqual(saved["sections"][0]["id"], "sicak-icecekler")
        self.assertTrue(saved["sections"][0]["items"][1]["addon"])
        self.assertNotIn("addon", saved["sections"][0]["items"][0])
        self.assertEqual(store.get_menu(), saved)

    def test_update_menu_rejects_bad_price(self):
        with self.assertRaises(store.ValidationError):
            store.update_menu({"serpme": {"price": 40000}, "sections": [{"title": "X", "items": [{"name": "Su", "price": "abc"}]}]})

    def test_update_menu_rejects_too_many_sections(self):
        sections = [{"title": f"B{i}", "items": []} for i in range(store.MAX_MENU_SECTIONS + 1)]
        with self.assertRaises(store.ValidationError):
            store.update_menu({"serpme": {"price": 1}, "sections": sections})


class HelperTests(unittest.TestCase):
    def test_normalize_phone_variants(self):
        for raw in ("05321234567", "+90 532 123 45 67", "532-123-4567"):
            self.assertEqual(store.normalize_phone(raw), "05321234567")

    def test_slugify_turkish(self):
        self.assertEqual(store.slugify("Köy Tereyağı Şişe"), "koy-tereyagi-sise")


if __name__ == "__main__":
    unittest.main()
