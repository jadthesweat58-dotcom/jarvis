"""Bundle the Jarvis dashboard into one self-contained demo page.

The page runs with no server: demo/demo-backend.js answers the dashboard's API
calls in the browser and Jarvis thinks with Claude through the claude.ai
artifact "sample" capability.

    python scripts/build_demo.py [output.html]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "jarvis" / "static"


def build() -> str:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    shim = (ROOT / "demo" / "demo-backend.js").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")

    # The artifact host supplies the document skeleton, charset/viewport and favicon.
    for pattern in (r"<!doctype html>\s*", r"<html[^>]*>\s*", r"</?head>\s*", r"<body>\s*",
                    r"</body>\s*", r"</html>\s*", r'<meta charset="utf-8">\s*',
                    r'<meta name="viewport"[^>]*>\s*', r'<link rel="icon" href="data:[^"]*">\s*',
                    # installing as an app and push notifications need the real server
                    r'<link rel="(?:manifest|apple-touch-icon)"[^>]*>\s*',
                    r'<meta name="(?:theme-color|mobile-web-app-capable|apple-mobile-web-app-[\w-]+)"[^>]*>\s*'):
        html = re.sub(pattern, "", html, flags=re.IGNORECASE)

    dark = ":root { color-scheme: dark; }\nhtml, body { background: #030912; }\n"
    html = html.replace('<link rel="stylesheet" href="/static/style.css">',
                        f"<style>\n{dark}{css}</style>")
    html = html.replace('<script src="/static/app.js"></script>',
                        f"<script>\n{shim}</script>\n<script>\n{app}</script>")
    if "/static/" in html:
        raise SystemExit("build_demo: an asset reference was not inlined")
    return html.strip() + "\n"


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "demo" / "jarvis-demo.html"
    out.write_text(build(), encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")
