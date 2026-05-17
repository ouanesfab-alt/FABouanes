import os
from pathlib import Path

def bundle_js():
    static_js = Path("static/js")
    bundle_path = static_js / "app.bundle.js"
    
    # Files to bundle in order
    files = [
        "theme.js",
        "api.js",
        "layout.js",
        "forms.js",
        "tables.js",
        "notifications.js",
        "app.js"
    ]

    
    content = []
    for f in files:
        p = static_js / f if f != "app.js" else Path("static/app.js")
        if p.exists():
            content.append(f"// --- {f} ---")
            content.append(p.read_text(encoding="utf-8"))
            content.append("\n")

    
    bundle_path.write_text("\n".join(content), encoding="utf-8")
    print(f"Bundle created: {bundle_path} ({len(bundle_path.read_bytes())} bytes)")

if __name__ == "__main__":
    bundle_js()
