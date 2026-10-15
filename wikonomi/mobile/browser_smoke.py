"""Automated Android-sized Chromium smoke test against an isolated local Django DB.

Never runs against wikonomi.com or Render. Requires Playwright/Chromium installed.
Usage (in wikonomi/): python manage.py migrate && python mobile/browser_smoke.py
"""
import io
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

os.environ["DJANGO_SETTINGS_MODULE"] = "wikonomi.test_settings"
import django  # noqa: E402
django.setup()
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402
from core.models import Business, BusinessBranch, Product  # noqa: E402
from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright, expect  # noqa: E402

ROOT = "http://127.0.0.1:8765"
User = get_user_model()
user, _ = User.objects.get_or_create(username="mobile-browser-ci")
user.set_password("ci-test-not-production")
user.save()
Product.objects.get_or_create(name="CI Trukai Rice 1kg", defaults={"slug": "ci-trukai-rice-1kg"})
business, _ = Business.objects.get_or_create(name="CI Test Grocery", defaults={"slug": "ci-test-grocery"})
BusinessBranch.objects.get_or_create(
    canonical_business=business, slug="ci-test-grocery-main",
    defaults={"name": "Main", "latitude": -9.46, "longitude": 147.16},
)
client = Client()
client.force_login(user)
session = client.cookies[settings.SESSION_COOKIE_NAME].value

with tempfile.TemporaryDirectory() as directory:
    image_path = Path(directory) / "price-tag.png"
    Image.new("RGB", (800, 600), "white").save(image_path)
    screenshots = Path("browser-screenshots")
    screenshots.mkdir(exist_ok=True)
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", "127.0.0.1:8765", "--noreload"],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "wikonomi.test_settings"},
    )
    try:
        for attempt in range(35):
            try:
                with urlopen(ROOT + "/healthz/", timeout=2) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("Local Django UI test server did not start")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2, is_mobile=True, has_touch=True,
                base_url=ROOT,
            )
            context.add_cookies([{
                "name": settings.SESSION_COOKIE_NAME,
                "value": session,
                "domain": "127.0.0.1", "path": "/",
                "httpOnly": True, "sameSite": "Lax",
            }])
            page = context.new_page()
            page.goto("/app/", wait_until="domcontentloaded")
            expect(page.get_by_role("heading", name="Help PNG find better prices.")).to_be_visible()
            expect(page.get_by_role("link", name="Snap a price")).to_be_visible()
            page.screenshot(path=str(screenshots / "home.png"), full_page=True)

            page.get_by_role("link", name="Snap a price").first.click()
            expect(page.locator("#price-form")).to_be_visible()
            page.locator("#id_photo").set_input_files(str(image_path))
            expect(page.locator("#photo-preview")).to_be_visible()

            page.locator("#product-search").fill("CI Trukai")
            expect(page.get_by_role("option", name="CI Trukai Rice 1kg")).to_be_visible()
            page.get_by_role("option", name="CI Trukai Rice 1kg").click()
            page.locator("#branch-search").fill("CI Test Grocery")
            expect(page.get_by_role("option", name="CI Test Grocery Main")).to_be_visible()
            page.get_by_role("option", name="CI Test Grocery Main").click()

            page.locator("#id_price").fill("12.50")
            page.get_by_role("button", name="Save draft").click()
            expect(page.locator("#draft-status")).to_contain_text("Draft saved")
            page.screenshot(path=str(screenshots / "submit.png"), full_page=True)
            page.get_by_role("button", name="Submit price").click()
            expect(page).to_have_url(__import__("re").compile(r".*/app/\\?created=.*"))
            expect(page.get_by_text("Price submitted for review.")).to_be_visible()
            expect(page.get_by_text("CI Trukai Rice 1kg")).to_be_visible()
            page.screenshot(path=str(screenshots / "success.png"), full_page=True)
            print("PASS: Android-sized dashboard, photo upload, suggestions, offline draft and contribution")
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()
