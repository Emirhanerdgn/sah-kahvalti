"""HTTP seviyesinde entegrasyon testleri: statik izin listesi, oturum, CSRF başlığı, sipariş."""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server  # noqa: E402
import store  # noqa: E402

PASSWORD = "test-sifre-123456"


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SAH_ADMIN_PASSWORD"] = PASSWORD
        cls.tmp = tempfile.TemporaryDirectory()
        cls._orig = store.DATA_DIR
        store.DATA_DIR = Path(cls.tmp.name)
        store.create_product({"name": "Kivi Reçeli", "category": "recel", "price": 24000, "stock": 5,
                              "image": "assets/products/kivi-receli.svg"})
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.DATA_DIR = cls._orig
        cls.tmp.cleanup()

    def setUp(self):
        server.LOGIN_RL.hits.clear()
        server.ORDER_RL.hits.clear()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode() if body is not None else None
        hdrs = {"Content-Type": "application/json"} if body is not None else {}
        hdrs.update(headers or {})
        conn.request(method, path, body=payload, headers=hdrs)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res, data

    def login(self):
        res, _ = self.request("POST", "/api/admin/login", {"password": PASSWORD})
        self.assertEqual(res.status, 200)
        return res.getheader("Set-Cookie").split(";")[0]


class StaticFileTests(ServerTestCase):
    def test_serves_public_files(self):
        for path in ("/", "/css/style.css", "/js/shop.js", "/panel/", "/assets/products/kivi-receli.svg"):
            res, _ = self.request("GET", path)
            self.assertEqual(res.status, 200, path)

    def test_blocks_private_files_in_any_case(self):
        for path in ("/data/orders.json", "/Data/orders.json", "/DATA/products.json", "/server.py",
                     "/Server.PY", "/store.py", "/README.MD", "/.env", "/.ENV", "/tests/test_store.py",
                     "/tools/make_products.py", "/data%5corders.json", "/..%2fserver.py", "/css/../server.py"):
            res, _ = self.request("GET", path)
            self.assertEqual(res.status, 404, path)

    def test_security_headers_present(self):
        res, _ = self.request("GET", "/")
        self.assertEqual(res.getheader("X-Content-Type-Options"), "nosniff")
        self.assertIn("default-src 'self'", res.getheader("Content-Security-Policy"))

    def test_video_supports_range_requests(self):
        res, data = self.request("GET", "/assets/video/hero-960.mp4", headers={"Range": "bytes=0-99"})
        self.assertEqual(res.status, 206)
        self.assertEqual(len(data), 100)
        self.assertTrue(res.getheader("Content-Range").startswith("bytes 0-99/"))
        res, _ = self.request("GET", "/assets/video/hero-960.mp4", headers={"Range": "bytes=999999999-"})
        self.assertEqual(res.status, 416)

    def test_static_snapshot_json_is_public_but_data_dir_is_not(self):
        self.assertEqual(self.request("GET", "/assets/data/menu.json")[0].status, 200)
        self.assertEqual(self.request("GET", "/data/menu.json")[0].status, 404)

    def test_panel_without_slash_redirects(self):
        res, _ = self.request("GET", "/panel")
        self.assertEqual((res.status, res.getheader("Location")), (301, "/panel/"))


class AdminApiTests(ServerTestCase):
    def test_admin_requires_session(self):
        res, _ = self.request("GET", "/api/admin/orders")
        self.assertEqual(res.status, 401)

    def test_wrong_password_rejected_and_rate_limited(self):
        for _ in range(server.LOGIN_LIMIT[0]):
            res, _ = self.request("POST", "/api/admin/login", {"password": "yanlis"})
            self.assertEqual(res.status, 401)
        res, _ = self.request("POST", "/api/admin/login", {"password": PASSWORD})
        self.assertEqual(res.status, 429)

    def test_session_cookie_is_httponly_strict(self):
        res, _ = self.request("POST", "/api/admin/login", {"password": PASSWORD})
        cookie = res.getheader("Set-Cookie")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)

    def test_mutation_without_panel_header_is_forbidden(self):
        cookie = self.login()
        res, _ = self.request("PUT", "/api/admin/settings", {"shippingFee": 0}, {"Cookie": cookie})
        self.assertEqual(res.status, 403)

    def test_upload_rejects_non_image(self):
        cookie = self.login()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/admin/upload", body=b"<svg onload=alert(1)>",
                     headers={"Cookie": cookie, "X-Sah-Panel": "1", "Content-Type": "image/svg+xml"})
        self.assertEqual(conn.getresponse().status, 415)
        conn.close()


class OrderApiTests(ServerTestCase):
    def test_public_shop_hides_stock_numbers(self):
        _, data = self.request("GET", "/api/shop")
        product = json.loads(data)["data"]["products"][0]
        self.assertNotIn("stock", product)
        self.assertTrue(product["inStock"])

    def test_order_roundtrip(self):
        pid = json.loads(self.request("GET", "/api/shop")[1])["data"]["products"][0]["id"]
        body = {"customer": {"name": "Deneme Kişi", "phone": "05320000001", "city": "Buca",
                             "address": "Deneme Sokak No:1 Daire 2"},
                "items": [{"id": pid, "qty": 1}], "payment": "kapida", "consent": True}
        res, data = self.request("POST", "/api/orders", body)
        self.assertEqual(res.status, 201, data)
        self.assertTrue(json.loads(data)["data"]["id"].startswith("SAH-"))

    def test_public_menu_and_admin_menu_requires_session(self):
        res, data = self.request("GET", "/api/menu")
        self.assertEqual(res.status, 200)
        self.assertIn("serpme", json.loads(data)["data"])
        res, _ = self.request("PUT", "/api/admin/menu", {"serpme": {"price": 1}, "sections": []})
        self.assertEqual(res.status, 401)

    def test_invalid_json_returns_400(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/orders", body=b"{bozuk", headers={"Content-Type": "application/json"})
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()


if __name__ == "__main__":
    unittest.main()
