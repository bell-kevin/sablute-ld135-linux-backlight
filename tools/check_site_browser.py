#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Optional Playwright checks for the website, with and without JavaScript.

Serves only local files. Playwright and its selected browser must already be
installed; neither is a dependency of the keyboard helper or the published site.
"""

import argparse
from contextlib import contextmanager, ExitStack
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
from threading import Thread
from urllib.parse import urlsplit


WIDTHS = (320, 390, 820, 1440)
BACKGROUND = {"light": "rgb(245, 245, 239)", "dark": "rgb(21, 28, 24)"}
KEY_LIGHT = {
    "white": "#ffffff", "blue": "#9bbfff", "red": "#ffaaa0",
    "green": "#a4f9b2", "cyan": "#a1f4f6", "yellow": "#fff2a6",
    "pink": "#f6b3fa",
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextmanager
def serve(directory):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(directory.resolve()))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def inspect_page(page, url):
    errors = []
    requests = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requests.append(request.url))
    page.on("requestfailed", lambda request: errors.append(
        f"{request.url}: {request.failure}"))
    page.on("response", lambda response: errors.append(
        f"HTTP {response.status}: {response.url}")
        if response.status >= 400 and not response.url.endswith("/favicon.ico")
        else None)
    page.goto(url, wait_until="networkidle")
    return errors, requests


def no_overflow(page):
    assert page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    ), "The page scrolls horizontally"


def compare_screenshot(actual, expected, label):
    if actual == expected:
        return
    directory = Path(tempfile.mkdtemp(prefix="ld135-browser-diff-"))
    (directory / "actual.png").write_bytes(actual)
    (directory / "expected.png").write_bytes(expected)
    raise AssertionError(f"{label}: screenshots differ; inspect {directory}")


def screenshot_matrix(browser, url, baseline_url, expect):
    for theme in ("light", "dark"):
        for width in WIDTHS:
            images = {}
            for scripts in (True, False):
                context = browser.new_context(
                    java_script_enabled=scripts, color_scheme=theme,
                    reduced_motion="reduce", viewport={"width": width, "height": 900}
                )
                try:
                    page = context.new_page()
                    errors, requests = inspect_page(page, url)
                    expect(page.locator("body")).to_have_css(
                        "background-color", BACKGROUND[theme])
                    for selector in ("#theme-select", "#cycle-color", "#reset-color", "[data-copy]"):
                        for control in page.locator(selector).all():
                            expect(control).to_be_visible()
                            expect(control).to_be_enabled()
                    no_overflow(page)
                    images[scripts] = page.screenshot(
                        full_page=True, animations="disabled", caret="hide")
                    assert not errors, errors
                    if not scripts:
                        assert not any(urlsplit(request).path.endswith(".js")
                                       for request in requests), requests
                finally:
                    context.close()
            label = f"{theme}, {width}px"
            compare_screenshot(images[False], images[True], f"JS on/off at {label}")
            if baseline_url:
                context = browser.new_context(
                    color_scheme=theme, reduced_motion="reduce",
                    viewport={"width": width, "height": 900}
                )
                try:
                    page = context.new_page()
                    errors, _ = inspect_page(page, baseline_url)
                    before = page.screenshot(
                        full_page=True, animations="disabled", caret="hide")
                    assert not errors, errors
                    compare_screenshot(images[True], before, f"JS baseline at {label}")
                finally:
                    context.close()


def check_interactions(browser, browser_name, url, scripts, expect):
    context = browser.new_context(
        java_script_enabled=scripts, color_scheme="light", reduced_motion="reduce",
        viewport={"width": 390, "height": 900}
    )
    try:
        if scripts:
            if browser_name == "chromium":
                context.grant_permissions(["clipboard-read", "clipboard-write"])
            else:
                # These engines do not expose the same clipboard permissions.
                # Verify the text passed to the real application's click handler.
                context.add_init_script("""Object.defineProperty(navigator, 'clipboard', {
                    value: {writeText: async text => { window.copiedCommand = text; }}
                });""")
        page = context.new_page()
        errors, requests = inspect_page(page, url)
        theme = page.locator("#theme-select")
        for os_theme in ("dark", "light"):
            page.emulate_media(color_scheme=os_theme)
            expect(page.locator("body")).to_have_css(
                "background-color", BACKGROUND[os_theme])
        for choice in ("dark", "light", "auto"):
            theme.select_option(choice)
            expected = "light" if choice == "auto" else choice
            expect(page.locator("body")).to_have_css(
                "background-color", BACKGROUND[expected])
        theme.select_option("dark")
        page.emulate_media(color_scheme="light")
        expect(page.locator("body")).to_have_css("background-color", BACKGROUND["dark"])
        if scripts:
            page.reload(wait_until="networkidle")
            expect(theme).to_have_value("dark")
            expect(page.locator("body")).to_have_css("background-color", BACKGROUND["dark"])
            assert page.locator('meta[name="theme-color"]').evaluate_all(
                "metas => metas.every(meta => meta.content === '#151c18')")
        else:
            assert page.locator("html").get_attribute("data-theme") is None
            theme.focus()
            theme.press("Home")
            expect(theme).to_have_value("auto")
            page.emulate_media(color_scheme="dark")
            expect(page.locator("body")).to_have_css("background-color", BACKGROUND["dark"])
            theme.press("End")
            expect(theme).to_have_value("light")
            expect(page.locator("body")).to_have_css("background-color", BACKGROUND["light"])

        preview = page.locator(".preview")
        cycle = page.locator("#cycle-color")
        if scripts:
            for color in (*list(KEY_LIGHT)[1:], "white"):
                cycle.click()
                expect(page.locator("#preview-color")).to_have_text(color.title())
                expect(preview).to_have_css("--key-light", KEY_LIGHT[color])
                expect(page.locator("#color-picker")).to_be_hidden()
            cycle.click()
        else:
            cycle.focus()
            cycle.press("Enter")
            expect(page.locator("#color-picker")).to_be_visible()
            no_overflow(page)
            for color, light in KEY_LIGHT.items():
                page.locator(f'#preview-palette input[value="{color}"]').check()
                expect(preview).to_have_css("--key-light", light)
                badge = page.locator("#preview-color") if color == "white" else page.locator(
                    f'.preview-color-option[data-color="{color}"]')
                expect(badge).to_be_visible()
                expect(badge).to_have_text(color.title())
            page.keyboard.press("Escape")
            expect(page.locator("#color-picker")).to_be_hidden()
        page.locator("#reset-color").click()
        expect(preview).to_have_css("--key-light", KEY_LIGHT["white"])
        expect(page.locator("#preview-color")).to_be_visible()
        expect(page.locator("#preview-color")).to_have_text("White")

        for button in page.locator("[data-copy]").all():
            command = page.locator(f'#{button.get_attribute("data-copy")}').text_content()
            button.click()
            if scripts:
                expect(button).to_have_text("Copied ✓")
                copied = page.evaluate("navigator.clipboard.readText()" if browser_name == "chromium"
                                       else "window.copiedCommand")
                assert copied == command, "Clipboard contents differ from the displayed command"
                expect(page.locator("#copy-help")).to_be_hidden()
            else:
                expect(page.locator("#copy-help")).to_be_visible()
                no_overflow(page)
                page.keyboard.press("Escape")
                expect(page.locator("#copy-help")).to_be_hidden()
        assert not errors, errors
        if not scripts:
            assert not any(urlsplit(request).path.endswith(".js") for request in requests), requests
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium")
    parser.add_argument("--baseline-directory", type=Path,
                        help="Optional previous docs directory for unchanged JS appearance checks")
    args = parser.parse_args()
    try:
        from playwright.sync_api import sync_playwright, expect
    except ImportError:
        parser.error("Install optional browser tools: python3 -m pip install playwright; "
                     f"python3 -m playwright install {args.browser}")
    directory = Path(__file__).resolve().parent.parent / "docs"
    if args.baseline_directory and not (args.baseline_directory / "index.html").is_file():
        parser.error("--baseline-directory must contain the previous website's index.html and assets")
    try:
        with ExitStack() as stack:
            url = stack.enter_context(serve(directory))
            baseline_url = stack.enter_context(serve(args.baseline_directory)) if args.baseline_directory else None
            playwright = stack.enter_context(sync_playwright())
            browser = getattr(playwright, args.browser).launch()
            stack.callback(browser.close)
            screenshot_matrix(browser, url, baseline_url, expect)
            for scripts in (False, True):
                check_interactions(browser, args.browser, url, scripts, expect)
    except Exception as error:
        print(f"Browser check failed ({args.browser}): {error}", file=sys.stderr)
        return 1
    print(f"Browser checks passed ({args.browser}): identical JS/no-JS screenshots at four widths "
          "in both themes; OS and manual themes, preview, copy controls, and responsive layout."
          + (" The JS appearance also matches the baseline." if baseline_url else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
