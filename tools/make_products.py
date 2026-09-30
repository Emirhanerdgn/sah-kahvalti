"""Geçici ürün görsellerini (SVG) ve başlangıç ürün listesini üretir.

Kendi kavanoz fotoğraflarınız hazır olunca panelden yükleyin; bu dosyaya gerek kalmaz.
Çalıştırma: python tools/make_products.py  (mevcut data/products.json'u EZMEZ)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "products"
DATA = ROOT / "data" / "products.json"

INK = "#2b1d14"
KRAFT = "#e9d9bb"
RED = "#9e2b25"


def gingham(pid: str) -> str:
    return f"""<pattern id="g-{pid}" width="14" height="14" patternUnits="userSpaceOnUse">
      <rect width="14" height="14" fill="#fbf4ea"/>
      <rect width="7" height="14" fill="{RED}" opacity=".55"/>
      <rect width="14" height="7" fill="{RED}" opacity=".55"/>
    </pattern>"""


def label(cx: float, cy: float, r: float, title: str, sub: str) -> str:
    return f"""
  <g>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="{KRAFT}" stroke="{INK}" stroke-width="2"/>
    <circle cx="{cx}" cy="{cy}" r="{r - 7}" fill="none" stroke="{INK}" stroke-width=".8" stroke-dasharray="2 3"/>
    <circle cx="{cx}" cy="{cy - r * .42}" r="{r * .22}" fill="{RED}"/>
    <text x="{cx}" y="{cy - r * .42 + r * .09}" text-anchor="middle" font-family="Georgia, serif" font-style="italic" font-size="{r * .26}" fill="#fbf4ea">Ş</text>
    <text x="{cx}" y="{cy + r * .1}" text-anchor="middle" font-family="Georgia, serif" font-size="{r * .15}" letter-spacing="3" fill="{INK}">ŞAH KİLER</text>
    <text x="{cx}" y="{cy + r * .38}" text-anchor="middle" font-family="Georgia, serif" font-style="italic" font-size="{r * .24}" fill="{RED}">{title}</text>
    <text x="{cx}" y="{cy + r * .6}" text-anchor="middle" font-family="Georgia, serif" font-size="{r * .12}" letter-spacing="1.5" fill="{INK}">{sub}</text>
  </g>"""


def backdrop(accent: str) -> str:
    return f"""<rect width="400" height="480" fill="#f3eadb"/>
  <circle cx="200" cy="250" r="165" fill="{accent}" opacity=".13"/>
  <ellipse cx="200" cy="432" rx="120" ry="14" fill="{INK}" opacity=".13"/>"""


def jar(pid, fill, accent, title, sub, dots=None):
    extra = ""
    if dots:
        extra = "".join(
            f'<circle cx="{x}" cy="{y}" r="11" fill="{dots}" opacity=".9"/>'
            for x, y in [(135, 380), (160, 400), (190, 385), (225, 402), (255, 380), (275, 400), (145, 205), (262, 215)]
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 480">
  <defs>{gingham(pid)}
    <linearGradient id="gl-{pid}" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".25" stop-color="#fff" stop-opacity="0"/><stop offset=".85" stop-color="#000" stop-opacity=".12"/></linearGradient>
  </defs>
  {backdrop(accent)}
  <rect x="110" y="150" width="180" height="280" rx="34" fill="{fill}"/>
  {extra}
  <rect x="110" y="150" width="180" height="280" rx="34" fill="url(#gl-{pid})" stroke="{INK}" stroke-opacity=".25" stroke-width="2"/>
  <rect x="126" y="126" width="148" height="34" rx="8" fill="#d8c9ad" stroke="{INK}" stroke-opacity=".3"/>
  <path d="M92 132 Q200 58 308 132 L298 150 Q200 118 102 150 Z" fill="url(#g-{pid})" stroke="{INK}" stroke-opacity=".35" stroke-width="1.5"/>
  <path d="M104 146 Q200 124 296 146" fill="none" stroke="#b08a4a" stroke-width="3"/>
  {label(200, 300, 74, title, sub)}
</svg>"""


def bottle(pid, fill, accent, title, sub):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 480">
  <defs><linearGradient id="gl-{pid}" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity=".3"/><stop offset=".3" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".2"/></linearGradient></defs>
  {backdrop(accent)}
  <path d="M175 40 h50 v70 q0 30 40 60 q20 16 20 50 v200 q0 14 -14 14 h-142 q-14 0 -14 -14 v-200 q0 -34 20 -50 q40 -30 40 -60 z" fill="{fill}"/>
  <path d="M175 40 h50 v70 q0 30 40 60 q20 16 20 50 v200 q0 14 -14 14 h-142 q-14 0 -14 -14 v-200 q0 -34 20 -50 q40 -30 40 -60 z" fill="url(#gl-{pid})" stroke="{INK}" stroke-opacity=".3" stroke-width="2"/>
  <rect x="170" y="26" width="60" height="30" rx="6" fill="{RED}" stroke="{INK}" stroke-opacity=".3"/>
  {label(200, 318, 70, title, sub)}
</svg>"""


def tin(pid, fill, accent, title, sub):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 480">
  {backdrop(accent)}
  <rect x="95" y="110" width="210" height="320" rx="10" fill="{fill}" stroke="{INK}" stroke-opacity=".35" stroke-width="2"/>
  <rect x="95" y="110" width="210" height="26" fill="#000" opacity=".08"/>
  <rect x="95" y="404" width="210" height="26" fill="#000" opacity=".08"/>
  <rect x="236" y="84" width="44" height="30" rx="5" fill="#c9b38a" stroke="{INK}" stroke-opacity=".4"/>
  <path d="M140 100 Q200 60 260 100" fill="none" stroke="{INK}" stroke-opacity=".5" stroke-width="5"/>
  {label(200, 270, 78, title, sub)}
</svg>"""


def crock(pid, fill, accent, title, sub):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 480">
  <defs>{gingham(pid)}</defs>
  {backdrop(accent)}
  <path d="M120 170 q-30 60 -20 160 q10 90 100 100 q90 -10 100 -100 q10 -100 -20 -160 z" fill="{fill}" stroke="{INK}" stroke-opacity=".35" stroke-width="2"/>
  <path d="M100 170 q100 -70 200 0 q-10 16 -20 18 q-80 -40 -160 0 q-10 -2 -20 -18z" fill="url(#g-{pid})" stroke="{INK}" stroke-opacity=".4"/>
  <path d="M118 184 q82 -22 164 0" fill="none" stroke="#b08a4a" stroke-width="4"/>
  {label(200, 305, 72, title, sub)}
</svg>"""


def wheel(pid, fill, accent, title, sub):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 480">
  {backdrop(accent)}
  <ellipse cx="200" cy="360" rx="150" ry="58" fill="#e8d9b5" stroke="{INK}" stroke-opacity=".3" stroke-width="2"/>
  <rect x="50" y="250" width="300" height="110" fill="{fill}"/>
  <ellipse cx="200" cy="250" rx="150" ry="58" fill="#fbf3dc" stroke="{INK}" stroke-opacity=".3" stroke-width="2"/>
  <path d="M50 250 v110 M350 250 v110" stroke="{INK}" stroke-opacity=".3" stroke-width="2"/>
  <path d="M200 250 L350 250 A150 58 0 0 1 280 300 Z" fill="#f4e6bf"/>
  {label(200, 150, 70, title, sub)}
</svg>"""


PRODUCTS = [
    # id, shape, fill, accent, label title, label sub, name, category, size, price(kuruş), badge, desc, extra
    ("sizma-zeytinyagi-1l", bottle, "#5b6b1f", "#7a8b2a", "Zeytinyağı", "SIZMA · 1 L",
     "Soğuk Sıkım Sızma Zeytinyağı", "zeytinyagi", "1 L", 65000, "Yeni hasat",
     "Ege zeytinlerinden soğuk sıkım, filtresiz sızma zeytinyağı. Kahvaltının ve salatanın olmazsa olmazı.", None),
    ("zeytinyagi-teneke-5l", tin, "#6e7c2b", "#7a8b2a", "Zeytinyağı", "TENEKE · 5 L",
     "Sızma Zeytinyağı Teneke", "zeytinyagi", "5 L", 290000, "Aile boyu",
     "Kışlık ihtiyacınız için 5 litrelik tenekede sızma zeytinyağı.", None),
    ("cilek-receli", jar, "#b3262a", "#b3262a", "Çilek", "ORGANİK REÇEL",
     "Organik Çilek Reçeli", "recel", "380 g", 22000, "Organik",
     "Bahçemizden toplanan çileklerle, bakır kazanda ağır ateşte kaynatılır. Katkısız.", None),
    ("visne-receli", jar, "#6e1424", "#6e1424", "Vişne", "ORGANİK REÇEL",
     "Organik Vişne Reçeli", "recel", "380 g", 22000, "Organik",
     "Mayhoş vişneler, bol meyve, az şeker. Seyhan Bacı'nın sabah sofralarından.", None),
    ("kayisi-receli", jar, "#e08a1e", "#e08a1e", "Kayısı", "EV YAPIMI REÇEL",
     "Kayısı Reçeli", "recel", "380 g", 21000, "",
     "İri kayısı dilimleri, parlak ve kıvamlı. Tereyağıyla bir dilim ekmek yeter.", None),
    ("incir-receli", jar, "#7a3d2a", "#7a3d2a", "İncir", "EV YAPIMI REÇEL",
     "İncir Reçeli", "recel", "380 g", 23000, "",
     "Bütün incirlerle, ceviz eşliğinde de nefis.", None),
    ("kivi-receli", jar, "#7a8f2a", "#7a8f2a", "Kivi", "EL YAPIMI REÇEL",
     "El Yapımı Kivi Reçeli", "recel", "380 g", 24000, "Sadece bizde",
     "Mahallenin kivilerinden, sadece bizde bulabileceğiniz el yapımı reçel.", None),
    ("gemlik-siyah-zeytin", jar, "#3a2a2a", "#3a2a2a", "Siyah Zeytin", "GEMLİK · 1 KG",
     "Gemlik Siyah Zeytin", "zeytin", "1 kg", 38000, "",
     "Salamura, az tuzlu, yağlı Gemlik tipi siyah zeytin.", "#1b1414"),
    ("kirma-yesil-zeytin", jar, "#9aa451", "#7a8b2a", "Kırma Zeytin", "YEŞİL · 1 KG",
     "Kırma Yeşil Zeytin", "zeytin", "1 kg", 34000, "",
     "Limon ve kekikle çeşnilenmiş kırma yeşil zeytin.", "#5f6b22"),
    ("koy-tereyagi", crock, "#f1d27a", "#e0b94a", "Tereyağı", "KÖY · 500 G",
     "Köy Tereyağı", "tereyagi", "500 g", 45000, "Taze",
     "Yayık tereyağı; gözlemenin üstüne, menemenin içine.", None),
    ("ezine-peyniri", tin, "#d9d3c2", "#b8ad8e", "Ezine Peyniri", "TAM YAĞLI · 1 KG",
     "Ezine Beyaz Peynir", "peynir", "1 kg", 52000, "",
     "Keçi, koyun ve inek sütünden, olgunlaştırılmış tam yağlı beyaz peynir.", None),
    ("koy-kasari", wheel, "#e2c26a", "#e0b94a", "Köy Kaşarı", "TAZE · 500 G",
     "Taze Köy Kaşarı", "peynir", "500 g", 39000, "",
     "Sofradaki meşhur eriyen kaşarın ta kendisi; tavada eritip ekmekle servis edin.", None),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    seed = []
    for i, (pid, shape, fill, accent, title, sub, name, cat, size, price, badge, desc, dots) in enumerate(PRODUCTS):
        svg = shape(pid, fill, accent, title, sub, dots) if shape is jar else shape(pid, fill, accent, title, sub)
        (OUT / f"{pid}.svg").write_text(svg, encoding="utf-8")
        seed.append({"id": pid, "name": name, "category": cat, "description": desc, "size": size,
                     "price": price, "stock": 20, "badge": badge, "image": f"assets/products/{pid}.svg",
                     "active": True, "sort": (i + 1) * 10})
    if DATA.exists():
        print(f"{DATA} zaten var, ürün listesi değiştirilmedi. SVG'ler güncellendi.")
        return
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(seed)} ürün yazıldı.")


if __name__ == "__main__":
    main()
