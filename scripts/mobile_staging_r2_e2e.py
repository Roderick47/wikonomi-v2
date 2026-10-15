"""One-off authenticated staging R2 image round-trip over the actual mobile app.

Writes one synthetic staging-only user and one pending demo price submission.
Never accesses wikonomi.com, real product data, production media or credentials.
"""
import io
import re
import secrets
import sys
import uuid
from html import unescape
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image

ORIGIN = "https://wikonomi-mobile-staging.onrender.com"
TIMEOUT = 75


def assert_staging_url(value):
    absolute = urljoin(ORIGIN, value)
    if urlparse(absolute).netloc != urlparse(ORIGIN).netloc:
        raise AssertionError("Refusing to access a non-staging host")
    return absolute


def csrf_token(html):
    match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    if not match:
        raise AssertionError("Django CSRF field is missing")
    return unescape(match.group(1))


def get(session, path):
    response = session.get(assert_staging_url(path), timeout=TIMEOUT)
    response.raise_for_status()
    return response


def form_post(session, path, *, data, files=None):
    response = session.post(
        assert_staging_url(path), data=data, files=files, timeout=TIMEOUT,
        allow_redirects=False, headers={"Referer": assert_staging_url(path)},
    )
    if response.status_code != 302:
        raise AssertionError(
            f"Staging submission returned HTTP {response.status_code}, expected 302"
        )
    assert_staging_url(response.headers.get("Location", ""))
    return response


def lookup_id(session, kind, query, exact_name):
    body = get(session, f"/app/search/{kind}/?q={requests.utils.quote(query)}").json()
    for row in body.get("results", []):
        if row["name"] == exact_name:
            return row["id"]
    raise AssertionError(f"Staging demo {kind} missing; no real catalog may be used")


def main():
    session = requests.Session()
    status = get(session, "/app/staging-db-status/").json()
    if status != {
        "staging_database_ready": True,
        "mobile_migrations_ready": True,
        "staging_media_configured": True,
    }:
        raise AssertionError(f"Staging database/media readiness incomplete: {status}")
    print("PASS staging PostgreSQL and dedicated R2 configuration are enabled")

    identifier = uuid.uuid4().hex
    username = "r2pilot_" + identifier[:12]
    password = "Wk!" + secrets.token_urlsafe(29)
    signup_page = get(session, "/users/signup/?next=/app/")
    response = form_post(
        session, "/users/signup/?next=/app/",
        data={
            "csrfmiddlewaretoken": csrf_token(signup_page.text),
            "username": username,
            "first_name": "Staging",
            "last_name": "R2Probe",
            "email": "mobile-r2-qa+" + identifier[:12] + "@example.com",
            "password1": password,
            "password2": password,
            "next": "/app/",
        },
    )
    if "/users/welcome/" not in response.headers["Location"]:
        raise AssertionError("Staging-only signup did not reach welcome flow")
    print("PASS created isolated staging-only synthetic contributor")

    product_id = lookup_id(session, "products", "Wikonomi Demo Rice", "Wikonomi Demo Rice 1kg")
    branch_id = lookup_id(session, "branches", "Wikonomi Demo Shop", "Wikonomi Demo Shop Main")
    print("PASS demo-only product and branch search")

    submit = get(session, "/app/submit/")
    buffer = io.BytesIO()
    Image.new("RGB", (80, 60), "#f0f0f0").save(buffer, "PNG")
    image_bytes = buffer.getvalue()
    client_id = str(uuid.uuid4())
    response = form_post(
        session, "/app/submit/",
        data={
            "csrfmiddlewaretoken": csrf_token(submit.text),
            "client_submission_id": client_id,
            "product": str(product_id),
            "business_branch": str(branch_id),
            "price": "12.50",
        },
        files={"photo": ("synthetic-staging-r2-proof.png", io.BytesIO(image_bytes), "image/png")},
    )
    if "?created=" + client_id not in response.headers["Location"]:
        raise AssertionError("Price submission did not return expected success redirect")
    print("PASS synthetic image and pending price submitted")

    home = get(session, response.headers["Location"])
    if "Price submitted for review" not in home.text:
        raise AssertionError("No pending contribution confirmation")
    match = re.search(r'href="(/app/evidence/[0-9a-f-]+/)"', home.text)
    if not match:
        raise AssertionError("Protected price-photo evidence link not displayed")
    evidence_path = match.group(1)
    photo = get(session, evidence_path)
    if photo.content != image_bytes or not photo.content.startswith(b"\\x89PNG"):
        raise AssertionError("Staging evidence downloaded incorrectly")
    print("PASS evidence photo round-trip matches original PNG bytes")

    unauthenticated = requests.get(assert_staging_url(evidence_path), timeout=TIMEOUT, allow_redirects=False)
    if unauthenticated.status_code != 302:
        raise AssertionError("Original image accessible without logging in")
    print("PASS anonymous evidence access is blocked")

    fresh = requests.Session()
    login_page = get(fresh, "/users/login/?next=/app/")
    form_post(
        fresh, "/users/login/?next=/app/",
        data={"csrfmiddlewaretoken": csrf_token(login_page.text),
              "username": username, "password": password, "next": "/app/"},
    )
    again = get(fresh, evidence_path)
    if again.content != image_bytes:
        raise AssertionError("New session cannot retrieve the stored original image")
    print("PASS photo retrieved from a new authenticated session")
    print("PASS complete private R2 image submission/retrieval smoke test")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAIL staging R2 smoke:", str(exc), file=sys.stderr)
        raise
