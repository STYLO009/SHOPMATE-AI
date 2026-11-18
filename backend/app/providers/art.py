"""Static SVG product illustrations served by the backend.

Sample-data products reference these instead of hot-linking merchant images,
so the UI always has a real, self-contained visual with no broken links.
"""

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
PRODUCTS_DIR = STATIC_DIR / "products"


def ensure_product_art() -> None:
    """Create the product illustration SVGs on first run (idempotent)."""
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, svg in PRODUCT_ART.items():
        path = PRODUCTS_DIR / f"{name}.svg"
        if not path.exists():
            path.write_text(svg, encoding="utf-8")


def product_art_url(backend_url: str, key: str) -> str:
    return f"{backend_url.rstrip('/')}/static/products/{key}.svg"


_BG = (
    '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#101423"/><stop offset="100%" stop-color="#070a12"/>'
    "</linearGradient>"
    '<radialGradient id="glow" cx="50%" cy="35%" r="65%">'
    '<stop offset="0%" stop-color="#4f8cff" stop-opacity="0.55"/>'
    '<stop offset="100%" stop-color="#4f8cff" stop-opacity="0"/>'
    "</radialGradient></defs>"
)

_FRAME = (
    '<rect width="640" height="480" rx="24" fill="url(#bg)"/>'
    '<ellipse cx="320" cy="180" rx="260" ry="180" fill="url(#glow)"/>'
)


def _wrap(inner: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480">{_BG}{_FRAME}'
        f"{inner}</svg>"
    )


_LAPTOP = _wrap(
    '<g stroke="#8fb8ff" stroke-width="6" fill="none" stroke-linejoin="round">'
    '<rect x="170" y="130" width="300" height="190" rx="12" fill="#0d1424"/>'
    '<rect x="190" y="150" width="260" height="150" rx="6" fill="#12203a"/>'
    '<path d="M140 330 h360 l24 40 h-408 z" fill="#0d1424"/></g>'
    '<g fill="#5b9dff"><rect x="210" y="170" width="120" height="10" rx="5"/>'
    '<rect x="210" y="192" width="170" height="10" rx="5" opacity="0.7"/>'
    '<rect x="210" y="214" width="90" height="10" rx="5" opacity="0.5"/></g>'
    '<circle cx="320" cy="352" r="7" fill="#a06bff"/>'
)

_SMARTPHONE = _wrap(
    '<g stroke="#8fb8ff" stroke-width="6" fill="#0d1424" stroke-linejoin="round">'
    '<rect x="245" y="70" width="150" height="330" rx="26"/>'
    '<rect x="261" y="92" width="118" height="286" rx="14" fill="#12203a" stroke="none"/></g>'
    '<rect x="296" y="80" width="48" height="8" rx="4" fill="#1c2c4d"/>'
    '<g fill="#5b9dff"><rect x="278" y="130" width="84" height="12" rx="6"/>'
    '<rect x="278" y="156" width="60" height="10" rx="5" opacity="0.7"/>'
    '<rect x="278" y="182" width="72" height="10" rx="5" opacity="0.5"/></g>'
    '<circle cx="320" cy="350" r="18" fill="none" stroke="#a06bff" stroke-width="5"/>'
)

_HEADPHONES = _wrap(
    '<g stroke="#8fb8ff" stroke-width="7" fill="none" stroke-linecap="round">'
    '<path d="M180 260 v-30 a140 140 0 0 1 280 0 v30"/>'
    '<rect x="150" y="250" width="70" height="110" rx="24" fill="#0d1424"/>'
    '<rect x="420" y="250" width="70" height="110" rx="24" fill="#0d1424"/></g>'
    '<g fill="#5b9dff"><rect x="168" y="278" width="34" height="54" rx="17"/>'
    '<rect x="438" y="278" width="34" height="54" rx="17"/></g>'
    '<circle cx="320" cy="200" r="10" fill="#a06bff"/>'
)

_SMARTWATCH = _wrap(
    '<g stroke="#8fb8ff" stroke-width="6" fill="#0d1424" stroke-linejoin="round">'
    '<rect x="255" y="60" width="130" height="70" rx="16"/>'
    '<rect x="255" y="350" width="130" height="70" rx="16"/>'
    '<rect x="235" y="130" width="170" height="220" rx="42"/></g>'
    '<rect x="253" y="150" width="134" height="180" rx="28" fill="#12203a"/>'
    '<circle cx="320" cy="240" r="52" fill="none" stroke="#5b9dff" stroke-width="6"/>'
    '<path d="M320 205 v38 l26 16" stroke="#a06bff" stroke-width="6" fill="none" '
    'stroke-linecap="round"/>'
)

_TABLET = _wrap(
    '<g stroke="#8fb8ff" stroke-width="6" fill="#0d1424" stroke-linejoin="round">'
    '<rect x="160" y="90" width="320" height="240" rx="18"/>'
    '<rect x="178" y="108" width="284" height="204" rx="10" fill="#12203a" stroke="none"/></g>'
    '<g fill="#5b9dff"><rect x="200" y="140" width="150" height="12" rx="6"/>'
    '<rect x="200" y="168" width="220" height="10" rx="5" opacity="0.7"/>'
    '<rect x="200" y="192" width="180" height="10" rx="5" opacity="0.5"/></g>'
    '<circle cx="430" cy="290" r="8" fill="#a06bff"/>'
)

_CAMERA = _wrap(
    '<g stroke="#8fb8ff" stroke-width="6" fill="#0d1424" stroke-linejoin="round">'
    '<path d="M150 170 h70 l24-34 h152 l24 34 h70 a20 20 0 0 1 20 20 v160 '
    'a20 20 0 0 1 -20 20 h-340 a20 20 0 0 1 -20 -20 v-160 a20 20 0 0 1 20 -20 z"/></g>'
    '<circle cx="320" cy="270" r="72" fill="#12203a" stroke="#5b9dff" stroke-width="8"/>'
    '<circle cx="320" cy="270" r="38" fill="#0b1120" stroke="#a06bff" stroke-width="6"/>'
    '<circle cx="440" cy="210" r="12" fill="#5b9dff"/>'
)

PRODUCT_ART = {
    "laptop": _LAPTOP,
    "smartphone": _SMARTPHONE,
    "headphones": _HEADPHONES,
    "smartwatch": _SMARTWATCH,
    "tablet": _TABLET,
    "camera": _CAMERA,
    "default": _wrap(
        '<rect x="200" y="140" width="240" height="200" rx="20" fill="#0d1424" '
        'stroke="#8fb8ff" stroke-width="6"/>'
        '<path d="M240 210 h160 M240 250 h120 M240 290 h140" stroke="#5b9dff" '
        'stroke-width="10" stroke-linecap="round" opacity="0.7"/>'
    ),
}
