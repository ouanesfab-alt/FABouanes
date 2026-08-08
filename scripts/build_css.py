#!/usr/bin/env python3
"""
FABouanes CSS Production Minifier & Bundler Script
Combines tokens.css, components.css, fonts.css, and app.css into a single minified production bundle with content hash.
"""

import hashlib
import pathlib
import re

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
DIST_DIR = STATIC_DIR / "dist"

FILES_TO_BUNDLE = [
    STATIC_DIR / "css" / "tokens.css",
    STATIC_DIR / "css" / "components.css",
    STATIC_DIR / "fonts" / "fonts.css",
    STATIC_DIR / "app.css",
]

def minify_css(css_text: str) -> str:
    """Perform fast, safe regex-based CSS minification."""
    # Strip comments
    css_text = re.sub(r'/\*[\s\S]*?\*/', '', css_text)
    # Strip whitespace around delimiters
    css_text = re.sub(r'\s*([\{\}:;,])\s*', r'\1', css_text)
    # Remove trailing semicolons before closing brace
    css_text = re.sub(r';\}', '}', css_text)
    # Remove redundant whitespace
    css_text = re.sub(r'\s+', ' ', css_text)
    return css_text.strip()

def main():
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    combined = []
    
    for path in FILES_TO_BUNDLE:
        if path.exists():
            combined.append(path.read_text(encoding='utf-8', errors='ignore'))
            
    full_css = "\n".join(combined)
    minified = minify_css(full_css)
    content_hash = hashlib.md5(minified.encode('utf-8')).hexdigest()[:8]
    
    output_bundle = DIST_DIR / f"bundle.{content_hash}.min.css"
    output_bundle.write_text(minified, encoding='utf-8')
    print(f"[OK] Generated production CSS bundle: {output_bundle.name} ({len(minified):,} bytes)")

if __name__ == "__main__":
    main()
