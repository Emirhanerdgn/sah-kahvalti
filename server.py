"""Şah Kahvaltı — site + Kiler mağaza API'si + yönetim paneli sunucusu.

Çalıştırma:  python server.py   (varsayılan port 8966)
Gerekli:     .env içinde SAH_ADMIN_PASSWORD (en az 10 karakter)
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import re
import secrets
import sys
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import store

ROOT = Path(__file__).parent.resolve()
UPLOAD_DIR = ROOT / "assets" / "uploads"
SESSION_TTL = 12 * 3600
MAX_JSON_BYTES = 64 * 1024
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
LOGIN_LIMIT = (5, 15 * 60)       # 15 dakikada 5 hatalı deneme
ORDER_LIMIT = (8, 60 * 60)       # saatte 8 sipariş / IP
# Sadece bu klasörler ve kökteki bu uzantılar sunulur (izin listesi; küçük harfe çevrilerek karşılaştırılır).
PUBLIC_DIRS = {"css", "js", "assets", "panel"}
PUBLIC_EXTS = {".html", ".css", ".js", ".svg", ".jpg", ".jpeg", ".png", ".webp", ".ico", ".woff2"}
REQUEST_TIMEOUT = 15

CSP = (
    "default-src 'self'; img-src 'self' data:; script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; frame-src https://www.google.com; "
    "connect-src 'self'; base-uri 'self'; form-action 'self'; object-src 'none'"
)
IMAGE_MAGIC = {b"\xff\xd8\xff": "jpg", b"\x89PNG": "png"}


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


class RateLimiter:
    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.hits: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def blocked(self, key: str) -> bool:
        now = time.time()
        with self.lock:
            recent = [t for t in self.hits.get(key, []) if now - t < self.window]
            self.hits[key] = recent
            return len(recent) >= self.limit

    def hit(self, key: str) -> None:
        with self.lock:
            self.hits.setdefault(key, []).append(time.time())


class Sessions:
    def __init__(self):
        self.tokens: dict[str, float] = {}
        self.lock = threading.Lock()

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.tokens[token] = time.time() + SESSION_TTL
        return token

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        with self.lock:
            exp = self.tokens.get(token)
            if exp and exp > time.time():
                return True
            self.tokens.pop(token, None)
            return False

    def drop(self, token: str | None) -> None:
        with self.lock:
            self.tokens.pop(token or "", None)


SESSIONS = Sessions()
LOGIN_RL = RateLimiter(*LOGIN_LIMIT)
ORDER_RL = RateLimiter(*ORDER_LIMIT)


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


class Handler(BaseHTTPRequestHandler):
    server_version = "Sah/1.0"
    sys_version = ""
    timeout = REQUEST_TIMEOUT

    # ---------- ortak ----------

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CSP)
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}\n")

    @property
    def client_ip(self) -> str:
        if os.environ.get("SAH_TRUSTED_PROXY") == "1":
            real = self.headers.get("X-Real-IP", "").strip()
            forwarded = [h.strip() for h in self.headers.get("X-Forwarded-For", "").split(",") if h.strip()]
            if real:
                return real
            if forwarded:
                return forwarded[-1]  # vekilin eklediği son değer; istemcinin yazdıkları öncesinde kalır
        return self.client_address[0]

    def send_json(self, status: int, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def ok(self, data=None, status=200, headers=None):
        self.send_json(status, {"success": True, "data": data, "error": None}, headers)

    def read_body(self, limit: int) -> bytes:
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError(400, "Geçersiz istek.") from None
        if n <= 0:
            raise ApiError(400, "İstek gövdesi boş.")
        if n > limit:
            raise ApiError(413, "İstek çok büyük.")
        return self.rfile.read(n)

    def read_json(self):
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ApiError(415, "JSON bekleniyor.")
        try:
            return json.loads(self.read_body(MAX_JSON_BYTES))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "JSON okunamadı.") from None

    def session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        return cookie["sah_session"].value if "sah_session" in cookie else None

    def require_admin(self, mutating: bool):
        if not SESSIONS.valid(self.session_token()):
            raise ApiError(401, "Oturum açmanız gerekiyor.")
        # Özel başlık: başka sitelerden gelen form/CSRF isteklerini engeller.
        if mutating and self.headers.get("X-Sah-Panel") != "1":
            raise ApiError(403, "İzin verilmeyen istek.")

    # ---------- yönlendirme ----------

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_PATCH(self):
        self.dispatch("PATCH")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def dispatch(self, method: str):
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/"):
                self.route_api(method, path)
            elif method == "GET":
                self.serve_static(path)
            else:
                raise ApiError(405, "Yönteme izin verilmiyor.")
        except ApiError as e:
            self.send_json(e.status, {"success": False, "data": None, "error": e.message})
        except store.ValidationError as e:
            self.send_json(422, {"success": False, "data": None, "error": str(e)})
        except store.NotFound:
            self.send_json(404, {"success": False, "data": None, "error": "Kayıt bulunamadı."})
        except Exception as e:  # noqa: BLE001 — beklenmeyen hatayı logla, ayrıntıyı sızdırma
            self.log_error("Beklenmeyen hata: %r", e)
            self.send_json(500, {"success": False, "data": None, "error": "Sunucu hatası."})

    def route_api(self, method: str, path: str):
        m = re.fullmatch(r"/api/admin/(products|orders)/([A-Za-z0-9-]{1,64})", path)
        routes = {
            ("GET", "/api/shop"): self.api_shop,
            ("GET", "/api/menu"): self.api_menu,
            ("GET", "/api/admin/menu"): self.api_admin_menu,
            ("PUT", "/api/admin/menu"): self.api_put_menu,
            ("POST", "/api/orders"): self.api_create_order,
            ("POST", "/api/admin/login"): self.api_login,
            ("POST", "/api/admin/logout"): self.api_logout,
            ("GET", "/api/admin/me"): self.api_me,
            ("GET", "/api/admin/products"): self.api_admin_products,
            ("POST", "/api/admin/products"): self.api_create_product,
            ("GET", "/api/admin/orders"): self.api_admin_orders,
            ("GET", "/api/admin/settings"): self.api_get_settings,
            ("PUT", "/api/admin/settings"): self.api_put_settings,
            ("POST", "/api/admin/upload"): self.api_upload,
        }
        handler = routes.get((method, path))
        if handler:
            return handler()
        if m and m.group(1) == "products" and method in ("PUT", "DELETE"):
            return self.api_product_item(method, m.group(2))
        if m and m.group(1) == "orders" and method == "PATCH":
            return self.api_order_status(m.group(2))
        raise ApiError(404, "Bulunamadı.")

    # ---------- genel API ----------

    def api_shop(self):
        fields = ("id", "name", "category", "description", "size", "price", "badge", "image")
        products = [
            {**{k: p.get(k) for k in fields}, "inStock": p["stock"] > 0, "maxQty": min(p["stock"], store.MAX_QTY_PER_ITEM)}
            for p in store.list_products()
        ]
        self.ok({"products": products, "categories": store.CATEGORIES,
                 "payments": store.PAYMENT_METHODS, "settings": store.public_settings()})

    def api_menu(self):
        self.ok(store.get_menu())

    def api_admin_menu(self):
        self.require_admin(mutating=False)
        self.ok(store.get_menu())

    def api_put_menu(self):
        self.require_admin(mutating=True)
        self.ok(store.update_menu(self.read_json()))

    def api_create_order(self):
        if ORDER_RL.blocked(self.client_ip):
            raise ApiError(429, "Çok fazla sipariş denemesi. Lütfen daha sonra tekrar deneyin.")
        order = store.create_order(self.read_json())
        ORDER_RL.hit(self.client_ip)
        settings = store.get_settings()
        self.ok({
            "id": order["id"], "total": order["total"], "shipping": order["shipping"],
            "payment": order["payment"], "items": order["items"],
            "bankInfo": settings["bankInfo"] if order["payment"] == "havale" else "",
        }, status=201)

    # ---------- oturum ----------

    def api_login(self):
        if LOGIN_RL.blocked(self.client_ip):
            raise ApiError(429, "Çok fazla hatalı deneme. 15 dakika sonra tekrar deneyin.")
        data = self.read_json()
        given = str(data.get("password", "")) if isinstance(data, dict) else ""
        expected = os.environ.get("SAH_ADMIN_PASSWORD", "")
        if not hmac.compare_digest(given.encode(), expected.encode()):
            LOGIN_RL.hit(self.client_ip)
            raise ApiError(401, "Şifre hatalı.")
        token = SESSIONS.create()
        cookie = f"sah_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_TTL}"
        if secure_cookies():
            cookie += "; Secure"
        self.ok({"ok": True}, headers=[("Set-Cookie", cookie)])

    def api_logout(self):
        SESSIONS.drop(self.session_token())
        self.ok({"ok": True}, headers=[("Set-Cookie", "sah_session=; Path=/; Max-Age=0; SameSite=Strict; HttpOnly")])

    def api_me(self):
        self.require_admin(mutating=False)
        self.ok({"ok": True, "categories": store.CATEGORIES, "statuses": store.ORDER_STATUSES,
                 "payments": store.PAYMENT_METHODS})

    # ---------- yönetim ----------

    def api_admin_products(self):
        self.require_admin(mutating=False)
        self.ok(store.list_products(include_inactive=True))

    def api_create_product(self):
        self.require_admin(mutating=True)
        self.ok(store.create_product(self.read_json()), status=201)

    def api_product_item(self, method: str, pid: str):
        self.require_admin(mutating=True)
        if method == "PUT":
            return self.ok(store.update_product(pid, self.read_json()))
        store.delete_product(pid)
        self.ok({"deleted": pid})

    def api_admin_orders(self):
        self.require_admin(mutating=False)
        self.ok(store.list_orders())

    def api_order_status(self, oid: str):
        self.require_admin(mutating=True)
        data = self.read_json()
        self.ok(store.set_order_status(oid, str(data.get("status", "")) if isinstance(data, dict) else ""))

    def api_get_settings(self):
        self.require_admin(mutating=False)
        self.ok(store.get_settings())

    def api_put_settings(self):
        self.require_admin(mutating=True)
        self.ok(store.update_settings(self.read_json()))

    def api_upload(self):
        self.require_admin(mutating=True)
        data = self.read_body(MAX_UPLOAD_BYTES)
        ext = next((e for magic, e in IMAGE_MAGIC.items() if data.startswith(magic)), None)
        if not ext and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            ext = "webp"
        if not ext:
            raise ApiError(415, "Sadece JPG, PNG veya WEBP yükleyebilirsiniz.")
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        name = f"{secrets.token_hex(8)}.{ext}"
        (UPLOAD_DIR / name).write_bytes(data)
        self.ok({"path": f"assets/uploads/{name}"}, status=201)

    # ---------- statik dosyalar ----------

    def serve_static(self, path: str):
        rel = unquote(path).lstrip("/")
        if rel == "panel":
            self.send_response(301)
            self.send_header("Location", "/panel/")
            self.end_headers()
            return
        if rel == "" or rel.endswith("/"):
            rel += "index.html"
        if "\\" in rel or "\x00" in rel:
            raise ApiError(404, "Bulunamadı.")
        target = (ROOT / rel).resolve()
        if ROOT not in target.parents or not target.is_file():
            raise ApiError(404, "Bulunamadı.")
        parts = target.relative_to(ROOT).as_posix().lower().split("/")
        is_public = (len(parts) == 1 and (parts[0].endswith(".html") or parts[0] == "favicon.ico")) or parts[0] in PUBLIC_DIRS
        if (not is_public or any(p.startswith(".") for p in parts)
                or target.suffix.lower() not in PUBLIC_EXTS):
            raise ApiError(404, "Bulunamadı.")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        cache = "no-cache" if target.suffix in (".html", ".js", ".css") else "public, max-age=604800"
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)


def secure_cookies() -> bool:
    """Yerel (127.0.0.1/localhost) dışında çerezler varsayılan olarak Secure olur."""
    flag = os.environ.get("SAH_SECURE_COOKIE")
    if flag in ("0", "1"):
        return flag == "1"
    return os.environ.get("HOST", "127.0.0.1") not in ("127.0.0.1", "localhost", "::1")


def main():
    load_env()
    password = os.environ.get("SAH_ADMIN_PASSWORD", "")
    if len(password) < 10:
        sys.exit("HATA: .env dosyasında en az 10 karakterlik SAH_ADMIN_PASSWORD tanımlayın (.env.example'a bakın).")
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("image/webp", ".webp")
    port = int(os.environ.get("PORT", "8966"))
    host = os.environ.get("HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Şah Kahvaltı sunucusu: http://{host}:{port}  (panel: /panel/)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
