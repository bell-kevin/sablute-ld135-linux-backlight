#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Check static-site metadata, local links, and assets without network access.

This is a small project check, not a complete HTML or CSS validator. It never
loads external URLs, executes site JavaScript, or opens a hardware device.
"""

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


PERSONAL_PATH = re.compile(r"/home/[^/\s<>]+/|/Users/[^/\s<>]+/|[A-Za-z]:\\Users\\")
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
CSS_IMPORT = re.compile(r"@import\s+(['\"])(.*?)\1", re.IGNORECASE)


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.language = None
        self.title = []
        self.in_title = False
        self.viewport = None
        self.ids = set()
        self.duplicate_ids = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.language = attrs.get("lang")
        if tag == "title":
            self.in_title = True
        if tag == "meta" and (attrs.get("name") or "").lower() == "viewport":
            self.viewport = attrs.get("content")
        identifier = attrs.get("id")
        if identifier:
            if identifier in self.ids:
                self.duplicate_ids.add(identifier)
            self.ids.add(identifier)
        for name in ("href", "src"):
            if attrs.get(name) is not None:
                self.links.append(attrs[name])

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def check_site(directory):
    root = directory.resolve()
    errors = []
    pages = {}
    references = []
    if not root.is_dir() or not (root / "index.html").is_file():
        return ["The site directory must contain index.html."]

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not path.resolve().is_relative_to(root):
            errors.append(f"{path.name}: file points outside the site directory")
            continue
        if path.suffix.lower() not in (".html", ".css", ".js", ".svg"):
            continue
        label = path.relative_to(root)
        source = path.read_text(encoding="utf-8")
        if PERSONAL_PATH.search(source) or "file://" in source:
            errors.append(f"{label}: contains a local personal or file URL path")
        if path.suffix.lower() == ".html":
            page = Page(path)
            page.feed(source)
            page.close()
            pages[path.resolve()] = page
            if not page.language or not page.language.strip():
                errors.append(f"{label}: missing html lang")
            if not "".join(page.title).strip():
                errors.append(f"{label}: missing nonempty title")
            if not page.viewport or "width=device-width" not in page.viewport.replace(" ", ""):
                errors.append(f"{label}: missing responsive viewport metadata")
            for identifier in sorted(page.duplicate_ids):
                errors.append(f"{label}: duplicate id {identifier!r}")
            references.extend((path, link) for link in page.links)
        elif path.suffix.lower() == ".css":
            references.extend((path, match.group(2)) for match in CSS_URL.finditer(source))
            references.extend((path, match.group(2)) for match in CSS_IMPORT.finditer(source))

    for source_path, link in references:
        label = source_path.relative_to(root)
        link = link.strip()
        try:
            url = urlsplit(link)
        except ValueError:
            errors.append(f"{label}: malformed URL {link!r}")
            continue
        if url.scheme or url.netloc:
            # External links and inline data are intentionally not fetched.
            continue
        local_path = unquote(url.path)
        if local_path.startswith("/") or "\\" in local_path:
            errors.append(f"{label}: local URL must be relative: {link!r}")
            continue
        target = (source_path.parent / local_path).resolve() if local_path else source_path.resolve()
        if not target.is_relative_to(root):
            errors.append(f"{label}: local URL escapes the site directory: {link!r}")
            continue
        if target.is_dir():
            target = (target / "index.html").resolve()
        if not target.is_relative_to(root) or not target.is_file():
            errors.append(f"{label}: local URL has no site file: {link!r}")
            continue
        if url.fragment and target.suffix.lower() == ".html":
            page = pages.get(target)
            if page is None or unquote(url.fragment) not in page.ids:
                errors.append(f"{label}: missing HTML anchor: {link!r}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path,
                        default=Path(__file__).resolve().parent.parent / "docs",
                        help="Site directory (default: the project's docs directory)")
    args = parser.parse_args()
    try:
        errors = check_site(args.directory)
    except (OSError, UnicodeError) as error:
        errors = [str(error)]
    if errors:
        for error in errors:
            print(f"Site check: {error}", file=sys.stderr)
        return 1
    print("Site checks passed: metadata, local links, assets, and portable paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
